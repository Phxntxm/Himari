import discord
import sqlalchemy as sa

from src import Session, bot
from src.models.database import Daily

daily = discord.app_commands.Group(
    name="daily",
    description="Commands to manage daily reminders.",
)


@daily.command(
    description="Add a daily counter, which will ping you every 24 hours, starting from when this command is ran."
)
async def create(interaction: discord.Interaction):
    """
    Add a daily counter, which will ping you every 24 hours, starting from when this command is ran.
    """
    with Session.begin() as db:
        daily = db.execute(
            sa.select(Daily).where(Daily.creator_id == interaction.user.id)
        ).scalar()

        if daily is not None:
            return await interaction.response.send_message(
                "You already have a daily counter setup, you can only have one per person.",
                ephemeral=True,
            )

        timestamp = interaction.created_at.timestamp()

        daily = Daily(
            creator_id=interaction.user.id,
            timestamp=int(timestamp),
        )

        db.add(daily)

    await interaction.response.send_message(f"Daily counter added.", ephemeral=True)

    bot._daily_handler.schedule()


@daily.command(description="Remove your daily counter.")
async def delete(interaction: discord.Interaction):
    """
    Remove your daily counter.
    """
    with Session.begin() as db:
        daily = db.execute(
            sa.select(Daily).where(Daily.creator_id == interaction.user.id)
        ).scalar()

        if daily is None:
            return await interaction.response.send_message(
                "You do not have a daily counter setup.", ephemeral=True
            )

        db.delete(daily)

    await interaction.response.send_message(f"Daily counter removed.", ephemeral=True)

    bot._daily_handler.schedule()


bot.tree.add_command(daily)
