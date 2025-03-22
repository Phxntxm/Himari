import io
import json
import logging
from typing import TypedDict, Union

import aiohttp
import discord
import sqlalchemy as sa
from discord.ext import commands, tasks

from src import Session
from src.models.database import Manga
from src.utils import get_channel
from src.utils.mangadex import Chapter, latest_chapter, search_manga
from src.views.mangadex import MangaNotificationView, MangaSearch

logger = logging.getLogger(__name__)


class MangadexGroupedItem(TypedDict):
    id: str


class MangaDBItem(TypedDict):
    mangadex_id: str
    mangas: list[MangadexGroupedItem]


@discord.app_commands.guild_only()
class MangaDexCog(
    commands.GroupCog,
    name="mangadex",
    description="Commands to manage MangaDex RSS feed stuff.",
):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.mangadex.start()

    async def cog_unload(self) -> None:
        self.mangadex.cancel()

    @discord.app_commands.command(description="Add a manga to follow the latest chapters of.")
    @discord.app_commands.describe(
        manga="The manga you want to follow the latest chapters of.",
        channel="The channel to post the latest chapters in.",
    )
    async def follow(
        self, interaction: discord.Interaction, manga: str, channel: Union[discord.Thread, discord.TextChannel]
    ):
        """
        Add a manga to follow the latest chapters of.
        """
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        mangas = await search_manga(manga)

        if len(mangas) == 0:
            await interaction.response.send_message("No manga found with that name.", ephemeral=True)
            return

        if len(mangas) == 1:
            _manga = mangas[0]

            with Session.begin() as db:
                db_manga = db.execute(
                    sa.select(Manga).filter(Manga.mangadex_id == _manga.id, Manga.guild_id == interaction.guild.id)
                ).scalar_one_or_none()

                if db_manga is not None:
                    await interaction.response.send_message("That manga is already in the list.", ephemeral=True)
                    return

                db.add(
                    Manga(
                        title=_manga.title,
                        description=_manga.description,
                        mangadex_id=_manga.id,
                        cover=_manga.cover,
                        guild_id=interaction.guild.id,
                        channel_id=channel.id,
                    )
                )

            await interaction.response.send_message(f"Added {_manga.title} to the manga list.", ephemeral=True)
        else:
            view = MangaSearch(mangas, interaction.user.id, channel)

            await interaction.response.send_message(
                f"There are {len(mangas)} mangas matching that search term. Please select the one you want to follow.",
                ephemeral=True,
                view=view,
            )

    @discord.app_commands.command(description="Get notifications when a new chapter of a manga is released.")
    async def notifications(self, interaction: discord.Interaction):
        if interaction.guild is None or interaction.channel is None:
            return await interaction.response.send_message("This command must be used in a server.")

        with Session(expire_on_commit=False) as db:
            mangas = db.query(Manga).filter(Manga.guild_id == interaction.guild.id).all()

            view = MangaNotificationView(mangas, interaction.user.id)

        await interaction.response.send_message(
            f"Select the manga you want to get notifications for. Page {view.page}/{view.last_page}",
            ephemeral=True,
            view=view,
        )

    async def post(self, manga: Manga | None, latest: Chapter):
        if manga is None:
            return

        guild = self.bot.get_guild(manga.guild_id)

        if guild is None:
            return

        channel = await get_channel(guild, manga.channel_id)

        if channel is None:
            return

        role = discord.utils.get(guild.roles, name="Manga Updates")

        if role is None:
            role = await guild.create_role(name="Manga Updates")

        for member in role.members:
            assert self.bot.user is not None

            if member.id == self.bot.user.id:
                continue

            await member.remove_roles(role)

        for follower in manga.followers:
            member = guild.get_member(follower.user_id)

            if member is None:
                continue

            await member.add_roles(role)

        content = f"{role.mention} New chapter of {manga.title} is out!"

        title = latest.title or manga.title

        title += " "

        if latest.volume is not None:
            title += f"[Volume {latest.volume}]"

        if latest.chapter is not None:
            title += f"[Chapter {latest.chapter}]"

        embed = discord.Embed(
            title=title,
            description=manga.description,
            url=f"https://mangadex.org/chapter/{latest.id}",
        )

        embed.set_author(name=manga.title, url=f"https://mangadex.org/title/{manga.mangadex_id}")

        if manga.cover is not None:
            url = f"https://uploads.mangadex.org/covers/{manga.mangadex_id}/{manga.cover}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as res:
                    if res.status == 200:
                        data = await res.read()
                        file = discord.File(io.BytesIO(data), filename="cover.png")

                        embed.set_image(url="attachment://cover.png")

                        await channel.send(content, file=file, embed=embed)
                    else:
                        await channel.send(content, embed=embed)

    @tasks.loop(seconds=60)
    async def mangadex(self):
        await self.bot.wait_until_ready()

        with Session.begin() as db:
            # This is done this way to limit the amount of
            #  API requests we make to Mangadex.
            query = sa.select(
                Manga.mangadex_id,
                sa.func.array_agg(
                    Manga.id,
                ).label("ids"),
            ).group_by(Manga.mangadex_id)

            all_manga = db.execute(query).all()

            errors = 0

            for row in all_manga:
                ids: list[int] = row.ids

                # Get the latest chapter, just continuing to the next one if we error
                try:
                    latest = await latest_chapter(row.mangadex_id)
                except Exception:
                    # If we error 5 times in a row, just stop
                    errors += 1
                    if errors >= 5:
                        logger.error("Error getting latest chapter", exc_info=True)
                        break
                    else:
                        continue

                for id in ids:
                    manga = db.get(Manga, id)

                    # This should NEVER happen, but just for typing sake
                    if manga is None:
                        logger.error(f"Manga {id} not found in database - how the hell?")
                        continue

                    # This is to clear out any manga follows that are no longer valid
                    #  IE guild deleted, bot left guild, channel deleted, etc.
                    #  first check the guild
                    guild = self.bot.get_guild(manga.guild_id)

                    if guild is None:
                        logger.error(f"Guild not found for manga {manga.id}  - should remove in future")
                        continue

                    # Then the channel
                    channel = await get_channel(guild, manga.channel_id)

                    if channel is None:
                        logger.error(f"Channel not found for manga {manga.id} - should remove in future")
                        continue

                    # Now, if we couldn't find the manga for whatever reason (network issues)
                    #  just ignore it. We're doing this here, so that we can still check over
                    #  guilds/channels regardless of if we can get the manga or not.
                    if latest is None:
                        logger.error(f"Latest chapter not found for manga {manga.id} - most likely network issues")
                        continue

                    # Also ignore if the latest chapter is the same as the one we have stored
                    if latest.id == manga.latest_chapter_id:
                        continue

                    # Otherwise it's a new one, so post it
                    try:
                        await self.post(manga, latest)
                    except Exception as e:
                        logger.error("Error posting new chapter", exc_info=e)
                    else:
                        manga.latest_chapter_id = latest.id


async def setup(bot: commands.Bot):
    await bot.add_cog(MangaDexCog(bot))
