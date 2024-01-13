from discord.ext import commands
from discord.flags import Intents

bot = commands.Bot(command_prefix="?", intents=Intents.all())
