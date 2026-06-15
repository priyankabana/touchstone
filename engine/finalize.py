from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from engine import provenance
from engine import reference as base_reference
from engine import router
from engine.models import Record, Verdict
from store import db


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CORRECTED_DATASET = DATA_DIR / "corrected_dataset.json"
CORRECTION_REPORT = DATA_DIR / "correction_report.json"
VERIFICATION_LOG = DATA_DIR / "verification_log.json"


class ReferenceView:
    def __init__(self, snapshot: dict[str, Any] | None = None) -> None:
        if snapshot is None:
            self.AS_OF = base_reference.AS_OF
            self.PRICE_FEED = base_reference.PRICE_FEED
            self.FX = base_reference.FX
            self.CUSIP_MAP = base_reference.CUSIP_MAP
            self.AMENDMENT_INDEX = base_reference.AMENDMENT_INDEX
            self.FEED_STATUS = base_reference.FEED_STATUS
            return

        self.AS_OF = str(snapshot.get("as_of_date") or base_reference.AS_OF)
        self.PRICE_FEED = dict(base_reference.PRICE_FEED)
        for ticker, price in dict(snapshot.get("prices") or {}).items():
            self.PRICE_FEED[(str(ticker), self.AS_OF)] = float(price)

        self.FX = {
            **base_reference.FX,
            **{str(currency): float(rate) for currency, rate in dict(snapshot.get("fx") or {}).items()},
        }
        self.CUSIP_MAP = {
            **base_reference.CUSIP_MAP,
            **{str(cusip): dict(value) for cusip, value in dict(snapshot.get("cusip_map") or {}).items()},
        }
        self.AMENDMENT_INDEX = _amendment_index(snapshot)
        self.FEED_STATUS = {
            **base_reference.FEED_STATUS,
            **dict(snapshot.get("feed_status") or snapshot.get("stale_feeds") or {}),
        }

    def resolve(self, cusip: str) -> dict[str, Any] | None:
        return self.CUSIP_MAP.get(cusip)


def _amendment_index(snapshot: dict[str, Any]) -> dict[tuple[str, ...], dict[str, str]]:
    index: dict[tuple[str, ...], dict[str, str]] = {}
    for row in list(snapshot.get("amendment_index") or []):
        if not isinstance(row, dict):
            continue
        filer = str(row.get("filer") or "")
        period = str(row.get("period") or snapshot.get("as_of_date") or base_reference.AS_OF)
        cusip = str(row.get("cusip") or row.get("record_id") or "")
        if filer and period and cusip:
            index[(filer, period, cusip)] = {
                "form": str(row.get("form") or "13F-HR/A"),
                "filed": str(row.get("filed") or "unknown date"),
                "accession": str(row.get("accession") or "uploaded-reference"),
            }
    for row in list(snapshot.get("amended") or []):
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            continue
        filer, period, cusip = (str(part) for part in row[:3])
        index[(filer, period, cusip)] = {
            "form": "13F-HR/A",
            "filed": "listed in uploaded reference",
            "accession": "uploaded-reference",
        }
    return index


def _load_records() -> list[Record]:
    with (DATA_DIR / "sample_records.json").open("r", encoding="utf-8") as handle:
        records = [Record.from_json(row) for row in json.load(handle)]
    with (DATA_DIR / "novel_record.json").open("r", encoding="utf-8") as handle:
        records.append(Record.from_json(json.load(handle)))
    return records


def _connect_or_seed() -> sqlite3.Connection:
    try:
        conn = db.connect()
        db.count(conn, "records")
        db.count(conn, "checks")
        return conn
    except (sqlite3.Error, ValueError):
        try:
            conn.close()  # type: ignore[possibly-undefined]
        except UnboundLocalError:
            pass
        conn, _records = router.seed_silent()
        return conn


def _apply_correction(row: dict[str, Any], correction: dict[str, Any]) -> None:
    field = correction["field"]
    new_value = correction["new_value"]
    if field == "identity":
        row.update(new_value)
        return
    row[field] = new_value


def _report_entry(record: Record, correction: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "row": record.id,
        "field": correction["field"],
        "old_value": correction["old_value"],
        "new_value": correction["new_value"],
        "why": correction["explanation"],
    }
    for key in ("currency", "fx_rate", "ratio"):
        if key in correction:
            entry[key] = correction[key]
    return entry


def _row_state(record: Record, verdict: Verdict, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.id,
        "filer": record.filer,
        "entity": row["entity_name"],
        "outcome": verdict.outcome,
        "reason": verdict.reason,
        "corrected": verdict.outcome == "fixed",
        "record": row,
    }


def process(
    records: list[Record] | None = None,
    reference_snapshot: dict[str, Any] | None = None,
    write_files: bool = True,
) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = _connect_or_seed()
    rows: list[dict[str, Any]] = []
    report: list[dict[str, Any]] = []
    verification_log: list[dict[str, Any]] = []
    summary = {"correct": 0, "auto_fixed": 0, "held_for_human": 0, "unknown": 0}
    input_records = records if records is not None else _load_records()
    ref = ReferenceView(reference_snapshot)

    try:
        for record in input_records:
            verdict = router.run_record(record, conn, ref)
            row = record.model_dump(mode="json")
            correction = verdict.evidence.get("correction")
            if verdict.outcome == "fixed" and isinstance(correction, dict):
                _apply_correction(row, correction)
                report.append(_report_entry(record, correction))
                summary["auto_fixed"] += 1
            elif verdict.outcome == "true":
                summary["correct"] += 1
            elif verdict.outcome == "held":
                summary["held_for_human"] += 1
            elif verdict.outcome == "unknown":
                summary["unknown"] += 1
            verification_log.append(provenance.trace_record(record, verdict, ref))
            rows.append(_row_state(record, verdict, row))
    finally:
        conn.close()

    corrected_rows = [row["record"] for row in rows if row["corrected"]]
    dataset = [row["record"] | {"final_status": row["outcome"].upper(), "final_reason": row["reason"]} for row in rows]

    if write_files:
        with CORRECTED_DATASET.open("w", encoding="utf-8") as handle:
            json.dump(dataset, handle, indent=2, sort_keys=True)
            handle.write("\n")
        with CORRECTION_REPORT.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
        with VERIFICATION_LOG.open("w", encoding="utf-8") as handle:
            json.dump(verification_log, handle, indent=2, sort_keys=True)
            handle.write("\n")

    return {
        "summary": summary,
        "rows": rows,
        "corrected_rows": corrected_rows,
        "report": report,
        "verification_log": verification_log,
    }


def main() -> None:
    result = process()
    summary = result["summary"]
    print(
        "finalized: "
        f"{summary['correct']} correct · "
        f"{summary['auto_fixed']} auto-fixed · "
        f"{summary['held_for_human']} held for a human · "
        f"{summary['unknown']} unknown"
    )
    for entry in result["report"]:
        print(
            f"{entry['row']} {entry['field']}: "
            f"{entry['old_value']} -> {entry['new_value']} — {entry['why']}"
        )


if __name__ == "__main__":
    main()
