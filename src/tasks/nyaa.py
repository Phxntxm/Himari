from typing import cast

import aiohttp
import discord
import feedparser
import sqlalchemy as sa
from discord.ext import tasks

from src import Session, bot
from src.models.database import Nyaa
from src.utils import search
from src.utils.nyaa import magnet

URL = "https://nyaa.si/?page=rss"


async def generate_embed(entry) -> discord.Embed:
    """
    Generates a discord embed for a nyaa torrent.
    """
    title = entry.title
    hash = entry.nyaa_infohash
    url = entry.id
    category = entry.nyaa_category
    size = entry.nyaa_size
    torrent_link = entry.link
    magnet_link = await magnet(title, hash)

    embed = discord.Embed(
        title=title,
        url=url,
        description=f"""
[Download Torrent]({torrent_link})
Magnet Link (Copy paste): {magnet_link}

**Category:** {category}
**Size:** {size}
""",
    )

    return embed


def get_latest(
    feed, name: str, latest: str | None = None
) -> list[feedparser.FeedParserDict]:
    results = []

    for entry in feed.entries:
        if not search(entry.title, name):
            continue

        # This one's a bit special, only give us the latest one, and then stop.
        if latest is None:
            results.append(entry)
            break

        if entry.id == latest:
            break

        results.append(entry)

    return results


@tasks.loop(seconds=5)
async def nyaa():
    await bot.wait_until_ready()

    with Session.begin() as db:
        feeds = db.execute(sa.select(Nyaa)).scalars().all()

        async with aiohttp.ClientSession() as session:
            # Get the RSS feed data
            async with session.get(URL) as resp:
                if resp.status > 299:
                    return

                # Pass to feedparser
                data = feedparser.parse(await resp.text())

        # Go through each RSS feed
        for nyaa_match in feeds:
            # Make sure the channel exists we want to send to
            guild = bot.get_guild(nyaa_match.guild_id)
            if guild is None:
                continue
            channel = guild.get_channel(nyaa_match.channel_id)
            if channel is None:
                continue
            if not isinstance(channel, discord.TextChannel):
                continue

            entry = None

            for entry in reversed(
                get_latest(data, nyaa_match.match, nyaa_match.latest)
            ):
                embed = await generate_embed(entry)
                await channel.send(embed=embed)

            if entry is not None:
                nyaa_match.latest = cast(str, entry.id)
