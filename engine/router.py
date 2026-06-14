from __future__ import annotations

import ast
import json
import sqlite3
from pathlib import Path
from typing import Any

from engine import checks, correct, reference
from engine.models import Record, Verdict
from store import db


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SPECIFICITY = [
    "check_supersession",
    "check_identity",
    "check_freshness",
    "check_claim_matches_source",
    "check_value_reconciles",
    "check_structural",
]


def _function_name(check_code: str) -> str:
    tree = ast.parse(check_code)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return node.name
    raise ValueError("proposal has no check function")


def _load_records(path: Path) -> list[Record]:
    with path.open("r", encoding="utf-8") as handle:
        rows = json.load(handle)
    return [Record.from_json(row) for row in rows]


def _load_record(path: Path) -> Record:
    with path.open("r", encoding="utf-8") as handle:
        return Record.from_json(json.load(handle))


def _ratio_text(ratio: float) -> str:
    if ratio == int(ratio):
        return f"{int(ratio):,}"
    return f"{ratio:,.1f}"


def _save_check_verdicts(
    record: Record,
    conn: sqlite3.Connection,
    ref: Any = reference,
) -> list[Verdict]:
    verdicts: list[Verdict] = []
    for _family, _name, fn in checks.CHECKS:
        verdict = fn(record, ref)
        verdict_id = db.insert_verdict(conn, record.id, verdict)
        db.insert_evidence(conn, verdict_id, verdict.evidence)
        verdicts.append(verdict)
    for verdict in _agent_verdicts(record, conn, ref):
        verdict_id = db.insert_verdict(conn, record.id, verdict)
        db.insert_evidence(conn, verdict_id, verdict.evidence)
        verdicts.append(verdict)
    return verdicts


def _approved_agent_codes(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    active_agent_names = {
        row["name"]
        for row in db.active_checks(conn)
        if row.get("created_by") == "agent" and row.get("status") == "active"
    }
    if not active_agent_names:
        return []
    rows = conn.execute(
        """
        SELECT check_code
        FROM proposals
        WHERE status = ?
        ORDER BY id
        """,
        ("approved",),
    ).fetchall()
    codes: list[tuple[str, str]] = []
    for row in rows:
        check_code = str(row["check_code"])
        name = _function_name(check_code)
        if name in active_agent_names:
            codes.append((name, check_code))
    return codes


def _agent_verdicts(record: Record, conn: sqlite3.Connection, ref: Any = reference) -> list[Verdict]:
    verdicts: list[Verdict] = []
    for name, check_code in _approved_agent_codes(conn):
        namespace: dict[str, Any] = {"Verdict": Verdict}
        exec(check_code, namespace)
        fn = namespace[name]
        if not callable(fn):
            continue
        verdict = fn(record, ref)
        if isinstance(verdict, Verdict):
            verdicts.append(verdict)
        else:
            verdicts.append(Verdict.model_validate(verdict))
    return verdicts


def _record_exists(conn: sqlite3.Connection, record_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM records WHERE id = ?",
        (record_id,),
    ).fetchone()
    return row is not None


def _combine(verdicts: list[Verdict]) -> Verdict:
    by_name = {verdict.check_name: verdict for verdict in verdicts}
    held = {
        verdict.check_name: verdict
        for verdict in verdicts
        if verdict.outcome == "held"
    }
    reconcile = by_name.get("check_value_reconciles")
    if reconcile and reconcile.outcome == "held":
        ratio = float(reconcile.evidence.get("ratio") or 0.0)
        explained = any(
            verdict.evidence.get("tag") == "WRONG UNITS"
            for verdict in held.values()
        )
        if ratio >= 50 and not explained:
            return Verdict(
                outcome="unknown",
                confidence=1.0,
                reason=(
                    f"this value is {_ratio_text(ratio)}x the independent estimate "
                    "— no existing check explains it; sending to the agent"
                ),
                evidence={
                    "ratio": ratio,
                    "source_check": "check_value_reconciles",
                },
                check_name="router",
            )

    wrong_units = [
        verdict for verdict in held.values() if verdict.evidence.get("tag") == "WRONG UNITS"
    ]
    if wrong_units:
        chosen = wrong_units[0]
        return Verdict(
            outcome="held",
            confidence=chosen.confidence,
            reason=chosen.reason,
            evidence=chosen.evidence,
            check_name=chosen.check_name,
        )

    for check_name in SPECIFICITY:
        if check_name in held:
            chosen = held[check_name]
            return Verdict(
                outcome="held",
                confidence=chosen.confidence,
                reason=chosen.reason,
                evidence=chosen.evidence,
                check_name=chosen.check_name,
            )

    return Verdict(
        outcome="true",
        confidence=1.0,
        reason="all checks passed; this value is proven by the current check library.",
        evidence={"checks_run": len(verdicts)},
        check_name="router",
    )


def _apply_correction(record: Record, verdict: Verdict, ref: Any = reference) -> Verdict:
    if verdict.outcome != "held":
        return verdict

    correction = correct.correct_record(record, verdict, ref)
    if correction.get("fixed"):
        evidence = dict(verdict.evidence)
        evidence["correction"] = correction
        return Verdict(
            outcome="fixed",
            confidence=verdict.confidence,
            reason=str(correction["explanation"]),
            evidence=evidence,
            check_name=verdict.check_name,
        )

    reason = str(correction.get("reason") or verdict.reason)
    evidence = dict(verdict.evidence)
    evidence["correction"] = correction
    return Verdict(
        outcome="held",
        confidence=verdict.confidence,
        reason=reason,
        evidence=evidence,
        check_name=verdict.check_name,
    )


def run_record(record: Record, conn: sqlite3.Connection, ref: Any = reference) -> Verdict:
    if not _record_exists(conn, record.id):
        db.insert_record(conn, record)
    verdicts = _save_check_verdicts(record, conn, ref)
    return _apply_correction(record, _combine(verdicts), ref)


def run_batch(
    records: list[Record],
    conn: sqlite3.Connection,
    ref: Any = reference,
) -> list[tuple[Record, Verdict]]:
    return [(record, run_record(record, conn, ref)) for record in records]


def seed_silent() -> tuple[sqlite3.Connection, list[Record]]:
    conn = db.init_db()
    records = _load_records(DATA_DIR / "sample_records.json")
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
    return conn, records


def load_novel() -> Record:
    return _load_record(DATA_DIR / "novel_record.json")
