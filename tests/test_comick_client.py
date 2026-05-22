import pytest

from services.comick_client import ComickClient


@pytest.fixture
def client():
    return ComickClient(session=None)


class FakeResponse:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def json(self):
        return {"ok": True}


class FakeSession:
    def __init__(self):
        self.request = None

    def get(self, url, **kwargs):
        self.request = {"url": url, **kwargs}
        return FakeResponse()


@pytest.mark.asyncio
async def test_fetch_json_sends_tachiyomi_user_agent():
    session = FakeSession()
    client = ComickClient(session=session)

    result = await client._fetch_json("https://example.test", params={"tachiyomi": "true"})

    assert result == {"ok": True}
    assert session.request["headers"] == {"User-Agent": "Tachiyomi/1.0"}
    assert session.request["params"] == {"tachiyomi": "true"}


@pytest.mark.asyncio
async def test_search_slug_returns_top_result(client, monkeypatch):
    async def fake_fetch_json(url, params=None):
        assert params == {"q": "Solo Leveling", "tachiyomi": "true"}
        return [{"slug": "solo-leveling", "title": "Solo Leveling"}]

    monkeypatch.setattr(client, "_fetch_json", fake_fetch_json)

    slug, top = await client.search_slug("Solo Leveling")

    assert slug == "solo-leveling"
    assert top == {"slug": "solo-leveling", "title": "Solo Leveling"}


@pytest.mark.asyncio
async def test_search_slug_returns_none_when_no_results(client, monkeypatch):
    async def fake_fetch_json(url, params=None):
        return []

    monkeypatch.setattr(client, "_fetch_json", fake_fetch_json)

    slug, top = await client.search_slug("Missing Manhwa")

    assert slug is None
    assert top is None


@pytest.mark.asyncio
async def test_get_latest_chapter_returns_chapter_info(client, monkeypatch):
    responses = [
        {"comic": {"hid": "comic-hid", "cover_url": "cover.png"}},
        {"chapters": [{"chap": "15", "title": "The Fight", "hid": "chapter-hid"}]},
    ]

    async def fake_fetch_json(url, params=None):
        return responses.pop(0)

    monkeypatch.setattr(client, "_fetch_json", fake_fetch_json)

    result = await client.get_latest_chapter("Test Manhwa", "test-slug")

    assert result == {
        "title": "Test Manhwa",
        "slug": "test-slug",
        "chapter": 15.0,
        "chapter_title": "The Fight",
        "link": "https://comick.dev/comic/test-slug/chapter/chapter-hid",
        "cover": "cover.png",
    }


@pytest.mark.asyncio
async def test_get_latest_chapter_returns_none_when_fetch_fails(client, monkeypatch):
    async def fake_fetch_json(url, params=None):
        return None

    monkeypatch.setattr(client, "_fetch_json", fake_fetch_json)

    result = await client.get_latest_chapter("Test Manhwa", "test-slug")

    assert result is None


@pytest.mark.asyncio
async def test_get_latest_chapter_returns_none_when_comic_has_no_hid(client, monkeypatch):
    async def fake_fetch_json(url, params=None):
        return {"comic": {"cover_url": "cover.png"}}

    monkeypatch.setattr(client, "_fetch_json", fake_fetch_json)

    result = await client.get_latest_chapter("Test Manhwa", "test-slug")

    assert result is None


@pytest.mark.asyncio
async def test_get_latest_chapter_returns_none_when_chapters_are_empty(client, monkeypatch):
    responses = [
        {"comic": {"hid": "comic-hid"}},
        {"chapters": []},
    ]

    async def fake_fetch_json(url, params=None):
        return responses.pop(0)

    monkeypatch.setattr(client, "_fetch_json", fake_fetch_json)

    result = await client.get_latest_chapter("Test Manhwa", "test-slug")

    assert result is None


@pytest.mark.asyncio
async def test_get_latest_chapter_handles_invalid_chapter_number_safely(client, monkeypatch):
    responses = [
        {"comic": {"hid": "comic-hid"}},
        {"chapters": [{"chap": "extra", "title": "Side Story", "hid": "chapter-hid"}]},
    ]

    async def fake_fetch_json(url, params=None):
        return responses.pop(0)

    monkeypatch.setattr(client, "_fetch_json", fake_fetch_json)

    result = await client.get_latest_chapter("Test Manhwa", "test-slug")

    assert result == {
        "title": "Test Manhwa",
        "slug": "test-slug",
        "chapter": 0.0,
        "chapter_title": "Side Story",
        "link": "https://comick.dev/comic/test-slug/chapter/chapter-hid",
        "cover": None,
    }


@pytest.mark.asyncio
async def test_get_latest_chapter_falls_back_to_search_when_slug_is_stale(client, monkeypatch):
    responses = [
        None,
        {"comic": {"hid": "new-comic-hid", "cover": "new-cover.png"}},
        {"chapters": [{"chap": "20", "title": "New Start", "hid": "new-chapter-hid"}]},
    ]

    async def fake_fetch_json(url, params=None):
        return responses.pop(0)

    async def fake_search_slug(title):
        return "new-slug", {"slug": "new-slug", "title": title}

    monkeypatch.setattr(client, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(client, "search_slug", fake_search_slug)

    result = await client.get_latest_chapter("Test Manhwa", "old-slug")

    assert result == {
        "title": "Test Manhwa",
        "slug": "new-slug",
        "chapter": 20.0,
        "chapter_title": "New Start",
        "link": "https://comick.dev/comic/new-slug/chapter/new-chapter-hid",
        "cover": "new-cover.png",
    }
