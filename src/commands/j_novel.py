import discord

from src import Session, bot
from src.models.database import JNovel
from src.utils.j_novel import search_series
from src.views.j_novel import JNovelSearch

jnovel = discord.app_commands.Group(
    name="jnovel",
    description="Commands to manage J-Novel Club RSS feed stuff.",
    guild_only=True,
)


@jnovel.command(description="Add a J-Novel series to follow and post to a channel.")
@discord.app_commands.describe(
    series="The series to follow.",
    channel="The channel to post to new chapters to.",
)
async def follow(
    interaction: discord.Interaction, series: str, channel: discord.TextChannel
):
    """
    Add a J-Novel series to follow and post to a channel.
    """
    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command must be used in a server."
        )
        return

    results = await search_series(series)

    if not results:
        return await interaction.response.send_message(
            "No results found.", ephemeral=True
        )

    if len(results) == 1:
        result = results[0]

        with Session.begin() as db:
            db_series = db.get(JNovel, result.id)

            if db_series is not None:
                return await interaction.response.send_message(
                    "That series is already in the follow list.", ephemeral=True
                )

            db.add(
                JNovel(
                    series=result.id,
                    title=result.title,
                    guild_id=interaction.guild.id,
                    channel_id=channel.id,
                    creator_id=interaction.user.id,
                )
            )

            await interaction.response.send_message(
                f"Added {result.title} to the follow list.", ephemeral=True
            )
    else:
        view = JNovelSearch(results, interaction.user.id, channel)

        await interaction.response.send_message(
            "Select the series you want to follow.", view=view, ephemeral=True
        )


bot.tree.add_command(jnovel)
