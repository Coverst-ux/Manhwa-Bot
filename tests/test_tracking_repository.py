import shutil
import uuid
from pathlib import Path

import aiosqlite
import pytest

from database.tracking_repository import TrackingRepository


@pytest.fixture
def repo():
    temp_dir = Path(__file__).parent / "_runtime_dbs" / uuid.uuid4().hex
    temp_dir.mkdir(parents=True)
    try:
        yield TrackingRepository(str(temp_dir / "test_manhwa.db"))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_init_tables_creates_expected_tables(repo):
    await repo.init_tables()

    async with aiosqlite.connect(repo.db_path) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('manhwas', 'chapter_tracking')"
        ) as cursor:
            rows = await cursor.fetchall()

    assert {row[0] for row in rows} == {"manhwas", "chapter_tracking"}


@pytest.mark.asyncio
async def test_add_manhwa_inserts_list_and_tracking_rows(repo):
    await repo.init_tables()

    await repo.add_manhwa(
        user_id=123,
        title="Solo Leveling",
        cover="cover.png",
        link="https://comick.dev/comic/solo-leveling",
        slug="solo-leveling",
    )

    async with aiosqlite.connect(repo.db_path) as db:
        async with db.execute("SELECT user_id, title, cover, link FROM manhwas") as cursor:
            manhwa_rows = await cursor.fetchall()
        async with db.execute(
            "SELECT user_id, manhwa_title, manhwa_slug, latest_chapter_notified FROM chapter_tracking"
        ) as cursor:
            tracking_rows = await cursor.fetchall()

    assert manhwa_rows == [(123, "Solo Leveling", "cover.png", "https://comick.dev/comic/solo-leveling")]
    assert tracking_rows == [(123, "Solo Leveling", "solo-leveling", 0.0)]


@pytest.mark.asyncio
async def test_get_all_tracked_manhwas_returns_tracking_rows(repo):
    await repo.init_tables()
    await repo.add_manhwa(123, "Solo Leveling", None, "https://comick.dev/comic/solo-leveling", "solo-leveling")

    rows = await repo.get_all_tracked_manhwas()

    assert rows == [(123, "Solo Leveling", "solo-leveling", 0.0)]


@pytest.mark.asyncio
async def test_update_latest_notified_updates_chapter(repo):
    await repo.init_tables()
    await repo.add_manhwa(123, "Solo Leveling", None, "https://comick.dev/comic/solo-leveling", "solo-leveling")

    await repo.update_latest_notified(123, "solo-leveling", 15.5)

    rows = await repo.get_all_tracked_manhwas()
    assert rows == [(123, "Solo Leveling", "solo-leveling", 15.5)]


@pytest.mark.asyncio
async def test_remove_manhwa_deletes_list_and_tracking_rows(repo):
    await repo.init_tables()
    await repo.add_manhwa(123, "Solo Leveling", None, "https://comick.dev/comic/solo-leveling", "solo-leveling")

    removed = await repo.remove_manhwa(123, "Solo Leveling")

    async with aiosqlite.connect(repo.db_path) as db:
        async with db.execute("SELECT * FROM manhwas") as cursor:
            manhwa_rows = await cursor.fetchall()
        async with db.execute("SELECT * FROM chapter_tracking") as cursor:
            tracking_rows = await cursor.fetchall()

    assert removed is True
    assert manhwa_rows == []
    assert tracking_rows == []


@pytest.mark.asyncio
async def test_remove_manhwa_returns_false_when_title_is_missing(repo):
    await repo.init_tables()

    removed = await repo.remove_manhwa(123, "Missing Title")

    assert removed is False
