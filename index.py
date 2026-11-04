"""Vercel entry point.

Vercel's filesystem is read-only except /tmp, and Touchstone writes its SQLite
database and result files under data/. On a cold start this copies the app into a
writable directory, runs it from there, and defaults to the offline demo (no API
key, no network calls). Locally, run `uvicorn api.main:app` as usual instead.
"""
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("OFFLINE", "1")
os.environ.setdefault("LIVE", "0")

SRC = Path(__file__).resolve().parent
RUNTIME = Path(os.environ.get("TOUCHSTONE_RUNTIME_DIR", "/tmp/touchstone"))

if not (RUNTIME / "api" / "main.py").exists():
    shutil.copytree(
        SRC,
        RUNTIME,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", ".vercel", "tests", "docs", "assets", "__pycache__", "*.pyc"),
    )

sys.path.insert(0, str(RUNTIME))
os.chdir(RUNTIME)

from api.main import app  # noqa: E402  (imported after the runtime copy on purpose)

__all__ = ["app"]
