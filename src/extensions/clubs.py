import discord
import sqlalchemy as sa
from discord.ext import commands

from src import Session
from src.models.database import Club, ClubMember


@discord.app_commands.guild_only()
class ClubCog(commands.GroupCog, name="club", description="Commands to manage clubs."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(description="Create a club")
    @discord.app_commands.describe(name="The name of the club to create")
    async def create(self, interaction: discord.Interaction, name: str):
        """Create a club. Clubs are used to get mentions when threads related to the club are created."""
        name = name.lower()

        if interaction.guild is None or interaction.channel is None:
            return await interaction.response.send_message(
                "This command must be used in a server."
            )

        with Session.begin() as session:
            club = session.execute(
                sa.select(Club).filter(
                    Club.name == name, Club.guild_id == interaction.guild.id
                )
            ).scalar_one_or_none()

            if club:
                return await interaction.response.send_message(
                    f"Club {name} already exists"
                )

            club = Club(
                name=name, guild_id=interaction.guild.id, creator_id=interaction.user.id
            )
            session.add(club)

        await interaction.response.send_message(f"Created club `{name}`")

    @discord.app_commands.command(description="Delete a club")
    @discord.app_commands.describe(name="The name of the club to delete")
    async def delete(self, interaction: discord.Interaction, name: str):
        """Delete a club. This will remove all members from the club."""
        name = name.lower()

        if (
            interaction.guild is None
            or interaction.channel is None
            or not isinstance(interaction.user, discord.Member)
        ):
            return await interaction.response.send_message(
                "This command must be used in a server."
            )

        with Session.begin() as session:
            club = session.execute(
                sa.select(Club).filter(
                    Club.name == name, Club.guild_id == interaction.guild.id
                )
            ).scalar_one_or_none()

            if not club:
                return await interaction.response.send_message(
                    f"Club {name} does not exist"
                )

            if (
                club.creator_id != interaction.user.id
                and not interaction.user.guild_permissions.manage_guild
            ):
                return await interaction.response.send_message(
                    f"You are not the creator of the club {name}"
                )

            for member in club.members:
                session.delete(member)

            session.delete(club)

        await interaction.response.send_message(f"Deleted club {name}")

    @discord.app_commands.command(description="Join a club")
    @discord.app_commands.describe(name="The name of the club to join")
    async def join(self, interaction: discord.Interaction, name: str):
        """Join a club. You will get mentions when threads related to the club are created."""
        name = name.lower()

        if interaction.guild is None or interaction.channel is None:
            return await interaction.response.send_message(
                "This command must be used in a server."
            )

        with Session.begin() as session:
            club = session.execute(
                sa.select(Club).filter(
                    Club.name == name, Club.guild_id == interaction.guild.id
                )
            ).scalar_one_or_none()

            if not club:
                return await interaction.response.send_message(
                    f"Club {name} does not exist"
                )

            if interaction.user.id in [member.user_id for member in club.members]:
                return await interaction.response.send_message(
                    f"You are already in club {name}"
                )

            club.members.append(ClubMember(user_id=interaction.user.id))

        await interaction.response.send_message(f"Joined club {name}")

    @discord.app_commands.command(description="Leave a club")
    @discord.app_commands.describe(name="The name of the club to leave")
    async def leave(self, interaction: discord.Interaction, name: str):
        """Leave a club. You will no longer get mentions when threads related to the club are created."""
        name = name.lower()

        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message(
                "This command must be used in a server."
            )
            return

        with Session.begin() as session:
            club = session.execute(
                sa.select(Club).filter(
                    Club.name == name, Club.guild_id == interaction.guild.id
                )
            ).scalar_one_or_none()

            if not club:
                await interaction.response.send_message(f"Club {name} does not exist")
                return

            if interaction.user.id not in [member.user_id for member in club.members]:
                await interaction.response.send_message(f"You are not in club {name}")
                return

            session.execute(
                sa.delete(ClubMember).filter(
                    ClubMember.user_id == interaction.user.id,
                    ClubMember.club_id == club.id,
                )
            )

        await interaction.response.send_message(f"Left club {name}")

    @discord.app_commands.command(description="List all clubs")
    async def list(self, interaction: discord.Interaction):
        """List all clubs in the server."""
        if interaction.guild is None or interaction.channel is None:
            return await interaction.response.send_message(
                "This command must be used in a server."
            )

        with Session.begin() as session:
            clubs = (
                session.execute(
                    sa.select(Club).filter(Club.guild_id == interaction.guild.id)
                )
                .scalars()
                .all()
            )

            if not clubs:
                return await interaction.response.send_message("No clubs exist")

            await interaction.response.send_message(
                "\n".join(
                    f"{club.name} ({len(club.members)} members)" for club in clubs
                )
            )

    @discord.app_commands.command(description="Publish a thread to a club")
    @discord.app_commands.describe(name="The name of the club to publish to")
    async def publish(self, interaction: discord.Interaction, name: str):
        """Publish a thread to a club.
        This will add all the members of this club to this thread, which gives them a notification.
        """
        name = name.lower()

        if (
            interaction.guild is None
            or interaction.channel is None
            or not isinstance(interaction.channel, discord.Thread)
            or not isinstance(interaction.user, discord.Member)
        ):
            return await interaction.response.send_message(
                "This command must be used in a thread in a server."
            )

        with Session.begin() as session:
            club = session.execute(
                sa.select(Club).filter(
                    Club.name == name, Club.guild_id == interaction.guild.id
                )
            ).scalar_one_or_none()

            if not club:
                return await interaction.response.send_message(
                    f"Club {name} does not exist"
                )

            if (
                club.creator_id != interaction.user.id
                and not interaction.user.guild_permissions.manage_guild
            ):
                return await interaction.response.send_message(
                    f"You are not the creator of club {name}"
                )

            # First make sure the user isn't in there already
            members_in_channel = {member.id for member in interaction.channel.members}
            club_members = {member.user_id for member in club.members}

            # Uncomment if I figure out how to remove system messages, if they can be...
            # 403 Forbidden (error code: 50021): Cannot execute action on a system message
            # asyncio.create_task(delete_thread_system_message(interaction.channel))

            for member_id in club_members.difference(members_in_channel):
                await interaction.channel.add_user(discord.Object(member_id))

            await interaction.response.send_message(f"Added everyone from club {name}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ClubCog(bot))
