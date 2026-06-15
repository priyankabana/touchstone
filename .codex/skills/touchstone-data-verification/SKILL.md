---
name: touchstone-data-verification
description: Verify financial rows against source contracts, auto-fix provable errors, and gate new Python checks through validation, sandbox replay, and human approval.
---

# Touchstone Data Verification

Use this skill when a dataset needs to be cleaned by Touchstone, or when a new data-quality pattern should become a reusable check.

## Invocation

```text
$touchstone-data-verification
```

## Bounded Context

Load only the context needed for the current task:

- Always read `AGENTS.md`, `engine/contract.py`, `engine/reference.py`, and the dataset schema.
- For uploaded datasets, inspect a small representative sample plus the provided `reference` block. Do not paste an unbounded dataset into a model prompt.
- Keep generated-check prompts to source contracts, the failing row, the unknown verdict reason, and the frozen reference snapshot.
- Never read `.env`, SQLite database files, `.venv`, or generated caches unless the user explicitly asks for operational debugging.

## Workflow

1. Run deterministic checks first with `engine/router.py`.
2. Auto-fix only through `engine/correct.py`, where the new value is derivable from the pinned reference or uploaded reference.
3. If a row is `UNKNOWN`, call the agent path:
   - diagnose with `agent/diagnose.py`
   - author strict JSON with `agent/author.py`
   - validate generated code with `agent/validate.py`
   - replay all records with `agent/sandbox.py`
   - require human approval through `agent/run_agent.py`
4. Final output is produced by `engine/finalize.py` and includes corrected rows plus `data/correction_report.json`.

## Safety Rules

- The model never directly decides TRUE/HELD/FIXED. Plain Python checks do that.
- Generated checks are not trusted until the AST validator and sandbox gate pass.
- Only `agent/run_agent.py` may import `store`; the lower-level agent files must not touch the database.
- Networked SEC access is limited to `ingest/edgar.py`; the demo defaults to offline snapshots.
- When the source of truth is missing, HOLD for a human instead of guessing.

