# Agent-Written Check Loop

Touchstone does not ask an LLM to judge whether a row is true. The deterministic router finds rows that existing checks cannot explain. Only then does the agent write a candidate Python check.

## Where It Lives

| Claim | File |
| --- | --- |
| Model call through OpenAI Responses API | `agent/_llm.py` |
| Plain-English root-cause diagnosis | `agent/diagnose.py` |
| Strict JSON check authoring | `agent/author.py` |
| AST allowlist and banned-token validation | `agent/validate.py` |
| Subprocess replay over historical JSON records | `agent/sandbox.py` |
| Human approval and check registration | `agent/run_agent.py` |
| Active check execution | `engine/router.py` |

## Gate

Generated code must pass this sequence before it becomes part of the library:

```text
UNKNOWN row
  -> diagnosis
  -> candidate check_code
  -> AST validate
  -> sandbox replay over data/*.json
  -> catch r8 with zero false alarms on r1/r5/r6
  -> human approve
  -> check library 6 -> 7
```

The sandbox does not use the database. It writes a tiny runner, imports the candidate check, replays JSON records, and times out after five seconds.

## Reproduce

```bash
OFFLINE=1 python -m agent.run_agent
python -m evals.metrics
python -m pytest tests/ -q
```

Expected offline behavior: the cached KRW/USD proposal is validated, replayed, approved, and Samsung becomes `HELD · WRONG UNITS`. Routine checking still reports `model calls this run: 0`; the model path is only for novel failures.

