import discord
import sqlalchemy as sa

from src import Session, bot
from src.models.database import Nyaa

nyaa = discord.app_commands.Group(
    name="nyaa",
    description="Commands to handle parsing Nyaa.si RSS feed",
    guild_only=True,
)


@nyaa.command(
    description="Add a new Nyaa RSS feed match to the database", name="follow"
)
@discord.app_commands.describe(
    name="The name of the RSS feed (used for identifying the feed)",
    match="The value to match the RSS feed title against (use what you would search on Nyaa.si)",
    channel="The channel to send new RSS feed entries to",
)
async def follow(
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


@nyaa.command(description="Remove an RSS feed from the database", name="unfollow")
@discord.app_commands.describe(
    name="The name of the RSS feed",
)
async def unfollow(interaction: discord.Interaction, name: str):
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

        session.delete(rss)

    await interaction.response.send_message(f"Removed RSS feed `{name}`")


bot.tree.add_command(nyaa)
