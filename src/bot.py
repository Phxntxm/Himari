from typing import Any

import discord
from discord.flags import Intents

TEST_GUILD = discord.Object(1174873140476780616)


class Bot(discord.Client):
    _test_mode = False

    def __init__(self, *, intents: Intents, **options: Any) -> None:
        super().__init__(intents=intents, **options)
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        if self._test_mode:
            self.tree.copy_global_to(guild=TEST_GUILD)

        await self.tree.sync()

        from src import tasks

        self._daily_handler = tasks.daily.DailyHandler()
        self._daily_handler.schedule()

        if self._test_mode:
            return

        tasks.nyaa.nyaa.start()
        tasks.mangadex.mangadex.start()
        tasks.j_novel.j_novel.start()


intents = Intents.default()
intents.members = True

bot = Bot(intents=intents)
