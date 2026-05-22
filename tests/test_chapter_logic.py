import pytest

from cogs.Tracking import AddManhwaComick


@pytest.fixture
def cog():
    return AddManhwaComick(bot=None)


@pytest.mark.parametrize("chapter, expected", [
    (10.0, "10"),
    (10.5, "10.5"),
    (0.0, "0"),
    (999.0, "999"),
    ("12", "12"),
    ("12.5", "12.5"),
])
def test_format_chapter_number(chapter, expected):
    assert AddManhwaComick.format_chapter_number(chapter) == expected


def test_format_chapter_number_handles_none_without_crashing():
    assert AddManhwaComick.format_chapter_number(None) == "None"


@pytest.mark.asyncio
async def test_search_slug_returns_top_result(cog, monkeypatch):
    async def fake_fetch_json(url, params=None):
        assert params == {"q": "Solo Leveling", "tachiyomi": "true"}
        return [{"slug": "solo-leveling", "title": "Solo Leveling"}]

    monkeypatch.setattr(cog, "fetch_json", fake_fetch_json)

    slug, top = await cog.search_slug("Solo Leveling")

    assert slug == "solo-leveling"
    assert top == {"slug": "solo-leveling", "title": "Solo Leveling"}


@pytest.mark.asyncio
async def test_search_slug_returns_none_when_no_results(cog, monkeypatch):
    async def fake_fetch_json(url, params=None):
        return []

    monkeypatch.setattr(cog, "fetch_json", fake_fetch_json)

    slug, top = await cog.search_slug("Missing Manhwa")

    assert slug is None
    assert top is None


@pytest.mark.asyncio
async def test_get_latest_chapter_returns_chapter_info(cog, monkeypatch):
    responses = [
        {"comic": {"hid": "comic-hid", "cover_url": "cover.png"}},
        {"chapters": [{"chap": "15", "title": "The Fight", "hid": "chapter-hid"}]},
    ]

    async def fake_fetch_json(url, params=None):
        return responses.pop(0)

    monkeypatch.setattr(cog, "fetch_json", fake_fetch_json)

    result = await cog.get_latest_chapter("Test Manhwa", "test-slug")

    assert result == {
        "title": "Test Manhwa",
        "slug": "test-slug",
        "chapter": 15.0,
        "chapter_title": "The Fight",
        "link": "https://comick.dev/comic/test-slug/chapter/chapter-hid",
        "cover": "cover.png",
    }


@pytest.mark.asyncio
async def test_get_latest_chapter_returns_none_when_fetch_fails(cog, monkeypatch):
    async def fake_fetch_json(url, params=None):
        return None

    monkeypatch.setattr(cog, "fetch_json", fake_fetch_json)

    result = await cog.get_latest_chapter("Test Manhwa", "test-slug")

    assert result is None


@pytest.mark.asyncio
async def test_get_latest_chapter_returns_none_when_comic_has_no_hid(cog, monkeypatch):
    async def fake_fetch_json(url, params=None):
        return {"comic": {"cover_url": "cover.png"}}

    monkeypatch.setattr(cog, "fetch_json", fake_fetch_json)

    result = await cog.get_latest_chapter("Test Manhwa", "test-slug")

    assert result is None


@pytest.mark.asyncio
async def test_get_latest_chapter_returns_none_when_chapters_are_empty(cog, monkeypatch):
    responses = [
        {"comic": {"hid": "comic-hid"}},
        {"chapters": []},
    ]

    async def fake_fetch_json(url, params=None):
        return responses.pop(0)

    monkeypatch.setattr(cog, "fetch_json", fake_fetch_json)

    result = await cog.get_latest_chapter("Test Manhwa", "test-slug")

    assert result is None


@pytest.mark.asyncio
async def test_get_latest_chapter_handles_invalid_chapter_number_safely(cog, monkeypatch):
    responses = [
        {"comic": {"hid": "comic-hid"}},
        {"chapters": [{"chap": "extra", "title": "Side Story", "hid": "chapter-hid"}]},
    ]

    async def fake_fetch_json(url, params=None):
        return responses.pop(0)

    monkeypatch.setattr(cog, "fetch_json", fake_fetch_json)

    result = await cog.get_latest_chapter("Test Manhwa", "test-slug")

    assert result == {
        "title": "Test Manhwa",
        "slug": "test-slug",
        "chapter": 0.0,
        "chapter_title": "Side Story",
        "link": "https://comick.dev/comic/test-slug/chapter/chapter-hid",
        "cover": None,
    }


@pytest.mark.asyncio
async def test_get_latest_chapter_falls_back_to_search_when_slug_is_stale(cog, monkeypatch):
    responses = [
        None,
        {"comic": {"hid": "new-comic-hid", "cover": "new-cover.png"}},
        {"chapters": [{"chap": "20", "title": "New Start", "hid": "new-chapter-hid"}]},
    ]

    async def fake_fetch_json(url, params=None):
        return responses.pop(0)

    async def fake_search_slug(title):
        return "new-slug", {"slug": "new-slug", "title": title}

    monkeypatch.setattr(cog, "fetch_json", fake_fetch_json)
    monkeypatch.setattr(cog, "search_slug", fake_search_slug)

    result = await cog.get_latest_chapter("Test Manhwa", "old-slug")

    assert result == {
        "title": "Test Manhwa",
        "slug": "new-slug",
        "chapter": 20.0,
        "chapter_title": "New Start",
        "link": "https://comick.dev/comic/new-slug/chapter/new-chapter-hid",
        "cover": "new-cover.png",
    }
