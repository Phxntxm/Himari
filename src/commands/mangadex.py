import discord

from src import Session, bot
from src.models.database import Manga
from src.utils.mangadex import search_manga
from src.views.mangadex import MangaNotificationView, MangaSearch

mangadex = discord.app_commands.Group(
    name="mangadex",
    description="Commands to handle following mangadex Manga.",
    guild_only=True,
)


@mangadex.command(
    name="follow", description="Add a manga to follow the latest chapters of."
)
@discord.app_commands.describe(
    manga="The manga you want to follow the latest chapters of.",
    channel="The channel to post the latest chapters in.",
)
async def follow(
    interaction: discord.Interaction, manga: str, channel: discord.TextChannel
):
    """
    Add a manga to follow the latest chapters of.
    """
    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    mangas = await search_manga(manga)

    if len(mangas) == 0:
        await interaction.response.send_message(
            "No manga found with that name.", ephemeral=True
        )
        return

    if len(mangas) == 1:
        _manga = mangas[0]

        with Session.begin() as db:
            db_manga = db.get(Manga, _manga.id)

            if db_manga is not None:
                await interaction.response.send_message(
                    "That manga is already in the list.", ephemeral=True
                )
                return

            db.add(
                Manga(
                    title=_manga.title,
                    description=_manga.description,
                    mangadex_id=_manga.id,
                    cover=_manga.cover,
                    guild_id=interaction.guild.id,
                    channel_id=channel.id,
                )
            )

        await interaction.response.send_message(
            f"Added {_manga.title} to the manga list.", ephemeral=True
        )

    else:
        view = MangaSearch(mangas, interaction.user.id, channel)

        await interaction.response.send_message(
            f"There are {len(mangas)} mangas matching that search term. Please select the one you want to follow.",
            ephemeral=True,
            view=view,
        )


# @mangadex.command(name="unfollow", description="Remove a manga from the list.")
# async def unfollow(interaction: discord.Interaction):
#     pass


@mangadex.command(
    name="notifications",
    description="Get notifications when a new chapter of a manga is released.",
)
async def notifications(interaction: discord.Interaction):
    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    with Session(expire_on_commit=False) as db:
        mangas = db.query(Manga).filter(Manga.guild_id == interaction.guild.id).all()

        view = MangaNotificationView(mangas, interaction.user.id)

    await interaction.response.send_message(
        f"Select the manga you want to get notifications for. Page {view.page}/{view.last_page}",
        ephemeral=True,
        view=view,
    )


bot.tree.add_command(mangadex)
