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

`engine.run_task()` shells out to `opencode run -m <model> --dir <sandbox> --format json "<task>"`. Opencode gets full edit/bash powers **only inside that sandbox** (`opencode.json` with `"*": "allow"` is written per-task dir). Secrets from `.env` are redacted from anything the bot prints.

## Files

- `bot.py` — thin launcher, loads cogs
- `cogs/tasks.py` — ping-to-build (opencode agent → reply + zip)
- `cogs/shell.py` — `!run !up !down !ps !logs`
- `cogs/files.py` — `!zip !get !files`
- `cogs/general.py` — `!help !ping !model`
- `core/engine.py` — opencode runner, sandboxing, secret redaction
- `core/supervisor.py` — background procs
- `core/helpers.py` — admin checks, chunked sends
- `config/settings.py` — env loading (one place)

## Safety notes

- `!run`/`!up`/opencode tasks = code execution. Admins only by default (`ADMIN_IDS` + server admins).
- Never run this on shared hosting. Never commit `.env`.
