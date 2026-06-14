from __future__ import annotations

import os
from pathlib import Path


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()


DEMO_TODAY = "2026-06-14"
INJECT_SEED = 42
FIXED_TIME = "T12:00:00"


def stamp() -> str:
    return DEMO_TODAY + FIXED_TIME


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


OFFLINE = _env_bool("OFFLINE", False)
LIVE = _env_bool("LIVE", True)

MODEL = "gpt-5.5"
FALLBACK_MODEL = "gpt-5.4"

EDGAR_UA = os.getenv("EDGAR_UA", "")
EDGAR_REQUEST_BUDGET = 4

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "touchstone.db"
CACHE_DIR = DATA_DIR / "live_cache"
