import asyncio
from datetime import datetime, timedelta

import pytz
import sqlalchemy as sa

from src import Session, bot
from src.models.database import Daily
from src.views.daily import DailyView


def sleep_amount(timestamp: int) -> int:
    tz = pytz.timezone("America/New_York")
    now = datetime.now(tz=tz)
    dt = datetime.fromtimestamp(timestamp, tz=tz) + timedelta(days=1)
    sleep_time = int(dt.timestamp()) - int(now.timestamp())
    # Lets take off 5 minutes, just to be safe.
    sleep_time -= 300
    return sleep_time


async def handle_daily(
    id: int, timestamp: int, creator_id: int, handler: "DailyHandler"
):
    amt = sleep_amount(timestamp)
    amt = max(0, amt)

    await asyncio.sleep(amt)
    await bot.wait_until_ready()

    view = DailyView(creator_id, handler)
    user = bot.get_user(creator_id)

    if user is None:
        with Session.begin() as db:
            db.execute(sa.delete(Daily).where(Daily.id == id))
        return

    with Session.begin() as db:
        daily = db.get(Daily, id)

        if daily is not None:
            daily.timestamp = int(datetime.now().timestamp()) + 300
            db.add(daily)

        message = f"""Daily reminder! {daily.message if daily is not None else ""}

Press Done once you have completed your daily tasks, and are ready to be notified again in 24 hours.
If you wish to cancel your daily counter, press Cancel."""

    await user.send(message, view=view)
    handler.schedule()


class DailyHandler:
    _scheduled: dict[int, asyncio.Task[None]] = {}

    def schedule(self):
        loop = asyncio.get_event_loop()

        with Session.begin() as db:
            dailies = db.execute(sa.select(Daily)).scalars().all()
            user_ids = [daily.creator_id for daily in dailies]

            # Check if any have been deleted
            for user_id, task in self._scheduled.copy().items():
                # If it is one we want scheduled, skip here, we'll handle in the next loop
                if user_id in user_ids:
                    continue
                # Otherwise cancel and delete it
                task.cancel()
                del self._scheduled[user_id]

            for daily in dailies:
                task = self._scheduled.get(daily.creator_id)

                # If task is None, they haven't been scheduled yet
                #  otherwise if it's done, it's time to reschedule
                if task is None or task.done():
                    self._scheduled[daily.creator_id] = loop.create_task(
                        handle_daily(daily.id, daily.timestamp, daily.creator_id, self)
                    )

    def cancel(self):
        for task in self._scheduled.values():
            task.cancel()
        self._scheduled.clear()
