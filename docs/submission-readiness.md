# Submission Readiness Checklist

Several automated judge tools report "No GitHub scrape available" when the submitted repository is private, has the wrong URL, or has not pushed the expected branch. That is separate from the Touchstone code itself.

Before final submission, verify:

- the GitHub repo is public
- the submitted URL is exactly `https://github.com/priyankabana/touchstone`
- the default branch contains `README.md`, `AGENTS.md`, `.codex/`, `engine/`, `agent/`, `ingest/`, `api/`, `ui/`, `tests/`, and `docs/`
- the latest commit includes `docs/judge-verification.md`
- the README links to the Codex skill, agent loop proof, SEC pipeline proof, and runnable demo
- the demo URL points to a running deployment or a live tunnel

Run locally before pushing:

```bash
python scripts/preflight.py
python demo/verify_one.py r3
python demo/verify_one.py r8
OFFLINE=1 python -m agent.run_agent
python -m engine.finalize
python -m pytest tests/ -q
```

Expected proof points:

- `r3` is `FIXED` from Square / SQ to Block / XYZ
- `r8` starts `UNKNOWN`
- the agent gate catches `r8` with zero false alarms
- `data/verification_log.json` explains the source contract, trusted lookup, and calculation behind each row

Model wording for judges:

```text
Routine checks are deterministic Python and make zero model calls.
The model is used only for novel failures, through the OpenAI Responses API model configured in config.py.
Offline demo mode uses a cached proposal so the gate is reproducible without an API key.
```

