from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast

import discord
import sqlalchemy as sa

from src import Session
from src.models.database import Daily

if TYPE_CHECKING:
    from src.utils.daily import DailyHandler


class DailyDone(discord.ui.Button):
    def __init__(self, user_id: int, handler: DailyHandler):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="Done",
            custom_id=f"daily:green:{user_id}",
        )
        self.handler = handler

    async def callback(self, interaction: discord.Interaction):
        with Session.begin() as db:
            daily = db.execute(
                sa.select(Daily).where(Daily.creator_id == interaction.user.id)
            ).scalar()

            if daily is None:
                return await interaction.response.send_message(
                    content="You do not have a daily counter setup."
                )

            daily.timestamp = int(datetime.utcnow().timestamp())
            db.add(daily)

        await interaction.response.send_message(
            content="You will receive another daily reminder in 24 hours"
        )

        cast(DailyView, self.view).stop()
        self.handler.schedule()


class DailyCancel(discord.ui.Button):
    def __init__(self, user_id: int, handler: DailyHandler):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Cancel",
            custom_id=f"daily:red:{user_id}",
        )
        self.handler = handler

    async def callback(self, interaction: discord.Interaction):
        with Session.begin() as db:
            db.execute(sa.delete(Daily).where(Daily.creator_id == interaction.user.id))

        await interaction.response.send_message(
            content="Daily counter has been cancelled."
        )

        cast(DailyView, self.view).stop()
        self.handler.schedule()


class DailyView(discord.ui.View):
    def __init__(self, user_id: int, handler: DailyHandler):
        super().__init__(timeout=None)
        self.add_item(DailyDone(user_id, handler=handler))
        self.add_item(DailyCancel(user_id, handler=handler))
