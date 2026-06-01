import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import logging

# ------------------------
# Setup
# ------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

log = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("TOKEN")


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------
# Cogs
# ------------------------
initial_extensions = [
    "cogs.Owner_Commands",
    "cogs.Tracking",
    "cogs.Hybrid_Commands",
    "cogs.Manual_Check"
]

async def load_cogs():
    for ext in initial_extensions:
        try:
            await bot.load_extension(ext)
            log.info("Loaded %s", ext)
        except Exception as e:
            log.exception("Failed to load %s: %s", ext, e)

# ------------------------
# Events
# ------------------------
@bot.event
async def on_ready():
    log.info("Logged in as %s (%s)", bot.user, bot.user.id)
    await asyncio.sleep(2)

    log.debug("Commands loaded in tree:")
    for cmd in bot.tree.get_commands():
        cog_name = cmd.binding.__class__.__name__ if cmd.binding else "None"
        log.debug("  /%s (from %s)", cmd.name, cog_name)

    try:
        log.info("Syncing commands globally...")
        synced = await bot.tree.sync()
        log.info("Synced %d command(s) globally", len(synced))
    except Exception as e:
        log.exception("Failed to sync commands: %s", e)

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="Novels")
    )
    log.info("Bot is fully ready.")

# ------------------------
# Main
# ------------------------
async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
