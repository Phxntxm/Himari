from dataclasses import dataclass

import aiohttp

BASE_URL = "https://api.mangadex.org"


@dataclass
class MangadexManga:
    id: str
    title: str
    description: str | None
    cover: str | None


@dataclass
class Chapter:
    id: str
    title: str
    volume: int | None
    chapter: int


async def search_manga(search: str) -> list[MangadexManga]:
    """
    Search for manga on MangaDex.
    """
    async with aiohttp.ClientSession() as session:
        res = await session.get(
            f"{BASE_URL}/manga",
            params={
                "title": search,
                "contentRating[]": ["safe", "suggestive", "erotica", "pornographic"],
                "includes[]": ["cover_art"],
            },
        )

        data = await res.json()

    mangas = []

    for manga in data["data"]:
        cover = None

        for relation in manga["relationships"]:
            if relation["type"] == "cover_art":
                cover = relation["attributes"]["fileName"]
                break

        attrs = manga["attributes"]
        title = attrs["title"].get("en") or next(iter(attrs["title"].values()))
        description = attrs["description"].get("en") or next(iter(attrs["description"].values()), None)

        mangas.append(
            MangadexManga(
                id=manga["id"],
                description=description,
                title=title,
                cover=cover,
            )
        )

    return mangas


async def latest_chapter(id: str) -> Chapter | None:
    """
    Get the chapters of a manga.
    """
    async with aiohttp.ClientSession() as session:
        res = await session.get(
            f"{BASE_URL}/manga/{id}/feed",
            params={
                "translatedLanguage[]": "en",
                "order[volume]": "desc",
                "order[chapter]": "desc",
                "order[publishAt]": "desc",
            },
        )

        data = await res.json()

    for chapter in data["data"]:
        if chapter["type"] == "chapter" and chapter["attributes"]["translatedLanguage"] == "en":
            return Chapter(
                id=chapter["id"],
                title=chapter["attributes"]["title"],
                volume=chapter["attributes"]["volume"],
                chapter=chapter["attributes"]["chapter"],
            )
