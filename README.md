# Touchstone

<p align="center"><img src="assets/touchstone-logo.svg" width="96" alt="Touchstone logo"></p>

> The data lie-detector: it proves every number, fixes what is provably wrong, and writes its own new checks.

Touchstone is a trust layer for financial data pipelines. A normal pipeline turns green when a row loads, even if the row is outdated, renamed, frozen, in the wrong units, or just an unsupported headline. Touchstone turns green only when the row is proven, safely fixed, or held with a plain-English reason.

## Demo Cases

| Case | Result | What happens |
| --- | --- | --- |
| OUTDATED | HELD | A corrected 13F-HR/A exists, so the old filing is held. |
| RENAMED | FIXED | Square / SQ is corrected to Block / XYZ from CUSIP truth. |
| STUCK | HELD | HTTP 200, but the newest feed record is 6 days old on a daily feed. |
| WRONG UNITS | FIXED after approval | Samsung is 1,302x too high because KRW landed in a USD field. |
| NO PROOF | FIXED | A "$500M Apple" headline is corrected to the filed value of about $48.4M. |

Clean rows pass as TRUE. Unsafe rows remain HELD. New patterns start as UNKNOWN, then become checks only after validation, sandbox replay, and human approval.

## Codex Evidence

- Skill: `.codex/skills/touchstone-data-verification/SKILL.md`
- Bounded agent config: `.codex/skills/touchstone-data-verification/agents/openai.yaml`
- Agent check loop proof: `docs/agent-check-loop.md`
- Auto-fix examples and audit trail: `docs/examples/auto-fix.md`
- SEC EDGAR pipeline proof: `docs/sec-edgar-pipeline.md`
- Judge verification map: `docs/judge-verification.md`
- Minimal runnable flow: `demo/verify_one.py`
- Provenance, approval, and source boundary: `docs/provenance-approval-sources.md`
- Submission readiness checklist: `docs/submission-readiness.md`

## Features

- Deterministic source-contract checks for 13F rows, identity, value reconciliation, feed freshness, and headline claims.
- Auto-correction only when the right answer is derivable from trusted reference data.
- Row-level verification log with trusted lookups, formulas, decisions, and corrections.
- Human queue for rows that should not be guessed.
- Agent-written Python checks for novel failures.
- AST validation, subprocess sandboxing, replay backtest, and human approval before activation.
- Offline demo mode with a pinned snapshot, no real clock, and zero routine model calls.
- FastAPI plus one self-contained HTML console for the live walkthrough.

## Honest Data Model

1. Real filing rows keep their source IDs, accessions, CUSIPs, and source labels.
2. Planted problems come from a seeded injector with a public injection log.
3. Reference values come from a pinned, hand-verified snapshot.

Data comes from the SEC's official EDGAR data API and a pinned, hand-verified snapshot; the demo runs offline from the snapshot. No web scraping.

## Architecture

```text
SEC EDGAR API / pinned snapshot
            |
        ingest/
            |
 seeded records + source contracts
            |
        engine/checks.py
            |
   TRUE / HELD / UNKNOWN
            |
   engine/correct.py
            |
 corrected dataset + audit report
            |
 UNKNOWN novel pattern
            |
 agent diagnose -> write Python check
            |
 AST validate -> sandbox replay -> gate
            |
 human approve -> check library 6 -> 7
```

## Quickstart

```bash
python -m pip install -r requirements.txt pytest
python -m ingest.inject
python run_demo.py
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## Useful Commands

```bash
make preflight
make test
make eval
make headless
```

Use live EDGAR only when you explicitly mean it:

```bash
OFFLINE=0 LIVE=1 python scripts/discover.py
OFFLINE=0 LIVE=1 python scripts/snapshot.py
```

## Safety Rail

Generated code is guilty until proven safe: exactly one `check_*` function, imports limited by AST allowlist, banned tokens rejected, subprocess sandbox with no database, zero false alarms on known clean rows, and human approval before activation.

Only `agent/run_agent.py` can import the database layer. Routine checking is plain Python and prints `model calls this run: 0`; the model is used only on the rare new-problem path through the OpenAI Responses API model configured in `config.py`.

## Submission Copy

**Project name:** Touchstone
**Tagline:** The data lie-detector: it proves every number, fixes what is wrong, and writes its own new checks.
**Description:** Touchstone is an autonomous data-verification agent for teams working with data they cannot fully trust. It verifies rows against source contracts and pinned reference truth, auto-fixes rows when the correct answer is provable, holds unsafe rows for a human, and lets an LLM agent write new Python checks only after an eval gate passes.
**Pitch:** A confidently wrong pipeline is worse than a crashed one because nobody notices. Touchstone makes every value prove itself. In the demo, a naive pipeline ships 8/8 rows as healthy; Touchstone catches the bad rows, corrects the provable ones, holds the human cases, and discovers a KRW/USD unit bug. The agent diagnoses it, writes a new check, replays history with zero false alarms, and only then can a human approve it.

Built live with OpenAI Codex.
