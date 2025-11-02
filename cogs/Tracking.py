from discord.ext import tasks, commands
from discord import app_commands
import discord
import asyncio
import aiosqlite
import aiohttp
import traceback
from typing import Optional

class AddManhwaComick(commands.Cog):
    BASE_URL = "https://comick-api-proxy.notaspider.dev/api"
    WEB_BASE = "https://comick.dev"
    TIMEOUT = aiohttp.ClientTimeout(total=10)

    def __init__(self, bot):
        self.bot = bot
        self._chapter_check_task = None
        self.session = None
        print("[AddManhwaComick] Cog initialized")

    async def cog_load(self):
        """runs when cog is loaded by discord.py; start tasks here."""
        print("[AddManhwaComick] Cog loaded - initializing DB and starting task")
        self.session = aiohttp.ClientSession(timeout=self.TIMEOUT)
        await self.init_db()
        await self.init_chapter_tracking_db()
        # create and start the repeated task safely
        if self._chapter_check_task is None:
            self._chapter_check_task = tasks.loop(hours=24)(self._chapter_check_loop)
            self._chapter_check_task.before_loop(self._before_chapter_check)
            self._chapter_check_task.start()

    async def cog_unload(self):
        """called when the cog is unloaded — stop background tasks cleanly."""
        print("[AddManhwaComick] Unloading cog: stopping tasks")
        if self._chapter_check_task and self._chapter_check_task.is_running():
            self._chapter_check_task.cancel()
        if self.session:
            await self.session.close()

    # ============ DATABASE ============

    async def init_db(self):
        try:
            async with aiosqlite.connect('manhwa.db') as db:
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS manhwas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        title TEXT NOT NULL,
                        cover TEXT,
                        link TEXT NOT NULL
                    )
                ''')
                await db.commit()
            print("[AddManhwaComick] Manhwas table initialized")
        except Exception as e:
            print(f"[AddManhwaComick] Manhwas table init failed: {e}")
            traceback.print_exc()

    async def init_chapter_tracking_db(self):
        try:
            async with aiosqlite.connect('manhwa.db') as db:
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS chapter_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        manhwa_title TEXT,
                        manhwa_slug TEXT,
                        latest_chapter_notified REAL,
                        last_notified_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, manhwa_slug)
                    )
                ''')
                await db.commit()
            print("[AddManhwaComick] Chapter tracking table initialized")
        except Exception as e:
            print(f"[AddManhwaComick] Chapter tracking table init failed: {e}")
            traceback.print_exc()

    # ============ UTILITIES ============

    async def fetch_json(self, url: str, params: Optional[dict] = None, retries: int = 2, timeout: int = 10):
        """Fetch JSON from API with basic retries and timeout."""
        if not self.session:
            return None

        for attempt in range(1, retries + 2):
            try:
                async with self.session.get(url, params=params) as resp:
                    if resp.status != 200:
                        print(f"[AddManhwaComick] API returned {resp.status} for {url} (attempt {attempt})")
                        if attempt <= retries:
                            await asyncio.sleep(1)
                            continue
                        return None
                    return await resp.json()
            except asyncio.TimeoutError:
                print(f"[AddManhwaComick] API request timeout for {url} (attempt {attempt})")
                if attempt <= retries:
                    await asyncio.sleep(1)
                    continue
                return None
            except Exception as e:
                print(f"[AddManhwaComick] Fetch error for {url} (attempt {attempt}): {e}")
                if attempt <= retries:
                    await asyncio.sleep(1)
                    continue
                return None

    async def search_slug(self, title: str):
        search_url = f"{self.BASE_URL}/v1.0/search"
        print(f"[AddManhwaComick] Searching for: {title}")
        data = await self.fetch_json(search_url, params={"q": title, "tachiyomi": "true"})
        if not data:
            print(f"[AddManhwaComick] No results for: {title}")
            return None, None
        top = data[0]
        slug = top.get("slug")
        print(f"[AddManhwaComick] Found: {top.get('title', title)} (slug: {slug})")
        return slug, top

    async def get_latest_chapter(self, title: str, slug: str):
        """
        Returns the latest chapter info for a given manhwa title/slug.
        Resolves slug if needed.
        """
        # Step 1: Try current slug
        comic_url = f"{self.BASE_URL}/v1.0/comic/{slug}"
        comic_data = await self.fetch_json(comic_url, params={"tachiyomi": "true"})

        if not comic_data or "comic" not in comic_data:
            # Fallback: search by title
            new_slug, top = await self.search_slug(title)
            if not new_slug:
                print(f"[AddManhwaComick] Could not resolve slug for {title}")
                return None
            slug = new_slug
            comic_data = await self.fetch_json(f"{self.BASE_URL}/v1.0/comic/{slug}", params={"tachiyomi": "true"})
            if not comic_data or "comic" not in comic_data:
                print(f"[AddManhwaComick] No comic data for {title} after resolving slug")
                return None

        comic_obj = comic_data["comic"]
        hid = comic_obj.get("hid")
        cover_url = comic_obj.get("cover_url") or comic_obj.get("cover")

        if not hid:
            print(f"[AddManhwaComick] No hid found for {title}")
            return None

        # Step 2: Fetch latest chapter by hid
        chapters_url = f"{self.BASE_URL}/v1.0/comic/{hid}/chapters"
        chapters_data = await self.fetch_json(chapters_url, params={"limit": 1, "tachiyomi": "true"})
        if not chapters_data or "chapters" not in chapters_data or not chapters_data["chapters"]:
            print(f"[AddManhwaComick] No chapters found for {title}")
            return None

        latest = chapters_data["chapters"][0]
        chap_num_raw = latest.get("chap") or latest.get("chapter") or 0
        try:
            chap_num = float(chap_num_raw)
        except Exception:
            chap_num = 0.0

        chap_title = latest.get("title", "")
        chap_hid = latest.get("hid") or latest.get("id") or ""
        chap_link = f"{self.WEB_BASE}/comic/{slug}/chapter/{chap_hid}"

        return {
            "title": title,
            "slug": slug,
            "chapter": chap_num,
            "chapter_title": chap_title,
            "link": chap_link,
            "cover": cover_url
        }

    # ============ SLASH COMMANDS ============

    @app_commands.command(name="add_manhwa", description="Add a manhwa to your list using Comick API")
    async def add_manhwa(self, interaction: discord.Interaction, title: str):
        print(f"[AddManhwaComick] add_manhwa called by {interaction.user} with title: {title}")
        await interaction.response.defer()

        slug, top = await self.search_slug(title)
        if not slug:
            await interaction.followup.send(f"❌ No results found for **{title}**.")
            return

        cover = top.get("cover_url") or top.get("cover")
        url = f"{self.WEB_BASE}/comic/{slug}"

        try:
            async with aiosqlite.connect('manhwa.db') as db:
                await db.execute(
                    "INSERT INTO manhwas (user_id, title, cover, link) VALUES (?, ?, ?, ?)",
                    (interaction.user.id, top.get("title", title), cover, url)
                )
                await db.execute(
                    "INSERT OR IGNORE INTO chapter_tracking (user_id, manhwa_title, manhwa_slug, latest_chapter_notified) VALUES (?, ?, ?, ?)",
                    (interaction.user.id, top.get("title", title), slug, 0)
                )
                await db.commit()
            print(f"[AddManhwaComick] Inserted {top.get('title', title)} for user {interaction.user.id}")
        except Exception as e:
            print(f"[AddManhwaComick] Database insert failed: {e}")
            traceback.print_exc()
            await interaction.followup.send("❌ Failed to save to database. Try again.")
            return

        embed = discord.Embed(
            title=top.get("title", title),
            url=url,
            description="✅ Added to your list!",
            color=0x2b2d31
        )
        if cover:
            embed.set_image(url=cover)
        embed.set_footer(text="Powered by Comick API")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="remove_manhwa", description="Remove a manhwa from your list")
    async def remove_manhwa(self, interaction: discord.Interaction, title: str):
        # UNTOUCHED
        ...

    @app_commands.command(name="list_manhwas", description="List all your saved manhwas")
    async def list_manhwas(self, interaction: discord.Interaction):
        # UNTOUCHED
        ...

    # ============ BACKGROUND TASK ============

    async def _before_chapter_check(self):
        await self.bot.wait_until_ready()
        print("[AddManhwaComick] Bot ready, chapter check task will start now")

    async def _chapter_check_loop(self):
        print("[AddManhwaComick] Running chapter check...")
        try:
            user_updates = {}
            async with aiosqlite.connect('manhwa.db') as db:
                async with db.execute("SELECT user_id, manhwa_title, manhwa_slug, latest_chapter_notified FROM chapter_tracking") as cursor:
                    rows = await cursor.fetchall()

            print(f"[AddManhwaComick] Checking {len(rows)} tracked manhwas")
            for user_id, manhwa_title, manhwa_slug, latest_notified in rows:
                try:
                    latest_info = await self.get_latest_chapter(manhwa_title, manhwa_slug)
                    if not latest_info:
                        continue

                    latest_chapter_num = latest_info["chapter"]
                    if latest_chapter_num > (latest_notified or 0):
                        if user_id not in user_updates:
                            user_updates[user_id] = []
                        user_updates[user_id].append(latest_info)

                        # Update DB immediately
                        async with aiosqlite.connect('manhwa.db') as db:
                            await db.execute(
                                "UPDATE chapter_tracking SET latest_chapter_notified = ?, last_notified_time = CURRENT_TIMESTAMP WHERE user_id = ? AND manhwa_slug = ?",
                                (latest_chapter_num, user_id, manhwa_slug)
                            )
                            await db.commit()
                except Exception as e:
                    print(f"[AddManhwaComick] Error checking {manhwa_title}: {e}")
                    traceback.print_exc()

            # Send DMs
            print(f"[AddManhwaComick] Sending updates to {len(user_updates)} users")
            for uid, updates in user_updates.items():
                try:
                    user = await self.bot.fetch_user(uid)
                    embed = discord.Embed(
                        title="📚 Your Manhwas Have New Chapters!",
                        description=f"**{len(updates)}** new chapter(s) since last check:",
                        color=0x2b2d31
                    )
                    if updates and updates[0]['cover']:
                        embed.set_image(url=updates[0]['cover'])

                    for update in updates:
                        chapter_num = int(update['chapter']) if update['chapter'] == int(update['chapter']) else update['chapter']
                        chapter_info = f"**Chapter {chapter_num}**"
                        if update['chapter_title']:
                            chapter_info += f"\n_{update['chapter_title']}_"
                        chapter_info += f"\n[Read here]({update['link']})"
                        embed.add_field(name=update['title'], value=chapter_info, inline=False)

                    embed.set_footer(text="Powered by Comick")
                    await user.send(embed=embed)
                    await asyncio.sleep(1)
                    print(f"[AddManhwaComick] Sent {len(updates)} updates to {uid}")
                except Exception as e:
                    print(f"[AddManhwaComick] Failed to send DM to {uid}: {e}")
                    traceback.print_exc()
        except Exception as e:
            print(f"[AddManhwaComick] Chapter check failed: {e}")
            traceback.print_exc()


# setup function for load_extension
async def setup(bot):
    cog = AddManhwaComick(bot)
    await bot.add_cog(cog)
    print("[AddManhwaComick] Cog added")
