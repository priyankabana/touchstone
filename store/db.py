from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import config
from engine.models import Proposal, Record, Verdict


ALLOWED_COUNT_TABLES = {"records", "checks", "verdicts", "evidence", "proposals"}


def connect(db_path: Path | str = config.DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str = config.DB_PATH) -> sqlite3.Connection:
    conn = connect(db_path)
    conn.executescript(
        """
        DROP TABLE IF EXISTS evidence;
        DROP TABLE IF EXISTS verdicts;
        DROP TABLE IF EXISTS proposals;
        DROP TABLE IF EXISTS checks;
        DROP TABLE IF EXISTS records;

        CREATE TABLE records (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            filer TEXT NOT NULL,
            form TEXT NOT NULL,
            period TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            entity_name TEXT NOT NULL,
            ticker TEXT NOT NULL,
            cusip TEXT NOT NULL,
            shares INTEGER NOT NULL,
            value_usd REAL NOT NULL,
            price REAL,
            accession TEXT,
            claimed_value REAL,
            headline TEXT,
            raw_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family TEXT NOT NULL,
            name TEXT NOT NULL UNIQUE,
            created_by TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE verdicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT NOT NULL,
            check_name TEXT NOT NULL,
            outcome TEXT NOT NULL,
            confidence REAL NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (record_id) REFERENCES records(id)
        );

        CREATE TABLE evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            verdict_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (verdict_id) REFERENCES verdicts(id)
        );

        CREATE TABLE proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diagnosis TEXT NOT NULL,
            check_code TEXT NOT NULL,
            rationale TEXT NOT NULL,
            test_plan TEXT NOT NULL,
            source TEXT NOT NULL,
            gate_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    return conn


def _record_dict(record: Record | dict[str, Any]) -> dict[str, Any]:
    if isinstance(record, Record):
        return record.model_dump(mode="json")
    return dict(record)


def insert_record(conn: sqlite3.Connection, record: Record | dict[str, Any]) -> str:
    data = _record_dict(record)
    raw_json = json.dumps(data, sort_keys=True)
    conn.execute(
        """
        INSERT OR REPLACE INTO records (
            id, source, filer, form, period, as_of_date, entity_name, ticker,
            cusip, shares, value_usd, price, accession, claimed_value, headline,
            raw_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["id"],
            data["source"],
            data["filer"],
            data["form"],
            data["period"],
            data["as_of_date"],
            data["entity_name"],
            data["ticker"],
            data["cusip"],
            data["shares"],
            data["value_usd"],
            data.get("price"),
            data.get("accession"),
            data.get("claimed_value"),
            data.get("headline"),
            raw_json,
            config.stamp(),
        ),
    )
    conn.commit()
    return str(data["id"])


def register_check(
    conn: sqlite3.Connection,
    family: str,
    name: str,
    *,
    created_by: str,
    status: str,
) -> int:
    conn.execute(
        """
        INSERT INTO checks (family, name, created_by, status, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            family = excluded.family,
            created_by = excluded.created_by,
            status = excluded.status,
            created_at = excluded.created_at
        """,
        (family, name, created_by, status, config.stamp()),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM checks WHERE name = ?",
        (name,),
    ).fetchone()
    return int(row["id"])


def insert_verdict(
    conn: sqlite3.Connection,
    record_id: str,
    verdict: Verdict | dict[str, Any],
) -> int:
    data = verdict.model_dump(mode="json") if isinstance(verdict, Verdict) else dict(verdict)
    cursor = conn.execute(
        """
        INSERT INTO verdicts (
            record_id, check_name, outcome, confidence, reason, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            data["check_name"],
            data["outcome"],
            data["confidence"],
            data["reason"],
            config.stamp(),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def insert_evidence(
    conn: sqlite3.Connection,
    verdict_id: int,
    evidence: dict[str, Any],
) -> list[int]:
    inserted: list[int] = []
    for key, value in evidence.items():
        cursor = conn.execute(
            """
            INSERT INTO evidence (verdict_id, key, value_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                verdict_id,
                key,
                json.dumps(value, sort_keys=True),
                config.stamp(),
            ),
        )
        inserted.append(int(cursor.lastrowid))
    conn.commit()
    return inserted


def insert_proposal(
    conn: sqlite3.Connection,
    proposal: Proposal | dict[str, Any],
    *,
    status: str = "pending",
) -> int:
    data = (
        proposal.model_dump(mode="json")
        if isinstance(proposal, Proposal)
        else dict(proposal)
    )
    stamped = config.stamp()
    cursor = conn.execute(
        """
        INSERT INTO proposals (
            diagnosis, check_code, rationale, test_plan, source, gate_json,
            status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["diagnosis"],
            data["check_code"],
            data["rationale"],
            data["test_plan"],
            data["source"],
            json.dumps(data.get("gate", {}), sort_keys=True),
            status,
            stamped,
            stamped,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def set_proposal_status(
    conn: sqlite3.Connection,
    proposal_id: int,
    status: str,
) -> None:
    conn.execute(
        """
        UPDATE proposals
        SET status = ?, updated_at = ?
        WHERE id = ?
        """,
        (status, config.stamp(), proposal_id),
    )
    conn.commit()


def get_proposal(conn: sqlite3.Connection, proposal_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, diagnosis, check_code, rationale, test_plan, source, gate_json,
               status, created_at, updated_at
        FROM proposals
        WHERE id = ?
        """,
        (proposal_id,),
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["gate"] = json.loads(data.pop("gate_json"))
    return data


def active_checks(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, family, name, created_by, status, created_at
        FROM checks
        WHERE status = ?
        ORDER BY id
        """,
        ("active",),
    ).fetchall()
    return [dict(row) for row in rows]


def count(conn: sqlite3.Connection, table: str) -> int:
    if table not in ALLOWED_COUNT_TABLES:
        raise ValueError(f"cannot count unknown table: {table}")
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    return int(row["n"])
