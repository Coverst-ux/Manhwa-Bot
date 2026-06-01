import discord
from discord.ext import commands
import aiohttp
import asyncio
import logging
from database.tracking_repository import TrackingRepository
from services.comick_client import ComickClient

log = logging.getLogger(__name__)

class ComickSlash(commands.Cog):
    BASE_URL = "https://comick-api-proxy.notaspider.dev/api"
    WEB_BASE = "https://comick.dev"
    TIMEOUT = aiohttp.ClientTimeout(total=10)

    def __init__(self, bot, comick: ComickClient):
        self.bot = bot
        self.comick = comick
    # ---------------- Utility ----------------
    async def send_embed(self, ctx_or_interaction, embed, view=None):
        try:
            if isinstance(ctx_or_interaction, commands.Context):
                await ctx_or_interaction.send(embed=embed, view=view)
            else:
                if not ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.response.send_message(embed=embed, view=view)
                else:
                    await ctx_or_interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            log.error("Failed to send embed: %s", e)
            try:
                if isinstance(ctx_or_interaction, commands.Context):
                    await ctx_or_interaction.send("⚠️ Failed to send message.")
                else:
                    await ctx_or_interaction.followup.send("⚠️ Failed to send message.")
            except Exception as e:
                log.error("Failed to send fallback message: %s", e)

    # ---------------- Commands ----------------
    @commands.hybrid_command(name="search", description="Search for a manga/manhwa by title")
    @discord.app_commands.describe(title="The manga/manhwa title to search")
    async def search(self, ctx: commands.Context, title: str):
        if ctx.interaction:
            await ctx.interaction.response.defer()
        slug, top = await self.comick.search_slug(title)

        if not slug:
            msg = f"❌ No results found for **{title}**."
            if ctx.interaction:
                await ctx.interaction.followup.send(msg)
            else:
                await ctx.send(msg)
            return
        
        cover = top.get("cover_url") or top.get("cover")
        
        embed = discord.Embed(
            title=top.get("title", "Unknown"),
            description=(top.get("desc") or "No description.")[:300],
            url=f"{self.WEB_BASE}/comic/{slug}",
            color=0x2b2d31
        )

        if cover:
            embed.set_image(url=cover)

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="📖 Read on Comick",
            url=f"{self.WEB_BASE}/comic/{slug}"
        ))

        await self.send_embed(ctx, embed, view)

    @commands.hybrid_command(name="getdetails", description="Get detailed info about a manga/manhwa")
    @discord.app_commands.describe(title="The manga/manhwa title")
    async def getdetails(self, ctx: commands.Context, title: str):
        if ctx.interaction:
            await ctx.interaction.response.defer()

        slug, _ = await self.comick.search_slug(title)
        if not slug:
            msg = f"❌ No results found for **{title}**."
            await (ctx.interaction.followup.send(msg) if ctx.interaction else ctx.send(msg))
            return

        data = await self.comick.get_details(slug)
        if not data:
            msg = "⚠️ No details found."
            await (ctx.interaction.followup.send(msg) if ctx.interaction else ctx.send(msg))
            return

        embed = discord.Embed(
            title=data.get("title", "Unknown"),
            description=(data.get("desc") or "No description.")[:4000],
            url=f"{self.comick.WEB_BASE}/comic/{slug}",
            color=0x1abc9c
        )

        if data.get("cover"):
            embed.set_image(url=data["cover"])

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="📖 Read on Comick",
            url=f"{self.comick.WEB_BASE}/comic/{slug}"
        ))

        await self.send_embed(ctx, embed, view)

    @commands.hybrid_command(
        name="latestchapter",
        description="Get the latest chapter of a manga/manhwa"
    )
    @discord.app_commands.describe(title="The manga/manhwa title")
    async def latestchapter(self, ctx: commands.Context, title: str):
        if ctx.interaction:
            await ctx.interaction.response.defer()

        slug, _ = await self.comick.search_slug(title)
        if not slug:
            msg = f"❌ No results found for **{title}**."
            await (ctx.interaction.followup.send(msg) if ctx.interaction else ctx.send(msg))
            return

        latest = await self.comick.get_latest_chapter(title, slug)

        if not latest:
            msg = "⚠️ Could not fetch chapters."
            await (ctx.interaction.followup.send(msg) if ctx.interaction else ctx.send(msg))
            return

        chapter_url = latest["link"]
        embed = discord.Embed(
            title=latest.get("title", "Latest Chapter"),
            description=f"[Read here]({chapter_url})" if chapter_url else "No link available",
            color=0xe67e22
        )

        view = discord.ui.View()
        if chapter_url:
            view.add_item(discord.ui.Button(
                label="📖 Read Chapter",
                url=chapter_url
            ))

        await self.send_embed(ctx, embed, view)

# ---------------- Setup ----------------
async def setup(bot):
    tracking_cog = bot.cogs.get("TrackingCog")
    await bot.add_cog(ComickSlash(bot, tracking_cog.comick))
    log.info("Cog added")
