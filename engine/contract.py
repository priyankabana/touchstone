from __future__ import annotations

from typing import Any

SOURCE_CONTRACTS = {
    "sec_13f": {
        "identity": "cusip",
        "value": "shares * price within 2%",
        "amendment": "13F-HR/A supersedes 13F-HR by filer + period",
    },
    "finra_trace": {
        "freshness": "daily",
    },
    "krx_adapter": {
        "units": "values are in KRW",
    },
    "news_claim": {
        "proof": "a headline's claimed figure must match the official filing",
    },
}


def source_family(source: str) -> str:
    suffix = "_synthetic"
    if source.endswith(suffix):
        return source[: -len(suffix)]
    return source


def get_contract(source: str) -> dict[str, Any]:
    family = source_family(source)
    return SOURCE_CONTRACTS.get(
        family,
        {"fallback": "no trusted source contract; hold unless another rule proves it"},
    )
