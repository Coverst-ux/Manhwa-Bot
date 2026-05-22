from discord.ext import tasks, commands
from discord import app_commands
import discord
import asyncio
import aiosqlite
import aiohttp
import logging
from services.comick_client import ComickClient

log = logging.getLogger(__name__)


class AddManhwaComick(commands.Cog):
    TIMEOUT = aiohttp.ClientTimeout(total=10)

    def __init__(self, bot):
        self.bot = bot
        self._chapter_check_task = None
        self.session = None
        self.comick = None
        log.info("Cog initialized")
    
    @staticmethod
    def format_chapter_number(chapter: float) -> str:
        """Format chapter number: show as int if whole, else as float."""
        try:
            if chapter == int(chapter):
                return str(int(chapter))
            return str(chapter)
        except (ValueError, TypeError):
            return str(chapter)

    async def cog_load(self):
        """runs when cog is loaded by discord.py; start tasks here."""
        log.info("Cog loaded - initializing DB and starting task")
        self.session = aiohttp.ClientSession(timeout=self.TIMEOUT)
        self.comick = ComickClient(self.session)
        await self.init_db()
        await self.init_chapter_tracking_db()
        # create and start the repeated task safely
        if self._chapter_check_task is None:
            self._chapter_check_task = tasks.loop(hours=24)(self._chapter_check_loop)
            self._chapter_check_task.before_loop(self._before_chapter_check)
            self._chapter_check_task.start()

    async def cog_unload(self):
        """called when the cog is unloaded — stop background tasks cleanly."""
        log.info("Unloading cog: stopping tasks")
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
            log.info("Manhwas table initialized")
        except Exception as e:
            log.error(f"Manhwas table init failed: {e}", exc_info=True)

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
            log.info("Chapter tracking table initialized")
        except Exception as e:
            log.error(f"Chapter tracking table init failed: {e}", exc_info=True)

    # ============ SLASH COMMANDS ============

    @app_commands.command(name="add_manhwa", description="Add a manhwa to your list using Comick API")
    async def add_manhwa(self, interaction: discord.Interaction, title: str):
        log.info(f"add_manhwa called by {interaction.user} with title: {title}")
        await interaction.response.defer()

        slug, top = await self.comick.search_slug(title)
        if not slug:
            await interaction.followup.send(f"❌ No results found for **{title}**.")
            return

        cover = top.get("cover_url") or top.get("cover")
        url = f"{self.comick.WEB_BASE}/comic/{slug}"

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
            log.info(f"Inserted {top.get('title', title)} for user {interaction.user.id}")
        except Exception as e:
            log.error(f"Database insert failed: {e}", exc_info=True)
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
        log.info(f"remove_manhwa called by {interaction.user} for: {title}")
        await interaction.response.defer()
        try:
            async with aiosqlite.connect('manhwa.db') as db:
                async with db.execute("SELECT link FROM manhwas WHERE title = ? AND user_id = ?", (title, interaction.user.id)) as cursor:
                    row = await cursor.fetchone()
                if not row:
                    await interaction.followup.send(f"❌ **{title}** not found in your list.")
                    return
                
                async with db.execute(
                    "SELECT manhwa_slug FROM chapter_tracking WHERE user_id = ? AND manhwa_title = ?",
                    (interaction.user.id, title)
                ) as cursor:
                    slug_row = await cursor.fetchone()
                    slug = slug_row[0] if slug_row else None
                
                cursor = await db.execute("DELETE FROM manhwas WHERE title = ? AND user_id = ?", (title, interaction.user.id))
                rows_deleted = cursor.rowcount
                
                if slug:
                    await db.execute("DELETE FROM chapter_tracking WHERE user_id = ? AND manhwa_slug = ?", (interaction.user.id, slug))
                
                await db.commit()
            
            if rows_deleted == 0:
                await interaction.followup.send(f"❌ **{title}** not found in your list.")
            else:
                await interaction.followup.send(f"🗑️ Removed **{title}** from your list!")
        except Exception as e:
            log.error(f"Database delete failed: {e}", exc_info=True)
            await interaction.followup.send("❌ Failed to remove. Try again.")

    # ============ BACKGROUND TASK ============

    async def _before_chapter_check(self):
        await self.bot.wait_until_ready()
        log.info("Bot ready, chapter check task will start now")

    async def _chapter_check_loop(self):
        log.info("Running chapter check...")
        async with aiosqlite.connect('manhwa.db') as db:
            async with db.execute("SELECT user_id, manhwa_title, manhwa_slug, latest_chapter_notified FROM chapter_tracking") as cursor:
                rows = await cursor.fetchall()
            try:
                user_updates = {}

                log.info(f"Checking {len(rows)} tracked manhwas")
                for user_id, manhwa_title, manhwa_slug, latest_notified in rows:
                    try:
                        latest_info = await self.comick.get_latest_chapter(manhwa_title, manhwa_slug)
                        if not latest_info:
                            continue

                        latest_chapter_num = latest_info["chapter"]
                        if latest_chapter_num > (latest_notified or 0):
                            if user_id not in user_updates:
                                user_updates[user_id] = []
                            user_updates[user_id].append(latest_info)

                            # Update DB immediately
                            await db.execute(
                                "UPDATE chapter_tracking SET latest_chapter_notified = ?, last_notified_time = CURRENT_TIMESTAMP WHERE user_id = ? AND manhwa_slug = ?",
                                (latest_chapter_num, user_id, manhwa_slug)
                                ) 
                            await db.commit()
                    except Exception as e:
                        log.error(f"Error checking {manhwa_title}: {e}", exc_info=True)

                # Send DMs
                log.info(f"Sending updates to {len(user_updates)} users")
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
                            chapter_num = self.format_chapter_number(update['chapter'])
                            chapter_info = f"**Chapter {chapter_num}**"
                            if update['chapter_title']:
                                chapter_info += f"\n_{update['chapter_title']}_"
                            chapter_info += f"\n[Read here]({update['link']})"
                            embed.add_field(name=update['title'], value=chapter_info, inline=False)

                        embed.set_footer(text="Powered by Comick")
                        await user.send(embed=embed)
                        await asyncio.sleep(1)
                        log.info(f"Sent {len(updates)} updates to {uid}")
                    except Exception as e:
                        log.error(f"Failed to send DM to {uid}: {e}", exc_info=True)
            except Exception as e:
                log.error(f"Chapter check failed: {e}", exc_info=True)

# setup function for load_extension
async def setup(bot):
    cog = AddManhwaComick(bot)
    await bot.add_cog(cog)
    log.info("Cog added")
