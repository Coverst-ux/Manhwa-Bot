import discord
from discord.ext import commands
import aiohttp
import asyncio

class ComickSlash(commands.Cog):
    BASE_URL = "https://comick-api-proxy.notaspider.dev/api"
    WEB_BASE = "https://comick.dev"
    TIMEOUT = aiohttp.ClientTimeout(total=10)

    def __init__(self, bot):
        self.bot = bot
        self.session = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession(timeout=self.TIMEOUT)

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    # ---------------- Utility ----------------
    async def fetch_json(self, url, params=None):
        if not self.session:
            return None
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception:
            pass
        return None

    async def search_slug(self, title: str):
        if not title or not title.strip():
            return None, None

        search_url = f"{self.BASE_URL}/v1.0/search"
        data = await self.fetch_json(
            search_url,
            params={"q": title, "tachiyomi": "true"}
        )

        if not data:
            return None, None

        top = data[0]
        return top.get("slug"), top

    async def send_embed(self, ctx_or_interaction, embed, view=None):
        try:
            if isinstance(ctx_or_interaction, commands.Context):
                await ctx_or_interaction.send(embed=embed, view=view)
            else:
                if not ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.response.send_message(embed=embed, view=view)
                else:
                    await ctx_or_interaction.followup.send(embed=embed, view=view)
        except Exception:
            try:
                if isinstance(ctx_or_interaction, commands.Context):
                    await ctx_or_interaction.send("⚠️ Failed to send message.")
                else:
                    await ctx_or_interaction.followup.send("⚠️ Failed to send message.")
            except Exception:
                pass

    # ---------------- Commands ----------------
    @commands.hybrid_command(name="search", description="Search for a manga/manhwa by title")
    @discord.app_commands.describe(title="The manga/manhwa title to search")
    async def search(self, ctx: commands.Context, title: str):
        if ctx.interaction:
            await ctx.interaction.response.defer()

        slug, top = await self.search_slug(title)
        if not slug:
            msg = f"❌ No results found for **{title}**."
            await (ctx.interaction.followup.send(msg) if ctx.interaction else ctx.send(msg))
            return

        embed = discord.Embed(
            title=top.get("title", "Unknown"),
            description=(top.get("desc") or "No description.")[:300],
            url=f"{self.WEB_BASE}/comic/{slug}",
            color=0x2b2d31
        )

        if top.get("cover"):
            embed.set_image(url=top["cover"])

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

        slug, _ = await self.search_slug(title)
        if not slug:
            msg = f"❌ No results found for **{title}**."
            await (ctx.interaction.followup.send(msg) if ctx.interaction else ctx.send(msg))
            return

        data = await self.fetch_json(f"{self.BASE_URL}/comic/{slug}")
        if not data:
            msg = "⚠️ No details found."
            await (ctx.interaction.followup.send(msg) if ctx.interaction else ctx.send(msg))
            return

        embed = discord.Embed(
            title=data.get("title", "Unknown"),
            description=(data.get("desc") or "No description.")[:4000],
            url=f"{self.WEB_BASE}/comic/{slug}",
            color=0x1abc9c
        )

        if data.get("cover"):
            embed.set_image(url=data["cover"])

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="📖 Read on Comick",
            url=f"{self.WEB_BASE}/comic/{slug}"
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

        slug, _ = await self.search_slug(title)
        if not slug:
            msg = f"❌ No results found for **{title}**."
            await (ctx.interaction.followup.send(msg) if ctx.interaction else ctx.send(msg))
            return

        comic = await self.fetch_json(f"{self.BASE_URL}/v1.0/comic/{slug}")
        if not comic or not comic.get("hid"):
            msg = "⚠️ Comic ID not found."
            await (ctx.interaction.followup.send(msg) if ctx.interaction else ctx.send(msg))
            return

        chapters = await self.fetch_json(
            f"{self.BASE_URL}/v1.0/comic/{comic['hid']}/chapters",
            params={"limit": 1, "tachiyomi": "true"}
        )

        data = chapters.get("chapters") or chapters.get("data") or []
        if not data:
            msg = "⚠️ No chapters found."
            await (ctx.interaction.followup.send(msg) if ctx.interaction else ctx.send(msg))
            return

        ch = data[0]
        embed = discord.Embed(
            title=ch.get("title", "Latest Chapter"),
            description=f"[Read here]({ch.get('url')})",
            color=0xe67e22
        )

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="📖 Read Chapter",
            url=ch.get("url")
        ))

        await self.send_embed(ctx, embed, view)

# ---------------- Setup ----------------
async def setup(bot):
    await bot.add_cog(ComickSlash(bot))
