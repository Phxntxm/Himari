import argparse

from config import TOKEN
from src import bot

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")

    if parser.parse_args().test:
        bot._test_mode = True

    bot.run(TOKEN)
