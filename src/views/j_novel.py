from __future__ import annotations

import typing

import discord

from src import Session
from src.models.database import JNovel
from src.utils.j_novel import Series


class JNovelSelection(discord.ui.Select):
    def __init__(self, stories: list[Series], channel: discord.TextChannel):
        self._channel = channel
        self.stories = stories

        options = [
            discord.SelectOption(label=manga.title[:90], value=manga.id)
            for manga in stories
        ]

        super().__init__(
            placeholder="JNovel", min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message(
                "This command must be used in a server.", ephemeral=True
            )
            return

        _uuid = self.values[0]

        story = next(filter(lambda m: m.id == _uuid, self.stories), None)
        assert story is not None

        with Session.begin() as db:
            db_story = db.get(JNovel, story.id)

            if db_story is not None:
                await interaction.response.send_message(
                    "That story is already in the list.", ephemeral=True
                )
                return

            db.add(
                JNovel(
                    series=story.id,
                    title=story.title,
                    guild_id=interaction.guild.id,
                    channel_id=self._channel.id,
                    creator_id=interaction.user.id,
                )
            )

        await interaction.response.defer()

        # Always should but typing doesn't know that
        await interaction.followup.edit_message(
            typing.cast(discord.Message, interaction.message).id,
            content=f"Added {story.title} to the follow list.",
            view=None,
        )


class JNovelSearch(discord.ui.View):
    def __init__(
        self,
        stories: list[Series],
        owner_id: int,
        channel: discord.TextChannel,
    ):
        super().__init__()

        self._owner = owner_id
        self.add_item(JNovelSelection(stories, channel=channel))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self._owner:
            await interaction.response.send_message(
                "You cannot use this command.", ephemeral=True
            )
            return False

        return True
