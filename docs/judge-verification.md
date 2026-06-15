# Judge Verification Map

This file maps the submission claims to files and commands a reviewer can inspect quickly.

## If Repo Scraping Fails

The public repo must be visible at the submitted URL and the default branch must contain these root files:

- `README.md`
- `AGENTS.md`
- `requirements.txt`
- `Makefile`
- `.codex/skills/touchstone-data-verification/SKILL.md`

If a review tool says "No GitHub scrape available," first check that the repo is public, the URL is correct, and the branch pushed to GitHub is the branch in the submission.

## Claims And Evidence

| Claim | Evidence |
| --- | --- |
| Built with a clear Codex spec | `AGENTS.md` |
| Visible Codex skill architecture | `.codex/skills/touchstone-data-verification/SKILL.md` |
| Bounded context and gates | `.codex/skills/touchstone-data-verification/agents/openai.yaml` |
| One end-to-end verification flow | `demo/verify_one.py` |
| SEC EDGAR source integration | `ingest/edgar.py`, `docs/sec-edgar-pipeline.md` |
| Seeded planted errors | `ingest/inject.py`, `data/injection_log.json` |
| Deterministic checks | `engine/checks.py`, `engine/router.py` |
| Auto-fix with audit trail | `engine/correct.py`, `engine/finalize.py`, `docs/examples/auto-fix.md` |
| Agent writes a new check | `agent/diagnose.py`, `agent/author.py`, `proposals/cached_proposal.json` |
| Generated code safety gate | `agent/validate.py`, `agent/sandbox.py` |
| Human approval before activation | `agent/run_agent.py` |
| Regression proof | `tests/test_spine.py`, `evals/metrics.py`, `scripts/preflight.py` |

## Commands To Run

```bash
python -m pip install -r requirements.txt pytest
python scripts/preflight.py
python demo/verify_one.py r3
python demo/verify_one.py r8
OFFLINE=1 python -m agent.run_agent
python -m engine.finalize
python -m pytest tests/ -q
```

Expected highlights:

- `r3` becomes `FIXED` because Square / SQ is corrected to Block / XYZ.
- `r8` starts as `UNKNOWN`.
- The agent proposal catches `r8`, has zero false alarms, and changes the library from 6 to 7 checks.
- Finalization writes a corrected dataset plus a correction report.

