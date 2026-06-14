from __future__ import annotations

import json
from typing import Any

import config
from agent import _llm


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _cached_proposal() -> dict[str, Any]:
    proposal = dict(_llm.load_cached())
    proposal["source"] = "cached"
    return proposal


def author_check(
    record: Any,
    diagnosis: str,
    ref_snapshot: dict[str, Any],
) -> dict[str, Any]:
    if config.OFFLINE:
        return _cached_proposal()

    prompt = (
        "You are Touchstone's check-writer. Return STRICT JSON only, with keys "
        "diagnosis, check_code, rationale, test_plan, source. The check_code must "
        "define exactly one Python function named check_currency_unit_consistency. "
        "Use plain reasons for non-experts and include the number. Do not wrap the "
        "JSON in markdown fences.\n\n"
        f"Record:\n{record}\n\n"
        f"Diagnosis:\n{diagnosis}\n\n"
        f"Reference snapshot:\n{ref_snapshot}\n"
    )
    try:
        raw = _llm.respond(prompt)
        proposal = json.loads(_strip_fences(raw))
        return {
            "diagnosis": proposal["diagnosis"],
            "check_code": proposal["check_code"],
            "rationale": proposal["rationale"],
            "test_plan": proposal["test_plan"],
            "source": proposal["source"],
        }
    except Exception:
        return _cached_proposal()
