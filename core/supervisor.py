"""Tiny process supervisor: !up name cmd... / !down / !ps / !logs.

Procs run detached with output to logs/<name>.log. State in procs.json
so `!ps` survives bot restarts (it re-checks pids, prunes the dead).
"""
import json
import os
import signal
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGDIR = os.path.join(ROOT, "logs")
STATE = os.path.join(ROOT, "procs.json")
os.makedirs(LOGDIR, exist_ok=True)


def _load() -> dict:
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save(d: dict):
    try:
        with open(STATE, "w") as f:
            json.dump(d, f, indent=2)
    except Exception:
        pass


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def start(name: str, cmd: str):
    name = "".join(c for c in name if c.isalnum() or c in "-_")[:32] or "job"
    d = _load()
    old = d.get(name)
    if old and _alive(old.get("pid", -1)):
        return False, f"`{name}` already running (pid {old['pid']}). `!down {name}` first."
    log = os.path.join(LOGDIR, f"{name}.log")
    lf = open(log, "ab")
    p = subprocess.Popen(cmd, shell=True, stdout=lf, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True,
                         cwd=os.path.join(ROOT, "sandbox"))
    d[name] = {"pid": p.pid, "cmd": cmd[:300], "started": int(time.time())}
    _save(d)
    return True, f"🚀 `{name}` up (pid {p.pid}). logs: `!logs {name}`"


def stop(name: str) -> str:
    d = _load()
    info = d.pop(name, None)
    _save(d)
    if not info:
        return f"no job named `{name}`."
    pid = info.get("pid", -1)
    try:
        os.killpg(pid, signal.SIGTERM)
        return f"🛑 `{name}` stopped."
    except Exception:
        return f"`{name}` was already dead."


def list_procs() -> str:
    d = _load()
    if not d:
        return "nothing running. `!up <name> <command...>` to start something."
    lines = []
    for name, info in d.items():
        pid = info.get("pid", -1)
        if not _alive(pid):
            lines.append(f"💀 `{name}` (pid {pid} dead)")
        else:
            lines.append(f"🟢 `{name}` pid {pid} — `{info.get('cmd', '')[:80]}`")
    # prune dead
    alive = {k: v for k, v in d.items() if _alive(v.get("pid", -1))}
    if len(alive) != len(d):
        _save(alive)
    return "\n".join(lines)


def tail(name: str, n: int = 40) -> str:
    log = os.path.join(LOGDIR, f"{os.path.basename(name)}.log")
    if not os.path.exists(log):
        return f"no logs for `{name}`."
    try:
        with open(log, "rb") as f:
            data = f.read()[-8000:].decode(errors="replace")
        return "\n".join(data.splitlines()[-n:]) or "(empty log)"
    except Exception as e:
        return f"log read error: {e}"
