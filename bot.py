"""Vibe Heavy — thin launcher. Real logic lives in cogs/ + core/.

Runs on YOUR machine with literal OpenCode inside (muse-spark).
Not 24/7 — that's what vibe-bot (Discloud) is for.
"""
import asyncio

import discord
from discord.ext import commands

from config import settings as cfg
from core import engine

COGS = ("cogs.tasks", "cogs.shell", "cogs.files", "cogs.general", "cogs.mod", "cogs.vibe")


class Heavy(commands.Bot):
    async def setup_hook(self):
        for ext in COGS:
            await self.load_extension(ext)
        print(f"cogs loaded: {', '.join(c.split('.')[1] for c in COGS)}")


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = Heavy(command_prefix=cfg.PREFIX, intents=intents, help_command=None)


@bot.event
async def on_ready():
    print(f"Heavy online as {bot.user} ({bot.user.id}) in {len(bot.guilds)} servers | model={cfg.MODEL}")
    await bot.change_presence(discord.Activity(
        type=discord.ActivityType.listening, name="@me + task | !help"))


if __name__ == "__main__":
    if not cfg.TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in .env")
    engine.ensure_auth()
    bot.run(cfg.TOKEN)
