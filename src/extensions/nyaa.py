from typing import cast

import aiohttp
import discord
import feedparser
import sqlalchemy as sa
from discord.ext import commands, tasks

from src import Session
from src.models.database import Nyaa
from src.utils import search
from src.utils.nyaa import magnet
from src.views.nyaa import NyaaNotificationView

URL = "https://nyaa.si/?page=rss"


async def generate_embed(
    entry: feedparser.FeedParserDict, given_title: str
) -> discord.Embed:
    """
    Generates a discord embed for a nyaa torrent.
    """
    title = entry.title
    hash = entry.nyaa_infohash
    url = entry.id
    category = entry.nyaa_category
    size = entry.nyaa_size
    torrent_link = entry.link
    magnet_link = await magnet(str(title), str(hash))

    embed = discord.Embed(
        title=title,
        url=url,
        description=f"""
[Download Torrent]({torrent_link})
Magnet Link (Copy paste):
{magnet_link}

**Name:** {given_title}
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


@discord.app_commands.guild_only()
class NyaaCog(
    commands.GroupCog,
    name="nyaa",
    description="Commands to manage Nyaa.si RSS feed stuff.",
):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.nyaa.start()

    async def cog_unload(self) -> None:
        self.nyaa.cancel()

    @discord.app_commands.command(
        description="Add a new Nyaa RSS feed match to the database"
    )
    @discord.app_commands.describe(
        name="The name of the RSS feed (used for identifying the feed)",
        match="The value to match the RSS feed title against (use what you would search on Nyaa.si)",
        channel="The channel to send new RSS feed entries to",
    )
    async def follow(
        self,
        interaction: discord.Interaction,
        name: str,
        match: str,
        channel: discord.TextChannel,
    ):
        """Add a new RSS feed to the database. This will not start the feed."""
        name = name.lower()

        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message(
                "This command must be used in a server.", ephemeral=True
            )
            return

        with Session.begin() as session:
            nyaa = session.execute(
                sa.select(Nyaa).filter(
                    Nyaa.name == name, Nyaa.guild_id == interaction.guild.id
                )
            ).scalar_one_or_none()

            if nyaa:
                await interaction.response.send_message(
                    "Nyaa.si feed match already exists with that name", ephemeral=True
                )
                return

            nyaa = session.execute(
                sa.select(Nyaa).filter(
                    Nyaa.match == match, Nyaa.guild_id == interaction.guild.id
                )
            ).scalar_one_or_none()

            if nyaa:
                await interaction.response.send_message(
                    "Nyaa.si feed match already exists with that search term",
                    ephemeral=True,
                )
                return

            rss = Nyaa(
                name=name,
                match=match,
                guild_id=interaction.guild.id,
                channel_id=channel.id,
                creator_id=interaction.user.id,
            )
            session.add(rss)

        await interaction.response.send_message(f"Added Nyaa feed `{name}`")

    @discord.app_commands.command(description="Remove an RSS feed from the database")
    @discord.app_commands.describe(
        name="The name of the RSS feed",
    )
    async def unfollow(self, interaction: discord.Interaction, name: str):
        """Remove an RSS feed from the database. This will stop the feed."""
        name = name.lower()

        if (
            interaction.guild is None
            or interaction.channel is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                "This command must be used in a server.", ephemeral=True
            )
            return

        with Session.begin() as session:
            rss = session.execute(
                sa.select(Nyaa).filter(
                    Nyaa.name == name, Nyaa.guild_id == interaction.guild.id
                )
            ).scalar_one_or_none()

            if not rss:
                await interaction.response.send_message(
                    "RSS feed does not exist", ephemeral=True
                )
                return

            if (
                not rss.creator_id == interaction.user.id
                and not interaction.user.guild_permissions.manage_guild
            ):
                await interaction.response.send_message(
                    "You are not the creator of this RSS feed", ephemeral=True
                )
                return

            for follower in rss.followers:
                session.delete(follower)
            session.delete(rss)

        await interaction.response.send_message(f"Removed RSS feed `{name}`")

    @discord.app_commands.command(description="List all RSS feeds")
    async def list(self, interaction: discord.Interaction):
        """List all RSS feeds."""
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message(
                "This command must be used in a server.", ephemeral=True
            )
            return

        with Session.begin() as session:
            feeds = (
                session.execute(
                    sa.select(Nyaa).filter(Nyaa.guild_id == interaction.guild.id)
                )
                .scalars()
                .all()
            )

            if not feeds:
                await interaction.response.send_message("No RSS feeds found")
                return

            msg = "\n".join(f"**{feed.name}**: `{feed.match}`" for feed in feeds)

            await interaction.response.send_message(
                f"RSS feeds (**name**: `match`):\n{msg}"
            )

    @discord.app_commands.command(
        description="Get notifications when a new seed matching a regex is posted."
    )
    async def notifications(self, interaction: discord.Interaction):
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message(
                "This command must be used in a server."
            )
            return

        with Session(expire_on_commit=False) as db:
            mangas = db.query(Nyaa).filter(Nyaa.guild_id == interaction.guild.id).all()

            view = NyaaNotificationView(mangas, interaction.user.id)

        await interaction.response.send_message(
            f"Select the seeds you want to get notifications for. Page {view.page}/{view.last_page}",
            ephemeral=True,
            view=view,
        )

    async def post(
        self, nyaa: Nyaa, channel: discord.TextChannel, entry: feedparser.FeedParserDict
    ):
        embed = await generate_embed(entry, nyaa.name)
        role = discord.utils.get(channel.guild.roles, name="Nyaa Seed Updates")

        if role is None:
            role = await channel.guild.create_role(name="Nyaa Seed Updates")

        for member in role.members:
            assert self.bot.user is not None

            if member.id == self.bot.user.id:
                continue

            await member.remove_roles(role)

        for follower in nyaa.followers:
            member = channel.guild.get_member(follower.user_id)

            if member is None:
                continue

            await member.add_roles(role)

        await channel.send(
            f"{role.mention} New seed has been posted for {nyaa.name}", embed=embed
        )

    @tasks.loop(seconds=5)
    async def nyaa(self):
        await self.bot.wait_until_ready()

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
                guild = self.bot.get_guild(nyaa_match.guild_id)
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
                    await self.post(nyaa_match, channel, entry)

                if entry is not None:
                    nyaa_match.latest = cast(str, entry.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NyaaCog(bot))
