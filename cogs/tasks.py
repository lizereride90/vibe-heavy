"""Ping router: opencode plans, vibe tools execute. Full NL server control.

"mute this guy" / "change #chat name to general" -> JSON actions -> run_tool.
Coding tasks -> files + zip (engine path). Plain chat -> reply.
No Gemini/Groq — opencode (muse-spark) is the only brain.
"""
import io
import os
import time
import zipfile

import discord
from discord.ext import commands

from config import settings as cfg
from core import engine, vibe_bridge as vb
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
            return
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
            await message.reply("tell me what to do — build something or run the server. `@VibeHeavy mute @spammer`")
            return

        now = time.monotonic()
        if now - self.last_used.get(message.guild.id, 0) < cfg.COOLDOWN_S:
            await message.reply("one sec — still working. try again in a bit.")
            return
        self.last_used[message.guild.id] = now

        admin = is_admin(message.author)
        workdir = engine.sandbox_for(message.guild.id, message.author.id)
        history = []
        try:
            async for m in message.channel.history(limit=12):
                if m.author.bot and m.author != me:
                    continue
                history.append(f"{m.author.display_name}: {(m.content or '')[:200]}")
            history.reverse()
        except Exception:
            pass

        tool_results: list[str] = []
        final = None
        changed: list[str] = []
        async with message.channel.typing():
            try:
                for _ in range(vb.MAX_ROUNDS):
                    prompt = vb.build_prompt(
                        task, message.author.display_name, admin,
                        message.guild.name, message.channel.name,
                        history, tool_results)
                    text, round_changed = await engine.run_task(prompt, workdir, cfg.TASK_TIMEOUT)
                    changed = round_changed or changed
                    actions = vb.extract_actions(text)
                    if not actions:
                        final = vb.final_text(text)
                        break
                    res = await vb.execute(actions, message.guild, admin,
                                           message.channel, message.author)
                    tool_results.extend(res)
                else:
                    final = "did what I could — ping me to continue."
            except Exception as e:
                await message.reply(f"brain blew up: {type(e).__name__}: {str(e)[:300]}")
                return

        # discord-action path: summarize what ran
        if tool_results and not changed:
            last = vb.final_text(final or "")
            summary = last if last and last != (final or "") else "done."
            detail = "\n".join(f"`{r}`" for r in tool_results[-8:])[:1500]
            await message.reply(f"{engine.redact(summary)[:500]}\n{engine.redact(detail)}"[:1900])
            return
        # coding path: zip new files
        if changed:
            if final:
                await message.reply(engine.redact(final)[:1800])
            try:
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    for f in changed[:50]:
                        z.write(os.path.join(workdir, f), f)
                buf.seek(0)
                await message.channel.send(
                    f"📦 {len(changed)} file(s):",
                    file=discord.File(buf, f"vibe-{message.id}.zip"))
            except Exception as e:
                print(f"zip send failed: {e}")
            return
        # chat path
        await message.reply(engine.redact(final or "done.")[:1900])


async def setup(bot: commands.Bot):
    await bot.add_cog(Tasks(bot))
