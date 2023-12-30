from __future__ import annotations

import typing

import discord

from src import Session
from src.models.database import Manga, MangaFollower
from src.utils.mangadex import MangadexManga


class MangaSelection(discord.ui.Select):
    def __init__(self, mangas: list[MangadexManga], channel: discord.TextChannel):
        self._channel = channel
        self.mangas = mangas

        options = [
            discord.SelectOption(label=manga.title[:90], value=manga.id)
            for manga in mangas
        ]

        super().__init__(
            placeholder="Manga", min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message(
                "This command must be used in a server.", ephemeral=True
            )
            return

        _uuid = self.values[0]

        manga = next(filter(lambda m: m.id == _uuid, self.mangas), None)
        assert manga is not None

        with Session.begin() as db:
            db_manga = db.get(Manga, manga.id)

            if db_manga is not None:
                await interaction.response.send_message(
                    "That manga is already in the list.", ephemeral=True
                )
                return

            db.add(
                Manga(
                    title=manga.title,
                    description=manga.description,
                    mangadex_id=manga.id,
                    cover=manga.cover,
                    guild_id=interaction.guild.id,
                    channel_id=self._channel.id,
                )
            )

        await interaction.response.defer()

        # Always should but typing doesn't know that
        await interaction.followup.edit_message(
            typing.cast(discord.Message, interaction.message).id,
            content=f"Added {manga.title} to the manga list.",
            view=None,
        )


class MangaSearch(discord.ui.View):
    def __init__(
        self,
        mangas: list[MangadexManga],
        owner_id: int,
        channel: discord.TextChannel,
    ):
        super().__init__()

        self._owner = owner_id
        self.add_item(MangaSelection(mangas, channel=channel))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self._owner:
            await interaction.response.send_message(
                "You cannot use this command.", ephemeral=True
            )
            return False

        return True


def determine_followers(mangas: list[Manga], user_id: int) -> dict[Manga, bool]:
    followers = {}

    with Session.begin() as db:
        for manga in mangas:
            db_manga = db.get(Manga, manga.id)

            if db_manga is None:
                followers[manga] = False
                continue

            follower = next(
                filter(lambda f: f.user_id == user_id, db_manga.followers), None
            )

            if follower is None:
                followers[manga] = False
            else:
                followers[manga] = True

    return followers


class MangaNotification(discord.ui.Select):
    def __init__(self, mangas: list[Manga], user_id: int):
        _mangas = determine_followers(mangas, user_id)

        options = [
            discord.SelectOption(
                label=manga.title[:90],
                value=manga.id,
                default=follower,
            )
            for manga, follower in _mangas.items()
        ]

        self._selected_options = {option.value for option in options if option.default}
        self._owner = user_id

        super().__init__(
            placeholder="Manga",
            options=options,
            max_values=min(25, len(mangas)),
            min_values=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message(
                "This command must be used in a server.", ephemeral=True
            )
            return

        await interaction.response.defer()

        new_selected_options = set(self.values).difference(self._selected_options)
        unselected_options = self._selected_options.difference(self.values)

        with Session.begin() as db:
            for option in new_selected_options:
                manga = db.get(Manga, option)
                assert manga is not None

                manga.followers.append(MangaFollower(user_id=interaction.user.id))

                db.add(manga)

            for option in unselected_options:
                manga = db.get(Manga, option)
                assert manga is not None

                follower = next(
                    filter(lambda f: f.user_id == self._owner, manga.followers), None
                )
                assert follower is not None

                db.delete(follower)

        self._selected_options = set(self.values)


class MangaNotificationNext(discord.ui.Button):
    def __init__(self, view: MangaNotificationView):
        super().__init__(style=discord.ButtonStyle.primary, label="Next")

        self._manga_view = view

    async def callback(self, interaction: discord.Interaction):
        self._manga_view.next()

        await interaction.response.edit_message(
            view=self._manga_view,
            content="Select the manga you want to get notifications for. "
            f"Page {self._manga_view.page}/{self._manga_view.last_page}",
        )


class MangaNotificationPrevious(discord.ui.Button):
    def __init__(self, view: MangaNotificationView):
        super().__init__(style=discord.ButtonStyle.primary, label="Previous")

        self._manga_view = view

    async def callback(self, interaction: discord.Interaction):
        self._manga_view.previous()

        await interaction.response.edit_message(
            view=self._manga_view,
            content="Select the manga you want to get notifications for. "
            f"Page {self._manga_view.page}/{self._manga_view.last_page}",
        )


class MangaNotificationView(discord.ui.View):
    def __init__(self, mangas: list[Manga], owner_id: int, page: int = 1):
        super().__init__()

        self._page = page
        self._max = 25
        self._mangas = mangas
        self._owner = owner_id

        self.setup_items()

    @property
    def mangas(self) -> list[Manga]:
        return self._mangas[(self._page - 1) * self._max : self._page * self._max]

    @property
    def page(self) -> int:
        return self._page

    @property
    def last_page(self) -> int:
        return max(int(len(self._mangas) / self._max), 1)

    def next(self):
        self._page += 1

        # Make sure the page is valid
        if self._page > self.last_page:
            self._page = 1

        self.setup_items()

    def previous(self):
        self._page -= 1

        # Make sure the page is valid
        if self._page < 1:
            self._page = self.last_page

        self.setup_items()

    def setup_items(self):
        self.clear_items()

        self.add_item(MangaNotification(self.mangas, self._owner))

        if self._page != 1:
            self.add_item(MangaNotificationPrevious(self))
        if self._page != self.last_page:
            self.add_item(MangaNotificationNext(self))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self._owner:
            await interaction.response.send_message(
                "You cannot use this command.", ephemeral=True
            )
            return False

        return True
