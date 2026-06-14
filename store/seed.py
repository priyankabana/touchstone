from __future__ import annotations

import json
from pathlib import Path

from engine import checks
from store import db


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_records() -> list[dict]:
    with (DATA_DIR / "sample_records.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _print_records(records: list[dict]) -> None:
    print("id  source                 filer                         entity")
    print("--  ---------------------  ----------------------------  ------------------------")
    for record in records:
        print(
            f"{record['id']:<3} "
            f"{record['source']:<21} "
            f"{record['filer'][:28]:<28} "
            f"{record['entity_name'][:24]:<24}"
        )


def seed() -> None:
    conn = db.init_db()
    try:
        records = _load_records()
        for record in records:
            db.insert_record(conn, record)

        for family, name, _fn in checks.CHECKS:
            db.register_check(
                conn,
                family,
                name,
                created_by="human",
                status="active",
            )

        _print_records(records)
        print(f"{db.count(conn, 'records')} records · {db.count(conn, 'checks')} checks")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
