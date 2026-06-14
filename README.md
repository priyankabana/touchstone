# Touchstone

<p align="center"><img src="assets/touchstone-logo.svg" width="96" alt="Touchstone logo"></p>
> Data that proves itself before it ships.

Touchstone is a lie-detector and auto-correction layer for data pipelines. Instead of marking a row healthy just because it loaded, Touchstone proves each value against source contracts, holds back rows that cannot be trusted, fixes rows when the correct answer is derivable, and uses an eval-gated agent to write new checks for novel failures.

## Why It Exists

Dashboards often fail quietly: outdated filings, renamed tickers, frozen feeds, wrong units, and unsupported news claims all look "green" if the row arrived. Touchstone changes the definition of healthy from "loaded successfully" to "proved correct, fixed with evidence, or held for a human."

## What The Demo Shows

Eight records enter the system. A naive pipeline ships all 8 as healthy. Touchstone catches the bad rows, fixes what it can prove, and sends the one unseen pattern to an agent.

| Case | Result | Plain-English reason |
| --- | --- | --- |
| OUTDATED | HELD | A corrected 13F-HR/A was filed later, so the old filing is held. |
| RENAMED | FIXED | Square / SQ is corrected to Block / XYZ from the CUSIP reference. |
| STUCK | HELD | The feed says HTTP 200, but the newest record is 6 days old on a daily feed. |
| WRONG UNITS | FIXED after approval | Samsung is 1,302x too high because KRW was placed in a USD field. |
| NO PROOF | FIXED | A "$500M Apple" headline is corrected to the filed figure of about $48.4M. |

Clean rows pass as TRUE. Rows that need source review remain HELD. Unknown rows become new checks only after validation, sandbox replay, and human approval.

## Core Features

- Source-contract checks for SEC 13F rows, feed freshness, headline claims, identities, and value reconciliation.
- Auto-correction when the right answer is derivable from pinned reference data.
- Human queue for things that should not be guessed, like outdated filings or frozen feeds.
- Agent-written Python checks for brand-new failures.
- AST validation, subprocess sandboxing, and historical backtest as the merge gate.
- Offline demo mode with deterministic data, no real clock, and zero routine model calls.
- FastAPI + self-contained HTML console for the live product walkthrough.

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
 corrected dataset + human queue
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

Generated code is guilty until proven safe:

```text
exactly one check_* function
  -> imports limited by AST allowlist
  -> banned tokens rejected
  -> subprocess sandbox with no database
  -> must catch the novel row with zero false alarms
  -> human approval before activation
```

Only `agent/run_agent.py` can import the database layer. Routine checking is plain Python and prints `model calls this run: 0`; the model is used only on the rare new-problem path.

## Submission Copy

**Project name:** Touchstone
**Tagline:** Data that proves itself before it ships.
**Description:** Touchstone is a data-trust engine for financial datasets. It verifies every row against source contracts and pinned reference truth, auto-fixes rows when the correct answer is provable, holds unsafe rows for a human, and lets an LLM agent write new Python checks only after an eval gate passes.
**Pitch:** Most dashboards turn green when data arrives, even if the data is outdated, renamed, frozen, in the wrong units, or just an unsupported headline. Touchstone changes "healthy" from "loaded" to "proved." In the demo, a naive pipeline ships 8/8 rows as healthy; Touchstone catches the bad rows, corrects the provable ones, holds the ones needing human review, and discovers a new KRW/USD unit bug. The agent diagnoses the bug, writes a new check, replays history with zero false alarms, and only then can a human approve it into the check library.

Built live with OpenAI Codex.
