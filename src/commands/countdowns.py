import random
import string

import discord
import sqlalchemy as sa

from src import Session, bot
from src.models.database import Countdown, CountdownImage

countdowns = discord.app_commands.Group(
    name="countdown",
    description="Commands to manage guild wide countdowns.",
    guild_only=True,
)


@countdowns.command(description="Add a countdown to the server.")
@discord.app_commands.describe(
    name="The name of the countdown.",
    timestamp="The date and time of the countdown.",
)
async def add(interaction: discord.Interaction, name: str, timestamp: int):
    """
    Add a countdown to the server.
    """
    name = name.lower()

    if interaction.guild is None or interaction.channel is None:
        return await interaction.response.send_message(
            "This command must be used in a server."
        )

    with Session.begin() as db:
        countdown = db.execute(
            sa.select(Countdown).where(
                Countdown.lookup == name, Countdown.guild_id == interaction.guild.id
            )
        ).scalar()

        if countdown is not None:
            return await interaction.response.send_message(
                "There is already a countdown with that name.", ephemeral=True
            )

        countdown = Countdown(
            guild_id=interaction.guild.id,
            creator_id=interaction.user.id,
            timestamp=timestamp,
            lookup=name,
        )

        db.add(countdown)

    await interaction.response.send_message(
        f"Countdown `{name}` added.", ephemeral=True
    )


@countdowns.command(description="Remove a countdown from the server.")
@discord.app_commands.describe(
    name="The name of the countdown.",
)
async def remove(interaction: discord.Interaction, name: str):
    """
    Remove a countdown from the server.
    """
    name = name.lower()

    if (
        interaction.guild is None
        or interaction.channel is None
        or isinstance(interaction.user, discord.User)
    ):
        return await interaction.response.send_message(
            "This command must be used in a server."
        )

    with Session.begin() as db:
        countdown = db.execute(
            sa.select(Countdown).where(
                Countdown.lookup == name, Countdown.guild_id == interaction.guild.id
            )
        ).scalar()

        if countdown is None:
            return await interaction.response.send_message(
                "There is no countdown with that name.", ephemeral=True
            )

        if (
            countdown.creator_id != interaction.user.id
            and not interaction.user.guild_permissions.manage_guild
        ):
            return await interaction.response.send_message(
                "You are not the creator of that countdown.", ephemeral=True
            )

        db.delete(countdown)

    await interaction.response.send_message(
        f"Countdown `{name}` removed.", ephemeral=True
    )


@countdowns.command(description="Post a particular countdown.")
@discord.app_commands.describe(
    name="The name of the countdown.",
)
async def lookup(interaction: discord.Interaction, name: str):
    """
    Post a particular countdown.
    """
    name = name.lower()

    if interaction.guild is None or interaction.channel is None:
        return await interaction.response.send_message(
            "This command must be used in a server."
        )

    with Session.begin() as db:
        countdown = db.execute(
            sa.select(Countdown).where(
                Countdown.lookup == name, Countdown.guild_id == interaction.guild.id
            )
        ).scalar_one_or_none()

        if countdown is None:
            return await interaction.response.send_message(
                f"There is no countdown with the name {name}.", ephemeral=True
            )

        embed = discord.Embed(
            title=string.capwords(name),
            description=f"Countdown ends <t:{countdown.timestamp}:R> on <t:{countdown.timestamp}>",
            color=discord.Color.green(),
        )

        if countdown.images:
            embed.set_image(url=random.choice(countdown.images).url)

        await interaction.response.send_message(embed=embed)


@countdowns.command(description="List all countdowns.")
async def list(interaction: discord.Interaction):
    """
    List all countdowns.
    """
    if interaction.guild is None or interaction.channel is None:
        return await interaction.response.send_message(
            "This command must be used in a server."
        )

    with Session.begin() as db:
        countdowns = (
            db.execute(
                sa.select(Countdown).where(Countdown.guild_id == interaction.guild.id)
            )
            .scalars()
            .all()
        )

        if not countdowns:
            return await interaction.response.send_message(
                "There are no countdowns for this server.", ephemeral=True
            )

        embed = discord.Embed(
            title="Countdowns",
            description="\n".join(
                [
                    f"{i + 1}) {string.capwords(countdown.lookup)} - <t:{countdown.timestamp}:R> on <t:{countdown.timestamp}>"
                    for i, countdown in enumerate(
                        sorted(countdowns, key=lambda c: c.timestamp)
                    )
                ]
            ),
            color=discord.Color.green(),
        )

        await interaction.response.send_message(embed=embed)


images = discord.app_commands.Group(
    name="images",
    description="Commands to manage countdown images.",
    guild_only=True,
    parent=countdowns,
)


@images.command(name="add", description="Add an image to a countdown.")
@discord.app_commands.describe(
    name="The name of the countdown.",
    url="The URL of the image to add.",
)
async def image_add(interaction: discord.Interaction, name: str, url: str):
    """
    Add an image to a countdown.
    """
    name = name.lower()

    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    with Session.begin() as db:
        countdown = db.execute(
            sa.select(Countdown).where(
                Countdown.lookup == name, Countdown.guild_id == interaction.guild.id
            )
        ).scalar()

        if countdown is None:
            return await interaction.response.send_message(
                "There is no countdown with that name.", ephemeral=True
            )

        if countdown.creator_id != interaction.user.id:
            return await interaction.response.send_message(
                "You are not the creator of that countdown.", ephemeral=True
            )

        image = db.execute(
            sa.select(CountdownImage).where(
                CountdownImage.url == url, CountdownImage.countdown_id == countdown.id
            )
        ).scalar()

        if image is not None:
            return await interaction.response.send_message(
                "There is already an image with that URL for that countdown.",
                ephemeral=True,
            )

        countdown.images.append(CountdownImage(url=url))

    await interaction.response.send_message(
        f"Image {url} added to countdown `{name}`.", ephemeral=True
    )


@images.command(name="remove", description="Remove an image from a countdown.")
@discord.app_commands.describe(
    name="The name of the countdown.",
    url="The URL of the image to remove.",
)
async def image_remove(interaction: discord.Interaction, name: str, url: str):
    """
    Remove an image from a countdown.
    """
    name = name.lower()

    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    with Session.begin() as db:
        countdown = db.execute(
            sa.select(Countdown).where(
                Countdown.lookup == name, Countdown.guild_id == interaction.guild.id
            )
        ).scalar()

        if countdown is None:
            return await interaction.response.send_message(
                "There is no countdown with that name.", ephemeral=True
            )

        if countdown.creator_id != interaction.user.id:
            return await interaction.response.send_message(
                "You are not the creator of that countdown.", ephemeral=True
            )

        image = db.execute(
            sa.select(CountdownImage).where(
                CountdownImage.url == url, CountdownImage.countdown_id == countdown.id
            )
        ).scalar()

        if image is None:
            return await interaction.response.send_message(
                "There is no image with that URL for that countdown.",
                ephemeral=True,
            )

        db.delete(image)

    await interaction.response.send_message(
        f"Image {url} removed from countdown `{name}`.", ephemeral=True
    )


bot.tree.add_command(countdowns)
