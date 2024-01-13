import discord
import sqlalchemy as sa
from discord.ext import commands

from src import Session
from src.models.database import Daily
from src.utils.daily import DailyHandler


class DailyCog(commands.GroupCog, name="daily"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._daily_handler = DailyHandler()

    async def cog_load(self) -> None:
        self._daily_handler = DailyHandler()
        self._daily_handler.schedule()

    async def cog_unload(self) -> None:
        self._daily_handler.cancel()

    @discord.app_commands.command(
        description="Add a daily counter, which will ping you every 24 hours, starting from when this command is ran."
    )
    async def create(
        self, interaction: discord.Interaction, message: str | None = None
    ):
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
                message=message,
            )

            db.add(daily)

        await interaction.response.send_message("Daily counter added.", ephemeral=True)

        self._daily_handler.schedule()

    @discord.app_commands.command(description="Remove your daily counter.")
    async def delete(self, interaction: discord.Interaction):
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

        await interaction.response.send_message(
            "Daily counter removed.", ephemeral=True
        )

        self._daily_handler.schedule()


async def setup(bot: commands.Bot):
    await bot.add_cog(DailyCog(bot))
