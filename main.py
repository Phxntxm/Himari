import asyncio
import pathlib

from discord import utils

from config import TOKEN
from src import bot


async def main():
    extensions = pathlib.Path("src/extensions").glob("*.py")

    for extension in extensions:
        await bot.load_extension(f"src.extensions.{extension.stem}")

    utils.setup_logging()
    await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
