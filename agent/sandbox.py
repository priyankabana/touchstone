from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from agent.validate import validate_code


REPO_ROOT = Path(__file__).resolve().parent.parent
CLEAN_RECORD_IDS = {"r1", "r5", "r6"}
NOVEL_RECORD_ID = "r8"


RUNNER = """
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from engine import reference
from engine.models import Record


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = Path(__file__).resolve().parent / "candidate_check.py"


def _load_candidate():
    spec = importlib.util.spec_from_file_location("candidate_check", CANDIDATE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.check_currency_unit_consistency


def _is_record(row):
    return (
        isinstance(row, dict)
        and "id" in row
        and "source" in row
        and "final_status" not in row
    )


def _records_from_payload(payload):
    if isinstance(payload, list):
        return [Record.from_json(row) for row in payload if _is_record(row)]
    if _is_record(payload):
        return [Record.from_json(payload)]
    return []


def _load_records():
    records = []
    for path in sorted((ROOT / "data").glob("*.json")):
        if path.name in {"corrected_dataset.json", "correction_report.json"}:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        records.extend(_records_from_payload(payload))
    return records


def main():
    check = _load_candidate()
    per_record = {}
    records = _load_records()
    for record in records:
        verdict = check(record, reference)
        per_record[record.id] = {
            "check_name": verdict.check_name,
            "outcome": verdict.outcome,
            "reason": verdict.reason,
            "tag": verdict.evidence.get("tag"),
        }

    clean_ids = {"r1", "r5", "r6"}
    caught_novel = per_record.get("r8", {}).get("outcome") == "held"
    false_positive_ids = [
        record_id
        for record_id in sorted(clean_ids)
        if per_record.get(record_id, {}).get("outcome") == "held"
    ]
    result = {
        "gate": caught_novel and not false_positive_ids,
        "caught_novel": caught_novel,
        "false_positives": len(false_positive_ids),
        "false_positive_ids": false_positive_ids,
        "per_record": per_record,
        "records_replayed": len(records),
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
"""


def _repo_root() -> Path:
    return REPO_ROOT


def _try_git_worktree(repo_root: Path) -> tuple[Path, Path | None]:
    git_check = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if git_check.returncode != 0:
        return repo_root, None

    temp_parent = Path(tempfile.mkdtemp(prefix="touchstone-worktree-"))
    worktree = temp_parent / "repo"
    add = subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree), "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if add.returncode != 0:
        shutil.rmtree(temp_parent, ignore_errors=True)
        return repo_root, None

    if not (worktree / "data" / "sample_records.json").exists():
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        shutil.rmtree(temp_parent, ignore_errors=True)
        return repo_root, None

    return worktree, temp_parent


def _cleanup_worktree(repo_root: Path, root: Path, temp_parent: Path | None) -> None:
    if temp_parent is None:
        return
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(root)],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    shutil.rmtree(temp_parent, ignore_errors=True)


def _runner_dir(root: Path) -> Path:
    path = root / "touchstone-sandbox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_runner(root: Path, check_code: str) -> Path:
    runner_dir = _runner_dir(root)
    candidate = runner_dir / "candidate_check.py"
    runner = runner_dir / "runner.py"
    candidate.write_text(
        "from engine.models import Verdict\n" + check_code,
        encoding="utf-8",
    )
    runner.write_text(RUNNER, encoding="utf-8")
    return runner


def _failure_result(why: str) -> dict[str, Any]:
    return {
        "gate": False,
        "caught_novel": False,
        "false_positives": 0,
        "per_record": {"error": why},
        "records_replayed": 0,
    }


def backtest(check_code: str) -> dict[str, Any]:
    ok, why = validate_code(check_code)
    if not ok:
        return _failure_result(why)

    repo_root = _repo_root()
    root, temp_parent = _try_git_worktree(repo_root)
    try:
        runner = _write_runner(root, check_code)
        env = dict(os.environ)
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(root) if not existing else str(root) + os.pathsep + existing
        completed = subprocess.run(
            [sys.executable, str(runner)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            return _failure_result(detail)
        try:
            return json.loads(completed.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as error:
            return _failure_result("sandbox returned invalid JSON: " + str(error))
    except subprocess.TimeoutExpired:
        return _failure_result("sandbox timed out after 5 seconds")
    finally:
        _cleanup_worktree(repo_root, root, temp_parent)
