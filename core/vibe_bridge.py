"""Bridge: opencode plans Discord actions as JSON, the bot executes them.

No Gemini/Groq anywhere. opencode (muse-spark) is the planner, vibe's
vendored run_tool (core/vibe/tools.py) is the executor.

Flow per @ping task:
  1. planner prompt (compact tool catalog + task + server context)
  2. engine.run_task -> text (+ maybe files for coding tasks)
  3. extract ```json actions``` -> execute via run_tool -> results
  4. repeat (max 3 rounds) so the planner can chain: list_members -> timeout
  5. no JSON block = final reply (chat) or files (coding task)
"""
import json

from core.vibe.tools import TOOLS_SCHEMA, run_tool

MAX_ROUNDS = 3
MAX_ACTIONS = 10


def catalog() -> str:
    lines = []
    for t in TOOLS_SCHEMA:
        fn = t.get("function", {})
        name = fn.get("name", "?")
        desc = fn.get("description", "")[:120]
        params = fn.get("parameters", {}).get("properties", {}) or {}
        req = fn.get("parameters", {}).get("required", []) or []
        args = ", ".join(f"{k}{'*' if k in req else ''}" for k in params) or "none"
        lines.append(f"- {name}({args}): {desc}")
    return "\n".join(lines)


PLANNER_RULES = """You control a Discord server through TOOLS. You cannot click Discord yourself.
To act, output ONLY this (no other text):

```json
[{"tool": "<name>", "args": {...}}]
```

Rules:
- Use exact tool names and argument keys from the catalog below.
- Chain across rounds: first round list_members/list_roles/channel_info to resolve names to IDs, later rounds act. Tool results come back to you automatically.
- Reads work for everyone. Anything that changes the server needs admin — the requester line tells you (admin=true/false). If admin=false, only use read/info tools and say you can't.
- NEVER output @everyone/@here or role mentions (<@&...>). Write "everyone" plain.
- Keep nicknames <= 32 chars. Never grant administrator. Never touch @everyone or bot roles.
- When done, reply with ONLY: FINAL: <short human summary of what you did>
- If the request is NOT about Discord (chat, coding, files), do NOT emit JSON — just answer or build normally.
"""


def build_prompt(task: str, author: str, admin: bool, guild_name: str,
                 channel_name: str, history: list[str], tool_results: list[str]) -> str:
    parts = [PLANNER_RULES,
             f"Server: {guild_name} | Channel: #{channel_name} | From: {author} (admin={admin})",
             "TOOLS CATALOG:\n" + catalog()]
    if history:
        parts.append("Recent chat:\n" + "\n".join(history[-10:]))
    if tool_results:
        parts.append("PREVIOUS TOOL RESULTS (use IDs from these):\n" + "\n".join(tool_results))
    parts.append(f"REQUEST: {task}")
    return "\n\n".join(parts)


def extract_actions(text: str) -> list[dict] | None:
    """Pull a JSON action list out of planner output. None = final reply."""
    t = (text or "").strip()
    if "```json" in t:
        try:
            body = t.split("```json", 1)[1].split("```", 1)[0]
            data = json.loads(body)
            return _coerce(data)
        except Exception:
            return None
    if t.lstrip().startswith("["):
        try:
            return _coerce(json.loads(t))
        except Exception:
            return None
    return None


def _coerce(data) -> list[dict] | None:
    if not isinstance(data, list):
        return None
    valid = {t.get("function", {}).get("name") for t in TOOLS_SCHEMA}
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("tool") or item.get("name")
        args = item.get("args") or item.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        if name in valid and isinstance(args, dict):
            out.append({"tool": name, "args": args})
    return out or None


def final_text(text: str) -> str:
    t = (text or "").strip()
    if t.upper().startswith("FINAL:"):
        t = t[6:].strip()
    # strip any leftover code fences
    if "```" in t:
        t = t.split("```")[0].strip()
    return t


async def execute(actions: list[dict], guild, admin: bool, origin, author) -> list[str]:
    results = []
    for a in actions[:MAX_ACTIONS]:
        try:
            res, _roles = await run_tool(a["tool"], a["args"], guild, admin, origin, author)
            results.append(f"{a['tool']} -> {str(res)[:600]}")
        except Exception as e:
            results.append(f"{a['tool']} -> ERROR {type(e).__name__}: {str(e)[:200]}")
    return results
