import asyncio
import logging

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from database.tracking_repository import TrackingRepository
from services.comick_client import ComickClient

log = logging.getLogger(__name__)


class TrackingCog(commands.Cog):
    TIMEOUT = aiohttp.ClientTimeout(total=10)

    def __init__(self, bot):
        self.bot = bot
        self._chapter_check_task = None
        self.session = None
        self.comick = None
        self.repo = TrackingRepository()
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
        """Runs when cog is loaded by discord.py; start tasks here."""
        log.info("Cog loaded - initializing DB and starting task")
        self.session = aiohttp.ClientSession(timeout=self.TIMEOUT)
        self.comick = ComickClient(self.session)
        await self.repo.init_tables()

        if self._chapter_check_task is None:
            self._chapter_check_task = tasks.loop(hours=24)(self._chapter_check_loop)
            self._chapter_check_task.before_loop(self._before_chapter_check)
            self._chapter_check_task.start()

    async def cog_unload(self):
        """Called when the cog is unloaded; stop background tasks cleanly."""
        log.info("Unloading cog: stopping tasks")
        if self._chapter_check_task and self._chapter_check_task.is_running():
            self._chapter_check_task.cancel()
        if self.session:
            await self.session.close()

    @app_commands.command(name="add_manhwa", description="Add a manhwa to your list using Comick API")
    async def add_manhwa(self, interaction: discord.Interaction, title: str):
        log.info("add_manhwa called by %s with title: %s", interaction.user, title)
        await interaction.response.defer()

        slug, top = await self.comick.search_slug(title)
        if not slug:
            await interaction.followup.send(f"No results found for **{title}**.")
            return

        saved_title = top.get("title", title)
        cover = top.get("cover_url") or top.get("cover")
        url = f"{self.comick.WEB_BASE}/comic/{slug}"

        try:
            inserted = await self.repo.add_manhwa(interaction.user.id, saved_title, cover, url, slug)
            if not inserted:
                await interaction.followup.send(f"**{saved_title}** is already in your list.")
                return
            log.info("Inserted %s for user %s", saved_title, interaction.user.id)
        except Exception as e:
            log.error("Database insert failed: %s", e, exc_info=True)
            await interaction.followup.send("Failed to save to database. Try again.")
            return

        embed = discord.Embed(
            title=saved_title,
            url=url,
            description="Added to your list.",
            color=0x2b2d31,
        )
        if cover:
            embed.set_image(url=cover)
        embed.set_footer(text="Powered by Comick API")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="remove_manhwa", description="Remove a manhwa from your list")
    async def remove_manhwa(self, interaction: discord.Interaction, title: str):
        log.info("remove_manhwa called by %s for: %s", interaction.user, title)
        await interaction.response.defer()

        try:
            removed = await self.repo.remove_manhwa(interaction.user.id, title)
        except Exception as e:
            log.error("Database delete failed: %s", e, exc_info=True)
            await interaction.followup.send("Failed to remove. Try again.")
            return

        if not removed:
            await interaction.followup.send(f"**{title}** not found in your list.")
        else:
            await interaction.followup.send(f"Removed **{title}** from your list.")
            
    @app_commands.command(name="list_manhwa", description="List your saved manhwas")
    async def list_manhwas(self, interaction: discord.Interaction):
        log.info("list_manhwa called by %s", interaction.user)
        await interaction.response.defer()
        
        try:
           rows = await self.repo.get_user_manhwas(interaction.user.id)
        except Exception as e:
            log.error("Failed to fetch manhwa for %s: %s.", interaction.user.id, e, exc_info=True)
            await interaction.followup.send("Failed to fetch your list. Try again")
            return
        
        if not rows:
            await interaction.followup.send("Your list is empty. Use `/add_manhwa` to start tracking.")
            return

        description = "\n".join(f"[{title}]({link})" for title, link in rows)
        
        embed= discord.Embed(
            title="Your Manhwa List",
            description=description,
            color=0x2b2d31
        )
        embed.set_footer(text=f"{len(rows)} manhwa(s) tracked")
        await interaction.followup.send(embed=embed)        
        
        
        

    async def _before_chapter_check(self):
        await self.bot.wait_until_ready()
        log.info("Bot ready, chapter check task will start now")

    async def _chapter_check_loop(self):
        log.info("Running chapter check...")
        try:
            rows = await self.repo.get_all_tracked_manhwas()
            user_updates = {}

            log.info("Checking %d tracked manhwas", len(rows))
            for user_id, manhwa_title, manhwa_slug, latest_notified in rows:
                try:
                    latest_info = await self.comick.get_latest_chapter(manhwa_title, manhwa_slug)
                    if not latest_info:
                        continue

                    latest_chapter_num = latest_info["chapter"]
                    if latest_chapter_num > (latest_notified or 0):
                        user_updates.setdefault(user_id, []).append(latest_info)
                        await self.repo.update_latest_notified(user_id, manhwa_slug, latest_chapter_num)
                except Exception as e:
                    log.error("Error checking %s: %s", manhwa_title, e, exc_info=True)

            log.info("Sending updates to %d users", len(user_updates))
            for uid, updates in user_updates.items():
                try:
                    user = await self.bot.fetch_user(uid)
                    embed = discord.Embed(
                        title="Your Manhwas Have New Chapters!",
                        description=f"**{len(updates)}** new chapter(s) since last check:",
                        color=0x2b2d31,
                    )
                    if updates and updates[0]["cover"]:
                        embed.set_image(url=updates[0]["cover"])

                    for update in updates:
                        chapter_num = self.format_chapter_number(update["chapter"])
                        chapter_info = f"**Chapter {chapter_num}**"
                        if update["chapter_title"]:
                            chapter_info += f"\n_{update['chapter_title']}_"
                        chapter_info += f"\n[Read here]({update['link']})"
                        embed.add_field(name=update["title"], value=chapter_info, inline=False)

                    embed.set_footer(text="Powered by Comick")
                    await user.send(embed=embed)
                    await asyncio.sleep(1)
                    log.info("Sent %d updates to %s", len(updates), uid)
                except discord.Forbidden:
                    log.warning("Cannot send DM to %s: DMs disabled", uid)
                except Exception as e:
                    log.error("Failed to send DM to %s: %s", uid, e, exc_info=True)
        except Exception as e:
            log.error("Chapter check failed: %s", e, exc_info=True)


async def setup(bot):
    cog = TrackingCog(bot)
    await bot.add_cog(cog)
    log.info("Cog added")
