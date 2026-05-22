import logging

import aiosqlite

log = logging.getLogger(__name__)


class TrackingRepository:
    def __init__(self, db_path: str = "manhwa.db"):
        self.db_path = db_path

    async def init_tables(self):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS manhwas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        title TEXT NOT NULL,
                        cover TEXT,
                        link TEXT NOT NULL
                    )
                """)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS chapter_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        manhwa_title TEXT,
                        manhwa_slug TEXT,
                        latest_chapter_notified REAL,
                        last_notified_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, manhwa_slug)
                    )
                """)
                await db.commit()
            log.info("Tracking tables initialized")
        except Exception as e:
            log.error("Tracking table init failed: %s", e, exc_info=True)

    async def add_manhwa(self, user_id: int, title: str, cover: str | None, link: str, slug: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO manhwas (user_id, title, cover, link) VALUES (?, ?, ?, ?)",
                (user_id, title, cover, link),
            )
            await db.execute(
                """
                INSERT OR IGNORE INTO chapter_tracking
                (user_id, manhwa_title, manhwa_slug, latest_chapter_notified)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, title, slug, 0),
            )
            await db.commit()

    async def remove_manhwa(self, user_id: int, title: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT link FROM manhwas WHERE title = ? AND user_id = ?",
                (title, user_id),
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                return False

            async with db.execute(
                "SELECT manhwa_slug FROM chapter_tracking WHERE user_id = ? AND manhwa_title = ?",
                (user_id, title),
            ) as cursor:
                slug_row = await cursor.fetchone()
                slug = slug_row[0] if slug_row else None

            cursor = await db.execute(
                "DELETE FROM manhwas WHERE title = ? AND user_id = ?",
                (title, user_id),
            )
            rows_deleted = cursor.rowcount

            if slug:
                await db.execute(
                    "DELETE FROM chapter_tracking WHERE user_id = ? AND manhwa_slug = ?",
                    (user_id, slug),
                )

            await db.commit()
            return rows_deleted > 0

    async def get_all_tracked_manhwas(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT user_id, manhwa_title, manhwa_slug, latest_chapter_notified
                FROM chapter_tracking
                """
            ) as cursor:
                return await cursor.fetchall()

    async def update_latest_notified(self, user_id: int, slug: str, chapter: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE chapter_tracking
                SET latest_chapter_notified = ?, last_notified_time = CURRENT_TIMESTAMP
                WHERE user_id = ? AND manhwa_slug = ?
                """,
                (chapter, user_id, slug),
            )
            await db.commit()
