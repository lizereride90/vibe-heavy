"""Vibe Heavy — local-first Discord bot with literal OpenCode inside.

You run this on YOUR machine (phone/PC/VPS), not on Discloud.
- @ping <task>  -> OpenCode agent (muse-spark) builds it in a sandbox, bot replies + zips the result
- !run <cmd>    -> sandboxed shell exec (admins only)
- !up/!down/!ps/!logs -> background process supervisor (keep stuff running)
- !zip <path> / !get <path> -> send folders/files as attachments (admins only)

Everything opencode touches lives under ./sandbox/<guild>/<user>/ — never the repo root.
"""
import asyncio
import io
import os
import time
import zipfile

import discord
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")
MODEL = os.getenv("OPENCODE_MODEL", "opencode/muse-spark-1.3-contributor-free")
ADMIN_IDS = {x.strip() for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
TASK_TIMEOUT = int(os.getenv("TASK_TIMEOUT", "600"))
RUN_TIMEOUT = int(os.getenv("RUN_TIMEOUT", "60"))

import engine
import supervisor as sup

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
last_used: dict[int, float] = {}


def is_admin(m: discord.Member) -> bool:
    if m.guild_permissions.administrator:
        return True
    return str(m.id) in ADMIN_IDS or str(m.name) in ADMIN_IDS


async def chunked_send(ch, text: str):
    text = text or "(empty reply)"
    for i in range(0, len(text), 1900):
        await ch.send(text[i:i + 1900])


@client.event
async def on_ready():
    print(f"Heavy online as {client.user} ({client.user.id}) in {len(client.guilds)} servers | model={MODEL}")
    await client.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, name="@me + task | !help"))


@client.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    me = client.user
    body = message.content.strip()

    # ---- prefix commands ----
    if body.startswith("!"):
        await handle_cmd(message, body[1:].strip())
        return

    # ---- ping the bot -> opencode task ----
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

    task = body
    for m in message.mentions:
        task = task.replace(f"<@{m.id}>", "").replace(f"<@!{m.id}>", "")
    task = task.strip()
    if not task:
        await message.reply("tell me what to build. `@VibeHeavy make me a todo website`")
        return

    now = time.monotonic()
    if now - last_used.get(message.guild.id, 0) < 10:
        await message.reply("one sec — still working. try again in a bit.")
        return
    last_used[message.guild.id] = now

    admin = is_admin(message.author)
    workdir = engine.sandbox_for(message.guild.id, message.author.id)
    prompt = ("You are VibeHeavy, an expert coding agent inside a Discord bot. "
              "Build exactly what is asked. Write real runnable files, no placeholders. "
              f"Requester is {'an ADMIN' if admin else 'a normal user'}.\n\nTASK: {task}")
    async with message.channel.typing():
        try:
            text, changed = await engine.run_task(prompt, workdir, TASK_TIMEOUT)
        except Exception as e:
            await message.reply(f"opencode blew up: {type(e).__name__}: {str(e)[:300]}")
            return
    reply = engine.redact(text)[:1800]
    await message.reply(reply or "done.")
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


async def handle_cmd(message: discord.Message, cmd: str):
    parts = cmd.split()
    if not parts:
        return
    c, args = parts[0].lower(), parts[1:]
    admin = is_admin(message.author)

    if c == "help":
        await message.reply(
            "**VibeHeavy** (runs here, not 24/7)\n"
            "`@me <task>` — build anything (website, bot, script) → replies + zip\n"
            "`!run <cmd>` `!up <name> <cmd>` `!down <name>` `!ps` `!logs <name>` (admin)\n"
            "`!zip <path>` `!get <path>` `!files [path]` (admin)")
        return

    if c in ("run", "up", "down", "ps", "logs", "zip", "get", "files") and not admin:
        await message.reply("admins only, gng.")
        return

    if c == "run":
        shell = cmd[3:].strip()
        if not shell:
            await message.reply("usage: `!run <shell command>`")
            return
        async with message.channel.typing():
            out = await engine.run_shell(shell, RUN_TIMEOUT)
        await chunked_send(message.channel, f"```\n{engine.redact(out)[-1800:]}\n```")
        return

    if c == "up":
        if len(args) < 2:
            await message.reply("usage: `!up <name> <command...>`")
            return
        ok, msg = sup.start(args[0], " ".join(args[1:]))
        await message.reply(msg)
        return

    if c == "down":
        if not args:
            await message.reply("usage: `!down <name>`")
            return
        await message.reply(sup.stop(args[0]))
        return

    if c == "ps":
        await message.reply(sup.list_procs())
        return

    if c == "logs":
        if not args:
            await message.reply("usage: `!logs <name>`")
            return
        await chunked_send(message.channel, f"```\n{sup.tail(args[0])[-1800:]}\n```")
        return

    if c == "files":
        rel = args[0] if args else "."
        await message.reply(engine.list_tree(rel))
        return

    if c == "get":
        if not args:
            await message.reply("usage: `!get <path>`")
            return
        p = engine.safe_path(args[0])
        if not p or not os.path.isfile(p):
            await message.reply("no such file (sandbox only).")
            return
        if os.path.getsize(p) > 24 * 1024 * 1024:
            await message.reply("too big (>24MB).")
            return
        await message.channel.send(file=discord.File(p, os.path.basename(p)))
        return

    if c == "zip":
        if not args:
            await message.reply("usage: `!zip <path>`")
            return
        p = engine.safe_path(args[0])
        if not p or not os.path.exists(p):
            await message.reply("no such path (sandbox only).")
            return
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            if os.path.isfile(p):
                z.write(p, os.path.basename(p))
            else:
                for root, _, files in os.walk(p):
                    for f in files[:500]:
                        fp = os.path.join(root, f)
                        z.write(fp, os.path.relpath(fp, p))
        buf.seek(0)
        await message.channel.send("📦 here:", file=discord.File(buf, "vibe.zip"))
        return


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in .env")
    engine.ensure_auth()
    client.run(TOKEN)
