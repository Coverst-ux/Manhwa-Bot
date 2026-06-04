    # cog/Manual_Check.py
import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import aiohttp
import logging
from database.tracking_repository import TrackingRepository
from services.comick_client import ComickClient

log = logging.getLogger(__name__)


class ManualCheck(commands.Cog):
    PROXY_BASE = "https://comick-api-proxy.notaspider.dev/v1.0"
    WEB_BASE = "https://comick.dev"

    def __init__(self, bot, comick: ComickClient, repo: TrackingRepository):
        self.bot = bot
        self.comick = comick
        self.repo = repo
        log.info("Cog initialized")

    
   

    @app_commands.command(name="manual_check", description="Manually check for updates for your followed novels.")
    async def manual_check(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        updates = []

        
        rows = await self.repo.get_all_tracked_manhwas()
        user_rows = [row for row in rows if row[0] == interaction.user.id]
        
        if not user_rows:
            await interaction.followup.send("You have no tracked manhwas", ephemeral=True)
            return
            
        for user_id, title, slug, last_notified in user_rows:
            latest =  await self.comick.get_latest_chapter(title, slug)
            if not latest:
                continue 
            if latest['chapter'] > last_notified:
                updates.append((title, latest["chapter"], latest["chapter_title"], latest["link"]))
                await self.repo.update_latest_notified(interaction.user.id, slug, latest["chapter"])
            
        if not updates:
            await interaction.followup.send("✅ No new chapters since your last check.", ephemeral=True)
        else:
            embed = discord.Embed(
                title="📚 Manual Update Check",
                description=f"Found {len(updates)} new chapter(s):",
                color=0x2b2d31
            )
            for title, chap_num, chap_title, link in updates:
                field_value = f"**Chapter {chap_num}**"
                if chap_title:
                    field_value += f"\n_{chap_title}_"
                field_value += f"\n[Read here]({link})"
                embed.add_field(name=title, value=field_value, inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    tracking_cog = bot.cogs.get("TrackingCog")
    await bot.add_cog(ManualCheck(bot, tracking_cog.comick, tracking_cog.repo))
    log.info("Cog added")    
