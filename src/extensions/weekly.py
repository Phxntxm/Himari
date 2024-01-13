import random
import string
from datetime import datetime, timedelta

import discord
import pytz
import sqlalchemy as sa
from discord.ext import commands

from src import Session
from src.models.database import Failure, Success, Weekly


def get_next_timestamp(timestamp: int) -> tuple[int, bool]:
    tz = pytz.timezone("America/New_York")
    dt = datetime.fromtimestamp(timestamp, tz=tz)
    now = datetime.now(tz=tz)

    def _get_next_dt() -> datetime:
        """Get the next datetime for the countdown."""
        next_dt = now.replace(hour=dt.hour, minute=dt.minute, second=0)
        # Add a single day just in case this is the same day
        next_dt += timedelta(days=1)

        # Add a day until it's the weekday we want
        while next_dt.weekday() != dt.weekday():
            next_dt += timedelta(days=1)

        # Another replace, in case we've swapped into/out of DST
        return next_dt.replace(hour=dt.hour, minute=dt.minute, second=0)

    # If it's on the day, then we show the success gif no matter what
    if now.weekday() == dt.weekday():
        on_day = True

        # Lets do within 3 hours
        if now.hour > dt.hour + 3:
            next_dt = _get_next_dt()
        # If it's within the three hours, then we want to show the time today
        else:
            next_dt = now.replace(hour=dt.hour, minute=dt.minute, second=0)
    # Otherwise, add a day for each day until the day of the week, then set the time
    else:
        on_day = False

        next_dt = _get_next_dt()

    return int(next_dt.timestamp()), on_day


weekly = discord.app_commands.Group(
    name="weekly", guild_only=True, description="Handles weekly countdowns."
)


@weekly.command(description="Create a weekly countdown.")
@discord.app_commands.describe(
    lookup="The lookup that will be provided to get this weekly countdown.",
    timestamp="The timestamp to count down to. (use /timestamp to get a website to get this)",
)
async def create(interaction: discord.Interaction, lookup: str, timestamp: int) -> None:
    lookup = lookup.lower()

    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    # First make sure there's not a countdown with the same lookup
    with Session.begin() as session:
        countdowns = (
            session.execute(
                sa.select(Weekly).filter(
                    Weekly.guild_id == interaction.guild.id,
                    Weekly.lookup == lookup,
                )
            )
            .scalars()
            .all()
        )

        if len(countdowns) > 0:
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` already exists."
            )
            return

        countdown = Weekly(
            guild_id=interaction.guild.id,
            lookup=lookup,
            timestamp=timestamp,
            user_id=interaction.user.id,
        )
        session.add(countdown)

    await interaction.response.send_message(
        f"Weekly created. Lookup: `{lookup}`, Timestamp: <t:{timestamp}>"
    )


@weekly.command(description="Delete a weekly countdown.")
@discord.app_commands.describe(
    lookup="The lookup for the weekly countdown.",
)
async def delete(interaction: discord.Interaction, lookup: str) -> None:
    lookup = lookup.lower()

    if (
        interaction.guild is None
        or interaction.channel is None
        or isinstance(interaction.user, discord.User)
    ):
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    with Session.begin() as session:
        countdown = session.execute(
            sa.select(Weekly).filter(
                Weekly.guild_id == interaction.guild.id,
                Weekly.lookup == lookup,
            )
        ).scalar_one_or_none()

        if countdown is None:
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` does not exist."
            )
            return

        if (
            countdown.user_id != interaction.user.id
            and not interaction.user.guild_permissions.manage_guild
        ):
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` is not owned by you."
            )
            return

        session.delete(countdown)

    await interaction.response.send_message(f"Weekly countdown {lookup} deleted.")


@weekly.command(description="Get a weekly countdown.")
@discord.app_commands.describe(
    lookup="The lookup for the weekly countdown.",
)
async def lookup(interaction: discord.Interaction, lookup: str) -> None:
    lookup = lookup.lower()

    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    with Session.begin() as session:
        countdown = session.execute(
            sa.select(Weekly).filter(
                Weekly.guild_id == interaction.guild.id,
                Weekly.lookup == lookup,
            )
        ).scalar_one_or_none()

        if countdown is None:
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` does not exist, or no gifs have been added to it."
            )
            return

        timestamp, on_day = get_next_timestamp(countdown.timestamp)

        embed = discord.Embed(
            title=f"Weekly to {lookup.title()}",
            description=f"Next {lookup.title()} <t:{timestamp}:R> on <t:{timestamp}>",
            color=discord.Color.green() if on_day else discord.Color.red(),
        )

        choices = countdown.success_gifs if on_day else countdown.failure_gifs

        if choices:
            embed.set_image(url=random.choice(choices).url)

    await interaction.response.send_message(embed=embed)


