import io
import json
import traceback
from typing import TypedDict

import aiohttp
import discord
import sqlalchemy as sa
from discord.ext import tasks

from src import Session, bot
from src.models.database import Manga
from src.utils.mangadex import Chapter, latest_chapter


class MangadexGroupedItem(TypedDict):
    id: str


class MangaDBItem(TypedDict):
    mangadex_id: str
    mangas: list[MangadexGroupedItem]


async def post(manga: Manga | None, latest: Chapter):
    if manga is None:
        return

    guild = bot.get_guild(manga.guild_id)

    if guild is None:
        return

    channel = guild.get_channel(manga.channel_id)

    if channel is None or not isinstance(channel, discord.TextChannel):
        return

    role = discord.utils.get(guild.roles, name="Manga Updates")

    if role is None:
        role = await guild.create_role(name="Manga Updates")

    for member in role.members:
        assert bot.user is not None

        if member.id == bot.user.id:
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

    embed.set_author(
        name=manga.title, url=f"https://mangadex.org/title/{manga.mangadex_id}"
    )

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
async def mangadex():
    await bot.wait_until_ready()

    with Session.begin() as db:
        # This is done this way to limit the amount of
        #  API requests we make to Mangadex.
        query = sa.select(
            Manga.mangadex_id,
            sa.func.json_group_array(
                Manga.id,
            ).label("ids"),
        ).group_by(Manga.mangadex_id)

        all_manga = db.execute(query).all()

        for row in all_manga:
            ids: list[int] = json.loads(row.ids)

            # Get the latest chapter, just continuing to the next one if we error
            try:
                latest = await latest_chapter(row.mangadex_id)
            except Exception:
                traceback.print_exc()
                continue

            for id in ids:
                manga = db.get(Manga, id)

                # This should NEVER happen, but just for typing sake
                if manga is None:
                    continue

                # This is to clear out any manga follows that are no longer valid
                #  IE guild deleted, bot left guild, channel deleted, etc.
                #  first check the guild
                guild = bot.get_guild(manga.guild_id)

                if guild is None:
                    db.delete(manga)
                    continue

                # Then the channel
                channel = guild.get_channel(manga.channel_id)

                if channel is None or not isinstance(channel, discord.TextChannel):
                    db.delete(manga)
                    continue

                # Now, if we couldn't find the manga for whatever reason (network issues)
                #  just ignore it. We're doing this here, so that we can still check over
                #  guilds/channels regardless of if we can get the manga or not.
                if latest is None:
                    continue

                # Also ignore if the latest chapter is the same as the one we have stored
                if latest.id == manga.latest_chapter_id:
                    continue

                # Otherwise it's a new one, so post it
                try:
                    await post(manga, latest)
                except Exception:
                    traceback.print_exc()
                else:
                    manga.latest_chapter_id = latest.id
