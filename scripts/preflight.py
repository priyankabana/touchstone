import sys
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import io
import json
import tokenize

import config
from engine import checks
from store import db


ROOT = Path(__file__).resolve().parents[1]


def _status(name, ok, detail=""):
    print(("PASS" if ok else "FAIL") + " — " + name + ((" · " + detail) if detail else ""))
    return ok


def check_env():
    return _status(".env present", (ROOT / ".env").exists())


def check_db_seed():
    conn = db.init_db()
    try:
        records = json.loads((ROOT / "data" / "sample_records.json").read_text(encoding="utf-8"))
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
        record_count = db.count(conn, "records")
        check_count = db.count(conn, "checks")
    finally:
        conn.close()
    return _status(
        "DB seeds 7 records + 6 checks",
        record_count == 7 and check_count == 6,
        f"{record_count} records, {check_count} checks",
    )


def check_injection_log():
    path = ROOT / "data" / "injection_log.json"
    if not path.exists():
        return _status("injection log matches seed 42", False, "missing data/injection_log.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    ok = data.get("seed") == config.INJECT_SEED and "seed 42" in data.get("line", "")
    return _status("injection log matches seed 42", ok)


def check_cached_proposal():
    path = ROOT / "proposals" / "cached_proposal.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return _status("cached_proposal.json parses", False, str(error))
    required = {"diagnosis", "check_code", "rationale", "test_plan", "source"}
    return _status("cached_proposal.json parses", required.issubset(data))


def check_ui():
    path = ROOT / "ui" / "console.html"
    return _status("ui/console.html present", path.exists() and path.stat().st_size > 0)


def _strip_comments_and_strings(source):
    out = []
    reader = io.StringIO(source).readline
    for token in tokenize.generate_tokens(reader):
        if token.type in {tokenize.COMMENT, tokenize.STRING}:
            continue
        out.append(token.string)
    return " ".join(out)


def check_no_clock_random():
    paths = sorted((ROOT / "engine").glob("*.py")) + [ROOT / "ingest" / "inject.py"]
    offenders = []
    for path in paths:
        stripped = _strip_comments_and_strings(path.read_text(encoding="utf-8"))
        if ".now(" in stripped or "time.time(" in stripped or "import random" in stripped:
            offenders.append(str(path.relative_to(ROOT)))
    return _status(
        "no real clock/random in engine/ or ingest/inject.py",
        not offenders,
        ", ".join(offenders),
    )


def main():
    checks_ok = [
        check_env(),
        check_db_seed(),
        check_injection_log(),
        check_cached_proposal(),
        check_ui(),
        check_no_clock_random(),
    ]
    return 0 if all(checks_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