success = discord.app_commands.Group(
    name="success",
    guild_only=True,
    description="Handles success gifs for a weekly countdown.",
    parent=weekly,
)

failure = discord.app_commands.Group(
    name="failure",
    guild_only=True,
    description="Handles failure gifs for a weekly countdown.",
    parent=weekly,
)


@success.command(description="Add a success gif to a countdown.", name="add")
@discord.app_commands.describe(
    lookup="The lookup for the weekly countdown.",
    url="The URL of the success gif.",
)
async def addsuccess(interaction: discord.Interaction, lookup: str, url: str) -> None:
    lookup = lookup.lower()

    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    with Session.begin() as session:
        countdown = session.execute(
            sa.select(Weekly).filter(
                Weekly.guild_id == interaction.guild.id,
                Weekly.lookup == lookup,
            )
        ).scalar_one_or_none()

        if countdown is None:
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` does not exist."
            )
            return

        if countdown.user_id != interaction.user.id:
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` is not owned by you."
            )
            return

        if [gif for gif in countdown.success_gifs if gif.url == url]:
            await interaction.response.send_message(
                f"Success gif with URL `{url}` already exists."
            )
            return

        success = Success(url=url, weekly_id=countdown.id)
        session.add(success)

    await interaction.response.send_message(
        f"Success gif added to countdown `{lookup}`."
    )


@failure.command(description="Add a failure gif to a countdown.", name="add")
@discord.app_commands.describe(
    lookup="The lookup for the weekly countdown.",
    url="The URL of the failure gif.",
)
async def addfailure(interaction: discord.Interaction, lookup: str, url: str) -> None:
    lookup = lookup.lower()

    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    with Session.begin() as session:
        countdown = session.execute(
            sa.select(Weekly).filter(
                Weekly.guild_id == interaction.guild.id,
                Weekly.lookup == lookup,
            )
        ).scalar_one_or_none()

        if countdown is None:
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` does not exist."
            )
            return

        if countdown.user_id != interaction.user.id:
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` is not owned by you."
            )
            return

        if [gif for gif in countdown.failure_gifs if gif.url == url]:
            await interaction.response.send_message(
                f"Failure gif with URL `{url}` already exists."
            )
            return

        failure = Failure(url=url, weekly_id=countdown.id)
        session.add(failure)

    await interaction.response.send_message(
        f"Failure gif added to countdown `{lookup}`."
    )


