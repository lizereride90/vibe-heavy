"""OpenCode engine: runs `opencode run` headless, parses JSON events.

Model defaults to opencode/muse-spark-1.3-contributor-free (same one this
session runs on). Auth comes from OPENCODE_API_KEY in .env (the zai key) —
written to a local auth file on first boot, never committed.
"""
import asyncio
import json
import os

MODEL = os.getenv("OPENCODE_MODEL", "opencode/muse-spark-1.3-contributor-free")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SANDBOX = os.path.join(ROOT, "sandbox")

OPENCODE_JSON = {
    "$schema": "https://opencode.ai/config.json",
    "model": MODEL,
    "permission": {"*": "allow"},
}

_secrets: list[str] = []


def load_secrets():
    vals = []
    for k in ("DISCORD_TOKEN", "OPENCODE_API_KEY", "GITHUB_TOKEN"):
        v = os.getenv(k, "")
        if len(v) > 12:
            vals.append(v)
            # also mask tail-half in case output truncates it
            vals.append(v[-16:])
    global _secrets
    _secrets = sorted(set(vals), key=len, reverse=True)


def redact(text: str) -> str:
    if not _secrets:
        load_secrets()
    for s in _secrets:
        if s and s in text:
            text = text.replace(s, "***")
    return text


def ensure_auth():
    """Write opencode auth file from env so `opencode run` just works."""
    load_secrets()
    key = os.getenv("OPENCODE_API_KEY", "")
    if not key:
        print("engine: no OPENCODE_API_KEY in .env — opencode calls will fail until you add it.")
        return
    import pathlib
    # default location: ~/.local/share/opencode/auth.json
    auth = pathlib.Path(os.path.expanduser("~/.local/share/opencode/auth.json"))
    try:
        cur = json.loads(auth.read_text()) if auth.exists() else {}
    except Exception:
        cur = {}
    if cur.get("zai", {}).get("key") == key:
        return
    cur["zai"] = {"type": "api", "key": key}
    auth.parent.mkdir(parents=True, exist_ok=True)
    auth.write_text(json.dumps(cur))
    try:
        os.chmod(auth, 0o600)
    except Exception:
        pass
    print("engine: opencode auth ready.")


def sandbox_for(guild_id, user_id) -> str:
    d = os.path.join(SANDBOX, str(guild_id), str(user_id))
    os.makedirs(d, exist_ok=True)
    cfg = os.path.join(d, "opencode.json")
    if not os.path.exists(cfg):
        with open(cfg, "w") as f:
            json.dump({**OPENCODE_JSON, "model": os.getenv("OPENCODE_MODEL", MODEL)}, f, indent=2)
    return d


def safe_path(rel: str):
    """Resolve rel inside SANDBOX only. Returns abspath or None on escape."""
    base = os.path.realpath(SANDBOX)
    p = os.path.realpath(os.path.join(base, rel.lstrip("/")))
    if p != base and not p.startswith(base + os.sep):
        return None
    return p


def list_tree(rel: str) -> str:
    p = safe_path(rel)
    if not p or not os.path.exists(p):
        return "no such path (sandbox only)."
    if os.path.isfile(p):
        return p
    out = []
    for root, dirs, files in os.walk(p):
        dirs[:] = [d for d in dirs if not d.startswith(".")][:20]
        level = root.replace(p, "").count(os.sep)
        if level > 3:
            continue
        for f in sorted(files)[:40]:
            fp = os.path.join(root, f)
            out.append(f"{os.path.relpath(fp, p)} ({os.path.getsize(fp)}B)")
        if len(out) > 60:
            break
    return "```\n" + ("\n".join(out[:60]) or "(empty)") + "\n```"


async def run_shell(shell: str, timeout: int) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(
            shell, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            cwd=SANDBOX)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return f"(timed out after {timeout}s, killed)"
        return out.decode(errors="replace") or "(no output)"
    except Exception as e:
        return f"shell error: {type(e).__name__}: {e}"


async def run_task(prompt: str, workdir: str, timeout: int):
    """Run opencode headless. Returns (reply_text, changed_files rel paths)."""
    before = _snapshot(workdir)
    cmd = ["opencode", "run", "-m", os.getenv("OPENCODE_MODEL", MODEL),
           "--dir", workdir, "--format", "json", prompt]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            cwd=workdir)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return f"(opencode timed out after {timeout}s — partial work may be in the zip)", _diff(workdir, before)
        raw = out.decode(errors="replace")
    except FileNotFoundError:
        return ("opencode binary not found on this machine. install it: "
                "https://opencode.ai/docs"), []
    text, touched = _parse_json_events(raw)
    if not text:
        text = raw.strip().splitlines()[-30:]
        text = "\n".join(text)
    changed = _diff(workdir, before) + [t for t in touched if os.path.exists(os.path.join(workdir, t))]
    seen, final = set(), []
    for f in changed:
        if f not in seen and not f.startswith("."):
            seen.add(f)
            final.append(f)
    return (text.strip() or "done — check the zip.", final)


def _snapshot(workdir: str) -> dict:
    snap = {}
    for root, _, files in os.walk(workdir):
        for f in files:
            fp = os.path.join(root, f)
            try:
                snap[os.path.relpath(fp, workdir)] = (os.path.getsize(fp), int(os.path.getmtime(fp)))
            except Exception:
                pass
    return snap


def _diff(workdir: str, before: dict) -> list:
    return [rel for rel, meta in _snapshot(workdir).items() if before.get(rel) != meta][:100]


def _parse_json_events(raw: str):
    """Best-effort pull of assistant text + touched files from --format json."""
    texts, touched = [], []

    def walk(o):
        if isinstance(o, dict):
            t = o.get("type", "")
            if t in ("text",) and isinstance(o.get("text"), str):
                texts.append(o["text"])
            for k in ("filePath", "path", "filename"):
                v = o.get(k)
                if isinstance(v, str) and "/" not in v and "." in v and len(v) < 120:
                    touched.append(v)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            walk(json.loads(line))
        except Exception:
            continue
    # opencode json also nests message parts under data/part
    return "\n".join(texts).strip(), touched
