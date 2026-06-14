from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config


CACHED_PROPOSAL_PATH = Path(__file__).resolve().parent.parent / "proposals" / "cached_proposal.json"


def load_cached() -> dict[str, Any]:
    with CACHED_PROPOSAL_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _model_not_found(error: Exception) -> bool:
    text = str(error).lower()
    return (
        "model_not_found" in text
        or "model not found" in text
        or "does not exist" in text
    )


def _response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return str(text)
    if isinstance(response, dict):
        output_text = response.get("output_text")
        if output_text:
            return str(output_text)
    return str(response)


def respond(prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(timeout=12.0, max_retries=1)
    try:
        response = client.responses.create(model=config.MODEL, input=prompt)
    except Exception as error:
        if not _model_not_found(error):
            raise
        response = client.responses.create(model=config.FALLBACK_MODEL, input=prompt)
    return _response_text(response)
