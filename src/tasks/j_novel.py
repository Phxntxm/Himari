from typing import AsyncGenerator, cast

import aiohttp
import discord
import feedparser
import sqlalchemy as sa
from discord.ext import tasks

from src import Session, bot
from src.models.database import JNovel

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


@tasks.loop(seconds=5)
async def j_novel():
    await bot.wait_until_ready()

    with Session.begin() as db:
        feeds = db.execute(sa.select(JNovel)).scalars().all()

        for feed in feeds:
            guild = bot.get_guild(feed.guild_id)
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
