from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import router  # noqa: E402


def _records_by_id() -> dict[str, object]:
    conn, records = router.seed_silent()
    try:
        novel = router.load_novel()
        rows = records + [novel]
        return {record.id: record for record in rows}
    finally:
        conn.close()


def verify(record_id: str) -> dict[str, object]:
    records = _records_by_id()
    if record_id not in records:
        raise SystemExit(
            "unknown record id "
            + record_id
            + "; try one of "
            + ", ".join(sorted(records))
        )

    conn, _seeded_records = router.seed_silent()
    try:
        record = records[record_id]
        verdict = router.run_record(record, conn)
        return {
            "record_id": record.id,
            "company": record.entity_name,
            "filer": record.filer,
            "status": verdict.outcome.upper(),
            "reason": verdict.reason,
            "audit": verdict.evidence.get("correction") or verdict.evidence,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Touchstone record end-to-end.")
    parser.add_argument("record_id", nargs="?", default="r3")
    args = parser.parse_args()
    print(json.dumps(verify(args.record_id), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

