from __future__ import annotations

import discord

from src import Session
from src.models.database import Nyaa, NyaaFollower


def determine_followers(seeds: list[Nyaa], user_id: int) -> dict[Nyaa, bool]:
    followers = {}

    with Session.begin() as db:
        for seed in seeds:
            nyaa = db.get(Nyaa, seed.id)

            if nyaa is None:
                followers[seed] = False
                continue

            follower = next(
                filter(lambda f: f.user_id == user_id, nyaa.followers), None
            )

            if follower is None:
                followers[seed] = False
            else:
                followers[seed] = True

    return followers


class NyaaNotification(discord.ui.Select):
    def __init__(self, seeds: list[Nyaa], user_id: int):
        follower_map = determine_followers(seeds, user_id)

        options = [
            discord.SelectOption(
                label=manga.name[:90].title(),
                value=str(manga.id),
                default=follower,
            )
            for manga, follower in follower_map.items()
        ]

        self._selected_options = {option.value for option in options if option.default}
        self._owner = user_id

        super().__init__(
            placeholder="Nyaa",
            options=options,
            max_values=min(25, len(seeds)),
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
                seed = db.get(Nyaa, option)
                assert seed is not None

                seed.followers.append(NyaaFollower(user_id=interaction.user.id))

                db.add(seed)

            for option in unselected_options:
                seed = db.get(Nyaa, option)
                assert seed is not None

                follower = next(
                    filter(lambda f: f.user_id == self._owner, seed.followers), None
                )
                assert follower is not None

                db.delete(follower)

        self._selected_options = set(self.values)


class NyaaNotificationNext(discord.ui.Button):
    def __init__(self, view: NyaaNotificationView):
        super().__init__(style=discord.ButtonStyle.primary, label="Next")

        self._nyaa_view = view

    async def callback(self, interaction: discord.Interaction):
        self._nyaa_view.next()

        await interaction.response.edit_message(
            view=self._nyaa_view,
            content="Select the seeds you want to get notifications for. "
            f"Page {self._nyaa_view.page}/{self._nyaa_view.last_page}",
        )


class NyaaNotificationPrevious(discord.ui.Button):
    def __init__(self, view: NyaaNotificationView):
        super().__init__(style=discord.ButtonStyle.primary, label="Previous")

        self._nyaa_view = view

    async def callback(self, interaction: discord.Interaction):
        self._nyaa_view.previous()

        await interaction.response.edit_message(
            view=self._nyaa_view,
            content="Select the seeds you want to get notifications for. "
            f"Page {self._nyaa_view.page}/{self._nyaa_view.last_page}",
        )


class NyaaNotificationView(discord.ui.View):
    def __init__(self, seeds: list[Nyaa], owner_id: int, page: int = 1):
        super().__init__()

        self._page = page
        self._max = 25
        self._seeds = seeds
        self._owner = owner_id

        self.setup_items()

    @property
    def seeds(self) -> list[Nyaa]:
        return self._seeds[(self._page - 1) * self._max : self._page * self._max]

    @property
    def page(self) -> int:
        return self._page

    @property
    def last_page(self) -> int:
        return max(int(len(self._seeds) / self._max), 1)

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

        self.add_item(NyaaNotification(self.seeds, self._owner))

        if self._page != 1:
            self.add_item(NyaaNotificationPrevious(self))
        if self._page != self.last_page:
            self.add_item(NyaaNotificationNext(self))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self._owner:
            await interaction.response.send_message(
                "You cannot use this command.", ephemeral=True
            )
            return False

        return True
