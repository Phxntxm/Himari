from typing import AsyncGenerator, cast

import aiohttp
import discord
import feedparser
import sqlalchemy as sa
from discord.ext import commands, tasks

from src import Session
from src.models.database import JNovel
from src.utils.j_novel import search_series
from src.views.j_novel import JNovelSearch

BASE = "https://labs.j-novel.club/feed/series/{}.rss"


async def get_latest(
    series: str, latest: str | None
) -> AsyncGenerator[feedparser.FeedParserDict, None]:
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE.format(series)) as resp:
            if resp.status > 299:
                return

            data = await resp.read()

    feed = feedparser.parse(data)

    for entry in feed.entries:
        # This one's a bit special, only give us the latest one, and then stop.
        if latest is None:
            yield entry
            break

        if entry.id == latest:
            break

        yield entry


@discord.app_commands.guild_only()
class JNovelCog(
    commands.GroupCog,
    name="jnovel",
    description="Commands to manage J-Novel Club RSS feed stuff.",
):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.j_novel.start()

    async def cog_unload(self) -> None:
        self.j_novel.cancel()

    @discord.app_commands.command(
        description="Add a J-Novel series to follow and post to a channel."
    )
    @discord.app_commands.describe(
        series="The series to follow.",
        channel="The channel to post to new chapters to.",
    )
    async def follow(
        self,
        interaction: discord.Interaction,
        series: str,
        channel: discord.TextChannel,
    ):
        """
        Add a J-Novel series to follow and post to a channel.
        """
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message(
                "This command must be used in a server."
            )
            return

        results = await search_series(series)

        if not results:
            return await interaction.response.send_message(
                "No results found.", ephemeral=True
            )

        if len(results) == 1:
            result = results[0]

            with Session.begin() as db:
                db_series = db.get(JNovel, result.id)

                if db_series is not None:
                    return await interaction.response.send_message(
                        "That series is already in the follow list.", ephemeral=True
                    )

                db.add(
                    JNovel(
                        series=result.id,
                        title=result.title,
                        guild_id=interaction.guild.id,
                        channel_id=channel.id,
                        creator_id=interaction.user.id,
                    )
                )

                await interaction.response.send_message(
                    f"Added {result.title} to the follow list.", ephemeral=True
                )
        else:
            view = JNovelSearch(results, interaction.user.id, channel)

            await interaction.response.send_message(
                "Select the series you want to follow.", view=view, ephemeral=True
            )

    @tasks.loop(seconds=5)
    async def j_novel(self):
        await self.bot.wait_until_ready()

        with Session.begin() as db:
            feeds = db.execute(sa.select(JNovel)).scalars().all()

            for feed in feeds:
                guild = self.bot.get_guild(feed.guild_id)
                if guild is None:
                    break
                channel = guild.get_channel(feed.channel_id)
                if channel is None:
                    break
                if not isinstance(channel, discord.TextChannel):
                    break

                results = [r async for r in get_latest(feed.series, feed.latest)]
                entry = None

                for entry in reversed(results):
                    embed = discord.Embed(
                        title=entry.title,
                        url=entry.link,
                        color=discord.Color.blurple(),
                    )

                    cover = next(
                        filter(lambda link: link.rel == "enclosure", entry.links), None
                    )

                    if cover:
                        embed.set_image(url=cover.href)

                    await channel.send(embed=embed)

                if entry is not None:
                    feed.latest = cast(str, entry.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(JNovelCog(bot))
