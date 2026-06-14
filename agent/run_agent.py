from __future__ import annotations

import ast
import json
import sqlite3
from pathlib import Path
from typing import Any

from agent.author import author_check
from agent.diagnose import diagnose
from agent.sandbox import backtest
from agent.validate import validate_code
from engine import checks, reference
from engine.models import Record, Verdict
from store import db


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_batch() -> list[Record]:
    with (DATA_DIR / "sample_records.json").open("r", encoding="utf-8") as handle:
        return [Record.from_json(row) for row in json.load(handle)]


def _load_novel() -> Record:
    with (DATA_DIR / "novel_record.json").open("r", encoding="utf-8") as handle:
        return Record.from_json(json.load(handle))


def _seed(conn: sqlite3.Connection) -> None:
    for record in _load_batch():
        db.insert_record(conn, record)
    for family, name, _fn in checks.CHECKS:
        db.register_check(
            conn,
            family,
            name,
            created_by="human",
            status="active",
        )


def _reference_snapshot() -> dict[str, Any]:
    return {
        "AMENDMENT_INDEX": {
            "|".join(key): value for key, value in reference.AMENDMENT_INDEX.items()
        },
        "AS_OF": reference.AS_OF,
        "CUSIP_MAP": dict(reference.CUSIP_MAP),
        "FEED_STATUS": dict(reference.FEED_STATUS),
        "FX": dict(reference.FX),
        "PRICE_FEED": {
            "|".join(key): value for key, value in reference.PRICE_FEED.items()
        },
    }


def _unknown_reason(record: Record) -> str:
    price = reference.PRICE_FEED[(record.ticker, record.as_of_date)]
    estimate = record.shares * price
    ratio = record.value_usd / estimate
    return (
        f"this value is {ratio:,.0f}x the independent estimate "
        "— no existing check explains it; sending to the agent"
    )


def _function_name(check_code: str) -> str:
    tree = ast.parse(check_code)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return node.name
    raise ValueError("proposal has no check function")


def _print_summary(proposal_id: int, proposal: dict[str, Any], gate: dict[str, Any]) -> None:
    caught = "1/1" if gate.get("caught_novel") else "0/1"
    gate_word = "PASS" if gate.get("gate") else "FAIL"
    print(f"proposal #{proposal_id}")
    print()
    print("diagnosis:")
    print(proposal["diagnosis"])
    print()
    print("new check:")
    for line in proposal["check_code"].splitlines():
        print("+ " + line)
    print()
    print(
        f"backtest: replayed {gate['records_replayed']} · caught {caught} · "
        f"{gate['false_positives']} false alarms · gate {gate_word}"
    )


def _save_proposal(
    conn: sqlite3.Connection,
    proposal: dict[str, Any],
    gate: dict[str, Any],
    status: str,
) -> int:
    saved = dict(proposal)
    saved["gate"] = gate
    return db.insert_proposal(conn, saved, status=status)


def propose() -> dict[str, Any]:
    conn = db.init_db()
    try:
        _seed(conn)
        record = _load_novel()
        snapshot = _reference_snapshot()
        reason = _unknown_reason(record)
        diagnosis = diagnose(record.model_dump(mode="json"), reason, snapshot)
        proposal = author_check(record.model_dump(mode="json"), diagnosis, snapshot)

        ok, why = validate_code(proposal["check_code"])
        if not ok:
            gate = {
                "gate": False,
                "caught_novel": False,
                "false_positives": 0,
                "per_record": {"validation": why},
                "records_replayed": 0,
            }
            proposal_id = _save_proposal(conn, proposal, gate, "rejected")
            print(f"proposal #{proposal_id}")
            print("status: rejected")
            print(f"validation: {why}")
            return {"proposal_id": proposal_id, "gate": gate}

        gate = backtest(proposal["check_code"])
        proposal_id = _save_proposal(conn, proposal, gate, "pending")
        _print_summary(proposal_id, proposal, gate)
        return {"proposal_id": proposal_id, "gate": gate}
    finally:
        conn.close()


def _run_saved_check(record: Record, check_code: str) -> Verdict:
    namespace: dict[str, Any] = {"Verdict": Verdict}
    exec(check_code, namespace)
    fn = namespace[_function_name(check_code)]
    return fn(record, reference)


def approve(proposal_id: int) -> dict[str, Any]:
    conn = db.connect()
    try:
        proposal = db.get_proposal(conn, proposal_id)
        if proposal is None:
            print(f"proposal #{proposal_id}: not found")
            return {"approved": False, "reason": "proposal not found"}
        gate = proposal["gate"]
        if not gate.get("gate"):
            print(f"proposal #{proposal_id}: not approved; saved gate did not pass")
            return {"approved": False, "reason": "saved gate did not pass"}

        before = db.count(conn, "checks")
        db.register_check(
            conn,
            "currency",
            _function_name(proposal["check_code"]),
            created_by="agent",
            status="active",
        )
        db.set_proposal_status(conn, proposal_id, "approved")
        after = db.count(conn, "checks")

        record = _load_novel()
        db.insert_record(conn, record)
        verdict = _run_saved_check(record, proposal["check_code"])
        tag = verdict.evidence.get("tag", "WRONG UNITS")
        clean_reason = verdict.reason
        if clean_reason.startswith(tag + ": "):
            clean_reason = clean_reason[len(tag) + 2 :]
        print()
        print(f"r8 Samsung: {verdict.outcome.upper()} · {tag} — {clean_reason}")
        print(f"check library: {before} -> {after}")
        return {
            "approved": True,
            "outcome": verdict.outcome,
            "reason": clean_reason,
            "tag": tag,
            "library": {"before": before, "after": after},
        }
    finally:
        conn.close()


if __name__ == "__main__":
    result = propose()
    if result["gate"].get("gate"):
        approve(int(result["proposal_id"]))
