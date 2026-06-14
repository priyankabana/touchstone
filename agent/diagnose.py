from __future__ import annotations

from typing import Any

import config
from agent import _llm


def _cached_diagnosis() -> str:
    return str(_llm.load_cached()["diagnosis"])


def diagnose(record: Any, reason: str, ref_snapshot: dict[str, Any]) -> str:
    if config.OFFLINE:
        return _cached_diagnosis()

    prompt = (
        "You are Touchstone's data-check diagnostician. Explain the root cause "
        "in one plain-English paragraph for a smart non-expert.\n\n"
        f"Record:\n{record}\n\n"
        f"Current reason:\n{reason}\n\n"
        f"Reference snapshot:\n{ref_snapshot}\n\n"
        "Return only the diagnosis paragraph."
    )
    try:
        return _llm.respond(prompt).strip()
    except Exception:
        return _cached_diagnosis()
