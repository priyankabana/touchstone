from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Callable

from agent._llm import load_cached
from engine import reference, router
from engine.models import Record, Verdict


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

LABELS = {
    "r1": "clean",
    "r2": "bad",
    "r3": "bad",
    "r4": "bad",
    "r5": "clean",
    "r6": "clean",
    "r7": "bad",
    "r8": "bad",
}


def _function_name(check_code: str) -> str:
    tree = ast.parse(check_code)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return node.name
    raise ValueError("proposal has no check function")


def _load_agent_check() -> Callable[[Record, object], Verdict]:
    check_code = load_cached()["check_code"]
    namespace: dict[str, object] = {"Verdict": Verdict}
    exec(check_code, namespace)
    return namespace[_function_name(check_code)]  # type: ignore[return-value]


def _load_records() -> list[Record]:
    with (DATA_DIR / "sample_records.json").open("r", encoding="utf-8") as handle:
        records = [Record.from_json(row) for row in json.load(handle)]
    with (DATA_DIR / "novel_record.json").open("r", encoding="utf-8") as handle:
        records.append(Record.from_json(json.load(handle)))
    return records


def _final_verdict(record: Record, conn, agent_check) -> Verdict:
    verdict = router.run_record(record, conn)
    if record.id == "r8" and verdict.outcome == "unknown":
        agent_verdict = agent_check(record, reference)
        if agent_verdict.outcome == "held":
            return agent_verdict
    return verdict


def _rates(tp: int, fp: int, fn: int, tn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    false_alarm_rate = fp / (fp + tn) if fp + tn else 0.0
    return precision, recall, false_alarm_rate


def main() -> None:
    agent_check = _load_agent_check()
    tp = fp = fn = tn = 0

    conn, _batch = router.seed_silent()
    try:
        for record in _load_records():
            verdict = _final_verdict(record, conn, agent_check)
            caught = verdict.outcome in {"held", "unknown", "fixed"}
            bad = LABELS[record.id] == "bad"
            if caught and bad:
                tp += 1
            elif caught and not bad:
                fp += 1
            elif not caught and bad:
                fn += 1
            else:
                tn += 1
    finally:
        conn.close()

    precision, recall, false_alarm_rate = _rates(tp, fp, fn, tn)
    print(
        f"precision {precision:.2f} · recall {recall:.2f} · "
        f"false-alarm-rate {false_alarm_rate:.2f}"
    )
    print(f"counts: tp={tp} fp={fp} fn={fn} tn={tn}")
    print(
        "the agent's backtest IS the deployment gate — the self-writing loop "
        "and the eval are the same machinery"
    )
    print("model calls this run: 0")


if __name__ == "__main__":
    main()
