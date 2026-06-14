from __future__ import annotations

from typing import Any


AS_OF = "2026-03-31"

DEMO_PICKS = [
    "037833100",
    "594918104",
    "852234103",
    "67066G104",
    "191216100",
]

PRICE_FEED = {
    ("AAPL", AS_OF): 193.45,
    ("MSFT", AS_OF): 415.20,
    ("XYZ", AS_OF): 62.50,
    ("NVDA", AS_OF): 905.50,
    ("KO", AS_OF): 62.30,
    ("005930.KS", AS_OF): 52.00,
}

FX = {
    "KRW": 1302.0,
    "JPY": 154.0,
    "INR": 83.5,
}

CUSIP_MAP: dict[str, dict[str, Any]] = {
    "037833100": {"name": "Apple Inc.", "ticker": "AAPL"},
    "594918104": {"name": "Microsoft Corporation", "ticker": "MSFT"},
    "852234103": {
        "name": "Block, Inc.",
        "ticker": "XYZ",
        "former": {"ticker": "SQ", "retired": "2025-01-21"},
    },
    "67066G104": {"name": "NVIDIA Corporation", "ticker": "NVDA"},
    "191216100": {"name": "The Coca-Cola Company", "ticker": "KO"},
}

AMENDMENT_INDEX = {
    ("Renaissance Technologies LLC", AS_OF): {
        "form": "13F-HR/A",
        "filed": "2026-05-21",
        "accession": "0001037389-26-000XXX",
    }
}

FEED_STATUS = {
    "finra_trace": {
        "last_new_record": "2026-06-08",
        "expected_cadence_days": 1,
        "http_status": 200,
    }
}


def resolve(cusip: str) -> dict[str, Any] | None:
    return CUSIP_MAP.get(cusip)


def _self_check() -> None:
    apple_value = 250_000 * PRICE_FEED[("AAPL", AS_OF)]
    assert abs(apple_value - 48_400_000) / 48_400_000 < 0.02

    samsung_usd = 130_000 * PRICE_FEED[("005930.KS", AS_OF)]
    samsung_krw = samsung_usd * FX["KRW"]
    assert samsung_krw / samsung_usd == 1302


if __name__ == "__main__":
    _self_check()
    print("reference OK")
