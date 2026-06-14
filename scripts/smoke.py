import sys
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config


def _model_not_found(error):
    text = str(error).lower()
    return (
        "model_not_found" in text
        or "model not found" in text
        or "does not exist" in text
    )


def _response_text(response):
    text = getattr(response, "output_text", None)
    if text:
        return str(text)
    return str(response)


def _call(model):
    from openai import OpenAI

    client = OpenAI(timeout=12.0, max_retries=1)
    response = client.responses.create(
        model=model,
        input="Reply with exactly one word: ready",
    )
    return _response_text(response)


def main():
    if config.OFFLINE:
        print("offline — skipping")
        return 0

    model = config.MODEL
    try:
        text = _call(model)
    except Exception as error:
        if not _model_not_found(error):
            raise
        model = config.FALLBACK_MODEL
        text = _call(model)

    if "ready" not in text.strip().lower():
        print(f"FAIL — {model} answered {text!r}")
        return 1
    print(f"{model} answered ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
