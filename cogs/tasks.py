"""Ping-to-build: @VibeHeavy <task> -> opencode agent -> reply + zip."""
import io
import os
import time
import zipfile

import discord
from discord.ext import commands

from config import settings as cfg
from core import engine
from core.helpers import is_admin


class Tasks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_used: dict[int, float] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or not self.bot.user:
            return
        if message.content.strip().startswith(cfg.PREFIX):
            return  # prefix commands handled by the command processor
        me = self.bot.user
        pinged = me in message.mentions
        if not pinged and message.reference and message.reference.message_id:
            try:
                ref = message.reference.resolved or await message.channel.fetch_message(
                    message.reference.message_id)
                pinged = bool(ref) and ref.author == me
            except Exception:
                pinged = False
        if not pinged:
            return

        task = message.content
        for m in message.mentions:
            task = task.replace(f"<@{m.id}>", "").replace(f"<@!{m.id}>", "")
        task = task.strip()
        if not task:
            await message.reply("tell me what to build. `@VibeHeavy make me a todo website`")
            return

        now = time.monotonic()
        if now - self.last_used.get(message.guild.id, 0) < cfg.COOLDOWN_S:
            await message.reply("one sec — still working. try again in a bit.")
            return
        self.last_used[message.guild.id] = now

        admin = is_admin(message.author)
        workdir = engine.sandbox_for(message.guild.id, message.author.id)
        prompt = ("You are VibeHeavy, an expert coding agent inside a Discord bot. "
                  "Build exactly what is asked. Write real runnable files, no placeholders. "
                  f"Requester is {'an ADMIN' if admin else 'a normal user'}.\n\nTASK: {task}")
        async with message.channel.typing():
            try:
                text, changed = await engine.run_task(prompt, workdir, cfg.TASK_TIMEOUT)
            except Exception as e:
                await message.reply(f"opencode blew up: {type(e).__name__}: {str(e)[:300]}")
                return
        await message.reply(engine.redact(text)[:1800] or "done.")
        if changed:
            try:
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    for f in changed[:50]:
                        z.write(os.path.join(workdir, f), f)
                buf.seek(0)
                await message.channel.send(
                    f"📦 {len(changed)} file(s) from this task:",
                    file=discord.File(buf, f"vibe-{message.id}.zip"))
            except Exception as e:
                print(f"zip send failed: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Tasks(bot))
