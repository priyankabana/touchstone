from __future__ import annotations

import subprocess
import sys


def _batch_verdicts():
    from engine import router

    conn, records = router.seed_silent()
    try:
        return {record.id: verdict for record, verdict in router.run_batch(records, conn)}
    finally:
        conn.close()


def test_seed_is_idempotent() -> None:
    from store import db, seed

    seed.seed()
    seed.seed()
    conn = db.connect()
    try:
        assert db.count(conn, "records") == 7
    finally:
        conn.close()


def test_agent_does_not_import_store() -> None:
    code = """
import importlib
import sys

for name in ["agent.diagnose", "agent.author", "agent.validate", "agent.sandbox"]:
    importlib.import_module(name)

loaded = [name for name in sys.modules if name == "store" or name.startswith("store.")]
if loaded:
    raise SystemExit("loaded store modules: " + ", ".join(sorted(loaded)))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_true_rows() -> None:
    verdicts = _batch_verdicts()
    assert verdicts["r1"].outcome == "true"
    assert verdicts["r5"].outcome == "true"
    assert verdicts["r6"].outcome == "true"


def test_fixed_and_held_rows() -> None:
    verdicts = _batch_verdicts()
    assert verdicts["r3"].outcome == "fixed"
    assert "renamed" in verdicts["r3"].reason.lower()
    assert verdicts["r7"].outcome == "fixed"
    assert "claim corrected" in verdicts["r7"].reason.lower()
    assert verdicts["r2"].outcome == "held"
    assert "corrected" in verdicts["r2"].reason.lower()
    assert verdicts["r4"].outcome == "held"
    assert "stuck" in verdicts["r4"].reason.lower()


def test_novel_unknown() -> None:
    from engine import router

    conn, _records = router.seed_silent()
    try:
        verdict = router.run_record(router.load_novel(), conn)
    finally:
        conn.close()

    assert verdict.outcome == "unknown"
