from dataclasses import dataclass

import aiohttp

from src.utils import search

BASE_URL = "https://labs.j-novel.club"


@dataclass
class Series:
    id: str
    title: str
    description: str
    cover: str


async def _get_series(session: aiohttp.ClientSession, *, page=0) -> dict | None:
    limit = 100

    async with session.get(
        f"{BASE_URL}/app/v1/series",
        params={"format": "json", "skip": page * limit, "limit": limit},
    ) as resp:
        if resp.status > 299:
            return

        return await resp.json()


async def get_all_series() -> list[Series] | None:
    results: list[Series] = []

    async with aiohttp.ClientSession() as session:
        page = 0

        while True:
            data = await _get_series(session, page=page)

            if data is None:
                return

            for series in data["series"]:
                results.append(
                    Series(
                        id=series["legacyId"],
                        title=series["title"],
                        description=series["description"],
                        cover=series["cover"]["coverUrl"],
                    )
                )

            if data["pagination"]["lastPage"]:
                return results

            page += 1


async def search_series(query: str) -> list[Series]:
    series = await get_all_series()
    assert series is not None

    return [s for s in series if search(s.title, query)]
