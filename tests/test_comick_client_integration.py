import os

import aiohttp
import pytest

from services.comick_client import ComickClient


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_COMICK_INTEGRATION") != "1",
    reason="Set RUN_COMICK_INTEGRATION=1 to hit the real Comick proxy API.",
)


@pytest.mark.asyncio
async def test_comick_proxy_returns_search_data():
    async with aiohttp.ClientSession() as session:
        client = ComickClient(session=session)

        slug, top = await client.search_slug("Solo Leveling")

    assert slug
    assert isinstance(top, dict)
    assert top.get("slug") == slug


@pytest.mark.asyncio
async def test_comick_proxy_returns_latest_chapter_data():
    async with aiohttp.ClientSession() as session:
        client = ComickClient(session=session)

        latest = await client.get_latest_chapter("Solo Leveling", "solo-leveling")

    assert latest is not None
    assert latest["title"] == "Solo Leveling"
    assert latest["slug"]
    assert isinstance(latest["chapter"], float)
    assert latest["link"].startswith("https://comick.dev/comic/")
