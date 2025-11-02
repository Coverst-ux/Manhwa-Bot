# cog/Manual_Check.py
import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import aiohttp
import traceback

class ManualCheck(commands.Cog):
    PROXY_BASE = "https://comick-api-proxy.notaspider.dev/v1.0"
    WEB_BASE = "https://comick.dev"

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        print("[ManualCheck] Cog initialized")

    async def cog_unload(self):
        await self.session.close()
        print("[ManualCheck] Session closed")

    async def fetch_json(self, url: str, params=None):
        try:
            async with self.session.get(
                url, 
                headers={"User-Agent": "Tachiyomi/1.0"},
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    print(f"[ManualCheck] ❌ {response.status} for {url}")
                    return None
                return await response.json()
        except Exception as e:
            print(f"[ManualCheck] ⚠️ Fetch error for {url}: {e}")
            return None

    async def resolve_slug(self, title: str, current_slug: str):
        """Try current slug first, then fallback to searching by title."""
        # Try current slug
        url = f"{self.PROXY_BASE}/comic/{current_slug}/chapters"
        data = await self.fetch_json(url, params={"limit": 1, "tachiyomi": "true"})
        if data and "chapters" in data and len(data["chapters"]) > 0:
            return current_slug

        # Fallback: search by title
        search_url = f"{self.PROXY_BASE}/search"
        data = await self.fetch_json(search_url, params={"query": title, "limit": 1})
        if data and "results" in data and len(data["results"]) > 0:
            new_slug = data["results"][0].get("slug")
            print(f"[ManualCheck] Resolved slug for '{title}' -> {new_slug}")
            return new_slug

        print(f"[ManualCheck] ❌ Could not resolve slug for '{title}'")
        return None

    async def get_latest_chapter(self, slug: str):
        url = f"{self.PROXY_BASE}/comic/{slug}/chapters"
        data = await self.fetch_json(url, params={"limit": 1, "tachiyomi": "true"})
        if not data or "chapters" not in data or len(data["chapters"]) == 0:
            print(f"[ManualCheck] ❌ No chapter data for slug '{slug}'")
            return None

        chapter = data["chapters"][0]
        return {
            "number": chapter.get("chap"),
            "title": chapter.get("title"),
            "url": f"{self.WEB_BASE}/comic/{slug}/chapter/{chapter.get('hid')}"
        }

    @app_commands.command(name="manual_check", description="Manually check for updates for your followed novels.")
    async def manual_check(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        updates = []

        try:
            async with aiosqlite.connect("manhwa.db") as db:
                async with db.execute(
                    "SELECT manhwa_title, manhwa_slug, latest_chapter_notified FROM chapter_tracking WHERE user_id = ?",
                    (interaction.user.id,)
                ) as cursor:
                    rows = await cursor.fetchall()

                if not rows:
                    await interaction.followup.send("📭 You are not following any novels.", ephemeral=True)
                    return

                for title, slug, last_notified in rows:
                    print(f"[ManualCheck] Checking {title} ({slug})...")

                    # Resolve slug first
                    resolved_slug = await self.resolve_slug(title, slug)
                    if not resolved_slug:
                        continue

                    latest = await self.get_latest_chapter(resolved_slug)
                    if not latest or not latest["number"]:
                        continue

                    try:
                        latest_number = float(latest["number"])
                    except (ValueError, TypeError):
                        continue

                    if latest_number > last_notified:
                        updates.append((title, latest_number, latest["title"], latest["url"]))
                        # Update DB with resolved slug in case it changed
                        await db.execute(
                            "UPDATE chapter_tracking SET latest_chapter_notified = ?, manhwa_slug = ?, last_notified_time = CURRENT_TIMESTAMP WHERE user_id = ? AND manhwa_title = ?",
                            (latest_number, resolved_slug, interaction.user.id, title)
                        )

                await db.commit()

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

        except Exception as e:
            print("[ManualCheck] Error during manual check:", e)
            traceback.print_exc()
            await interaction.followup.send("⚠️ Failed to check updates. See logs.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ManualCheck(bot))
    print("[ManualCheck] Cog added")