@success.command(description="List success gifs for a countdown.", name="list")
@discord.app_commands.describe(
    lookup="The lookup for the weekly countdown.",
)
async def successlist(interaction: discord.Interaction, lookup: str) -> None:
    lookup = lookup.lower()

    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    with Session.begin() as session:
        countdown = session.execute(
            sa.select(Weekly).filter(
                Weekly.guild_id == interaction.guild.id,
                Weekly.lookup == lookup,
            )
        ).scalar_one_or_none()

        if countdown is None:
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` does not exist."
            )
            return

        if len(countdown.success_gifs) == 0:
            await interaction.response.send_message(
                f"No success gifs for countdown `{lookup}`."
            )
            return

        gifs = [f"<{gif.url}>" for gif in countdown.success_gifs]
        gifs_fmt = "\n".join(gifs)

    await interaction.response.send_message(f"Success gifs:\n{gifs_fmt}")


@failure.command(description="List failure gifs for a countdown.", name="list")
@discord.app_commands.describe(
    lookup="The lookup for the weekly countdown.",
)
async def failurelist(interaction: discord.Interaction, lookup: str) -> None:
    lookup = lookup.lower()

    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    with Session.begin() as session:
        countdown = session.execute(
            sa.select(Weekly).filter(
                Weekly.guild_id == interaction.guild.id,
                Weekly.lookup == lookup,
            )
        ).scalar_one_or_none()

        if countdown is None:
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` does not exist."
            )
            return

        if len(countdown.failure_gifs) == 0:
            await interaction.response.send_message(
                f"No failure gifs for countdown `{lookup}`."
            )
            return

        gifs = [f"<{gif.url}>" for gif in countdown.failure_gifs]
        gifs_fmt = "\n".join(gifs)

    await interaction.response.send_message(f"Failure gifs:\n{gifs_fmt}")


@success.command(description="Remove a success gif from a countdown.", name="remove")
@discord.app_commands.describe(
    lookup="The lookup for the weekly countdown.",
    url="The URL of the success gif.",
)
async def removesuccess(
    interaction: discord.Interaction, lookup: str, url: str
) -> None:
    lookup = lookup.lower()

    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    with Session.begin() as session:
        countdown = session.execute(
            sa.select(Weekly).filter(
                Weekly.guild_id == interaction.guild.id,
                Weekly.lookup == lookup,
            )
        ).scalar_one_or_none()

        if countdown is None:
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` does not exist."
            )
            return

        if countdown.user_id != interaction.user.id:
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` is not owned by you."
            )
            return

        gif = next((gif for gif in countdown.success_gifs if gif.url == url), None)

        if gif is None:
            await interaction.response.send_message(
                f"Success gif with URL `{url}` does not exist."
            )
            return

        session.delete(gif)

    await interaction.response.send_message(
        f"Success gif removed from countdown `{lookup}`."
    )


@failure.command(description="Remove a failure gif from a countdown.", name="remove")
@discord.app_commands.describe(
    lookup="The lookup for the weekly countdown.",
    url="The URL of the failure gif.",
)
async def removefailure(
    interaction: discord.Interaction, lookup: str, url: str
) -> None:
    lookup = lookup.lower()

    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    with Session.begin() as session:
        countdown = session.execute(
            sa.select(Weekly).filter(
                Weekly.guild_id == interaction.guild.id,
                Weekly.lookup == lookup,
            )
        ).scalar_one_or_none()

        if countdown is None:
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` does not exist."
            )
            return

        if countdown.user_id != interaction.user.id:
            await interaction.response.send_message(
                f"Weekly with lookup `{lookup}` is not owned by you."
            )
            return

        gif = next((gif for gif in countdown.failure_gifs if gif.url == url), None)

        if gif is None:
            await interaction.response.send_message(
                f"Failure gif with URL `{url}` does not exist."
            )
            return

        session.delete(gif)

    await interaction.response.send_message(
        f"Failure gif removed from countdown `{lookup}`."
    )


@weekly.command(description="List all the countdowns for this server.", name="list")
async def weeklylist(interaction: discord.Interaction) -> None:
    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    with Session.begin() as session:
        countdowns = (
            session.execute(
                sa.select(Weekly).filter(
                    Weekly.guild_id == interaction.guild.id,
                )
            )
            .scalars()
            .all()
        )

        if len(countdowns) == 0:
            await interaction.response.send_message("No countdowns for this server.")
            return

        description = ""

        for i, countdown in enumerate(
            sorted(countdowns, key=lambda c: get_next_timestamp(c.timestamp)[0])
        ):
            timestamp = get_next_timestamp(countdown.timestamp)[0]

            description += f"{i+1}) {string.capwords(countdown.lookup)} - <t:{timestamp}:R> on <t:{timestamp}>\n"

        embed = discord.Embed(
            title="Weekly Countdowns",
            description=description,
            color=discord.Color.green(),
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    bot.tree.add_command(weekly)
