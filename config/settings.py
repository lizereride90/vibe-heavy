"""Central settings — every cog reads from here. Fill .env, never commit it."""
import os

from dotenv import load_dotenv

load_dotenv()

TOKEN: str = os.getenv("DISCORD_TOKEN", "")
MODEL: str = os.getenv("OPENCODE_MODEL", "opencode/muse-spark-1.3-contributor-free")
ADMIN_IDS: set[str] = {x.strip() for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
TASK_TIMEOUT: int = int(os.getenv("TASK_TIMEOUT", "600"))
RUN_TIMEOUT: int = int(os.getenv("RUN_TIMEOUT", "60"))
PREFIX: str = os.getenv("PREFIX", "!")
COOLDOWN_S: int = int(os.getenv("COOLDOWN_S", "10"))
