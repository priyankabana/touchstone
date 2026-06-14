from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config
from engine import reference
from ingest import edgar


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

BLACKROCK_ACCESSION = "0001364742-26-000001"
RENAISSANCE_ACCESSION = "0001037389-26-000001"
CITADEL_ACCESSION = "0001423053-26-000001"
VANGUARD_ACCESSION = "0000102909-26-000001"
BERKSHIRE_ACCESSION = "0001067983-26-000001"


def _pinned_rows() -> dict[str, dict[str, Any]]:
    filing, _provenance = edgar.infotable(1037389, "pinned")
    return {row["cusip"]: row for row in filing["rows"]}


def _record(
    *,
    record_id: str,
    source: str,
    filer: str,
    form: str,
    period: str,
    as_of_date: str,
    entity_name: str,
    ticker: str,
    cusip: str,
    shares: int,
    value_usd: float,
    price: float | None,
    accession: str | None,
    claimed_value: float | None = None,
    headline: str | None = None,
) -> dict[str, Any]:
    record = {
        "accession": accession,
        "as_of_date": as_of_date,
        "claimed_value": claimed_value,
        "cusip": cusip,
        "entity_name": entity_name,
        "filer": filer,
        "form": form,
        "id": record_id,
        "period": period,
        "price": price,
        "shares": shares,
        "source": source,
        "ticker": ticker,
        "value_usd": value_usd,
    }
    if headline is not None:
        record["headline"] = headline
    return record


def _filing_record(
    *,
    record_id: str,
    filer: str,
    row: dict[str, Any],
    accession: str,
    entity_name: str | None = None,
    ticker: str | None = None,
) -> dict[str, Any]:
    return _record(
        record_id=record_id,
        source="sec_13f",
        filer=filer,
        form="13F-HR",
        period=reference.AS_OF,
        as_of_date=reference.AS_OF,
        entity_name=entity_name or row["name"],
        ticker=ticker or row["ticker"],
        cusip=row["cusip"],
        shares=row["shares"],
        value_usd=row["value_usd"],
        price=row["price"],
        accession=accession,
    )


def build_records() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    rows = _pinned_rows()

    apple = rows["037833100"]
    microsoft = rows["594918104"]
    block = rows["852234103"]
    nvidia = rows["67066G104"]
    coca_cola = rows["191216100"]
    samsung = rows["KR7005930003"]

    batch = [
        _filing_record(
            record_id="r1",
            filer="BlackRock Inc.",
            row=apple,
            accession=BLACKROCK_ACCESSION,
        ),
        _filing_record(
            record_id="r2",
            filer="Renaissance Technologies LLC",
            row=microsoft,
            accession=RENAISSANCE_ACCESSION,
        ),
        _filing_record(
            record_id="r3",
            filer="Citadel Advisors LLC",
            row=block,
            accession=CITADEL_ACCESSION,
            entity_name="Square, Inc.",
            ticker="SQ",
        ),
        _record(
            record_id="r4",
            source="finra_trace_synthetic",
            filer="FINRA TRACE",
            form="TRACE",
            period="2026-06-08",
            as_of_date="2026-06-08",
            entity_name="Apple Inc. 3.85% 2043",
            ticker="AAPL.BOND",
            cusip="037833AJ9",
            shares=1,
            value_usd=1_012_500.0,
            price=1_012_500.0,
            accession=None,
        ),
        _filing_record(
            record_id="r5",
            filer="Vanguard Group Inc.",
            row=nvidia,
            accession=VANGUARD_ACCESSION,
        ),
        _filing_record(
            record_id="r6",
            filer="Berkshire Hathaway Inc.",
            row=coca_cola,
            accession=BERKSHIRE_ACCESSION,
        ),
        _record(
            record_id="r7",
            source="news_claim",
            filer="BlackRock Inc.",
            form="NEWS",
            period=reference.AS_OF,
            as_of_date=reference.AS_OF,
            entity_name="Apple Inc.",
            ticker="AAPL",
            cusip="037833100",
            shares=0,
            value_usd=0.0,
            price=None,
            accession=None,
            claimed_value=500_000_000.0,
            headline="BlackRock holds $500M in Apple",
        ),
    ]

    novel = _record(
        record_id="r8",
        source="krx_adapter",
        filer="NPS Korea",
        form="KRX",
        period=reference.AS_OF,
        as_of_date=reference.AS_OF,
        entity_name=samsung["name"],
        ticker="005930.KS",
        cusip="KR7005930003",
        shares=130_000,
        value_usd=130_000 * 52.00 * reference.FX["KRW"],
        price=52.00,
        accession=None,
    )

    source_filings = [
        BLACKROCK_ACCESSION,
        RENAISSANCE_ACCESSION,
        CITADEL_ACCESSION,
        VANGUARD_ACCESSION,
        BERKSHIRE_ACCESSION,
    ]
    line = (
        f"INJECTION LOG · seed {config.INJECT_SEED} · real rows: 6 of 8 · "
        "changed fields: 2 · made-up rows: 2 · source filings: "
        + ", ".join(source_filings)
    )
    log = {
        "changed_fields": [
            {"field": "ticker", "from": "XYZ", "record": "r3", "to": "SQ"},
            {
                "field": "entity_name",
                "from": "Block, Inc.",
                "record": "r3",
                "to": "Square, Inc.",
            },
        ],
        "line": line,
        "made_up_rows": ["r4", "r7"],
        "real_rows": ["r1", "r2", "r3", "r5", "r6", "r8"],
        "seed": config.INJECT_SEED,
        "source_filings": source_filings,
    }
    return batch, novel, log


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_outputs() -> str:
    batch, novel, log = build_records()
    _write_json(DATA_DIR / "sample_records.json", batch)
    _write_json(DATA_DIR / "novel_record.json", novel)
    _write_json(DATA_DIR / "injection_log.json", log)
    return log["line"]


if __name__ == "__main__":
    print(write_outputs())
