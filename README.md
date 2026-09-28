# Vibe Heavy 💪

Separate beast from [vibe-bot](https://github.com/lizereride90/vibe-bot). That one runs 24/7 on Discloud. **This one runs on YOUR machine** (phone/PC/VPS) with literal OpenCode inside — model `muse-spark-1.3-contributor-free`. Not 24/7, but powerful.

> made by Ji-young (ji-eun) with @y.o.r.u.zekai

## What it does

- `@VibeHeavy make me a todo website` → opencode agent builds it in `sandbox/<server>/<you>/`, bot replies + sends a **zip** of the files
- `!run <cmd>` → shell in the sandbox (admins only, 60s cap)
- `!up <name> <cmd>` → keep stuff running in background (mini pm2)
- `!down <name>` / `!ps` / `!logs <name>` → manage background stuff
- `!zip <path>` / `!get <path>` / `!files` → send folders/files (admins only)
- `!help` → command list

## Setup (your machine)

Needs: Python 3.10+, [opencode](https://opencode.ai/docs) installed + logged in.

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in DISCORD_TOKEN, ADMIN_IDS, OPENCODE_API_KEY (your zai key)
python bot.py
```

Discord portal: enable `MESSAGE CONTENT INTENT`, invite with `bot` scope (Send Messages + Attach Files).

## How the AI works

`@ping` goes through `core/vibe_bridge.py`: opencode (muse-spark) **plans** Discord actions as JSON, the bot **executes** them with vibe's full toolset (`core/vibe/tools.py` — same 100+ tools as vibe-bot: members, roles, channels, mod, voice, polls, tickets, giveaways, triggers, welcome...). Multi-round chaining (lookup → act), max 3 rounds. Coding tasks build files + zip instead. No Gemini/Groq anywhere.

- `cogs/vibe.py` — passive life: welcome/goodbye, autorole, member counter, reaction roles, first-🎉 giveaway wins + watchdog auto-mod scan (Gemini, passive messages only)

## Files

- `bot.py` — thin launcher, loads cogs
- `cogs/tasks.py` — ping-to-build (opencode agent → reply + zip)
- `cogs/shell.py` — `!run !up !down !ps !logs`
- `cogs/files.py` — `!zip !get !files`
- `cogs/general.py` — `!help !ping !model`
- `cogs/mod.py` — vibe's Discord kit: `!purge !timeout !kick !ban !unban !warn !nick !role !slowmode !lock !avatar !whois !server`
- `core/engine.py` — opencode runner, sandboxing, secret redaction
- `core/supervisor.py` — background procs
- `core/helpers.py` — admin checks, chunked sends
- `config/settings.py` — env loading (one place)

## Safety notes

- `!run`/`!up`/opencode tasks = code execution. Admins only by default (`ADMIN_IDS` + server admins).
- Never run this on shared hosting. Never commit `.env`.
