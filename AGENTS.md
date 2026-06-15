# AGENTS.md — Touchstone

## What we're building (in one breath)
A **lie-detector for data**. We trust news the second we read it — we almost never check the source.
Dashboards do the same with data: they turn green when data *arrives*, even when it's wrong —
outdated, renamed, stuck, in the wrong units, or just an unproven claim. Touchstone makes every value
PROVE it's true, **holds back** the ones that can't with a plain-English reason, and when it meets a
NEW kind of problem it has no check for, an LLM agent diagnoses it, **writes a new check in Python**,
tests that check against history (the test is the approval gate), and a human approves it.
Nothing merges by itself.

Built live with OpenAI Codex at the Codex Community Hackathon, Pune.

## THE WORDS WE USE (simple on purpose — this is graded on clarity)
Status of every value:
- **TRUE** — proven correct.
- **HELD** — caught; we don't trust it (a plain reason is always shown).
- **UNKNOWN** — a problem we've never seen; the agent investigates → becomes HELD.

Why something was HELD (the one-word tag shown under the row):
- **OUTDATED** — "an officially corrected version was published later — holding the outdated one."
- **RENAMED** — "this company changed its name and ticker (Square→Block, SQ→XYZ) — this row uses the dead old ticker."
- **STUCK** — "the source says OK but hasn't sent a new number in 6 days on a daily feed — it's stuck, not fine."
- **WRONG UNITS** — "this value is in Korean won, not dollars (1,302× = the won-to-dollar rate)."
- **NO PROOF** — "the headline's number doesn't match the official filing — $500M claimed vs $48.4M filed."
- **BROKEN** — "the row itself is malformed."

Rules for reasons: written for a smart non-expert, always with the number in them, never a black-box
score. The console shows the STATUS word, then the TAG, then the full sentence.

## Non-negotiables
1. **Same answer every time.** Nothing in `engine/` or `ingest/inject.py` calls the real clock or uses
   randomness. The one "now" is `config.DEMO_TODAY`; timestamps come from `config.stamp()`.
2. **A verdict is never a true/false boolean.** It carries `outcome` ('true' / 'held' / 'unknown'),
   `confidence`, a human `reason`, and `evidence`. The reason is the product.
3. **Hold over silently passing.** A blank is honest; a believable wrong number is a liar that gets
   trusted. When unsure, HOLD it — with a reason.
4. **The agent has no database key.** `agent/diagnose.py`, `author.py`, `validate.py`, `sandbox.py`
   MUST NOT import `store` or `ingest`. Only `agent/run_agent.py` may touch `store`. A test enforces this.
5. **Generated code is guilty until proven safe:** AST allowlist (exactly one `check_…` function;
   imports limited to `math`/`datetime`; banned tokens rejected) → sandboxed test (subprocess, timeout,
   NO database) → gate (must catch the planted problem with ZERO false alarms) → a human approves.
6. **Honest data, three layers, always labelled:** real filing rows (we keep their source IDs) ·
   planted problems from a *seeded* injector with a PUBLIC log of exactly what it changed · a pinned,
   hand-checked reference snapshot. Source = the **SEC's official EDGAR data API + this snapshot**; the
   demo runs **offline from the snapshot**. This is **NOT web scraping**, and the README says so plainly.
7. **Honest cost.** Everyday checks are plain Python = 0 model calls. The model is used ONLY to diagnose
   and write a check when a NEW problem appears. The demo prints the call count.

## Where the model is used (judges will ask — answer exactly this)
- **OpenAI Codex BUILT this** from this file + specs, live.
- **The OpenAI Responses API model configured in `config.py` runs INSIDE it as the check-writer:** on a
  new problem it diagnoses the cause and writes a new Python check. Routine checking is plain code; the
  model is the rare, expensive new-problem path. Offline demo mode uses `proposals/cached_proposal.json`
  so reviewers can verify the whole gate with zero API calls.

## The demo — build to produce EXACTLY this
Eight records. A batch of seven (r1–r7), then r8 arrives separately as the brand-new problem.
- **r1** BlackRock / Apple → **TRUE** (recompute matches reported, within 0.1%).
- **r2** Renaissance / Microsoft → **HELD · OUTDATED** (a corrected 13F-HR/A was filed later).
- **r3** Citadel / "Square, Inc." → **HELD · RENAMED** (CUSIP is Block/XYZ; SQ retired 2025-01-21).
- **r4** bond feed → **HELD · STUCK** (HTTP 200 but newest record is 6 days old on a daily feed).
- **r5** Vanguard / NVIDIA → **TRUE**.  **r6** Berkshire / Coca-Cola → **TRUE**.
- **r7** a NEWS HEADLINE: "BlackRock holds $500M in Apple" → **HELD · NO PROOF** (real filing ≈ $48.4M).
- **r8** NPS / Samsung → **UNKNOWN** (value is 1,302× the estimate; no check explains it). After the
  agent writes `check_currency_unit_consistency` and a human approves → **HELD · WRONG UNITS**
  (it's in Korean won; 1,302× = the FX rate). Check library **6 → 7**.
- Batch result: **3 TRUE · 4 HELD**.  Plus r8: **UNKNOWN → caught** after the merge.
- Naive baseline (no checks): **8/8 "healthy — shipped"** (the trap we open with).
- Evals: **precision 1.00 · recall 1.00 · false-alarm-rate 0.00.**

**Combine rule (router priority):** if the recompute is off by ≥ 50× → UNKNOWN (send to agent); else if
any check HELD it → HELD with the MOST SPECIFIC reason, in order OUTDATED > RENAMED > STUCK > NO PROOF
> recompute > BROKEN; else TRUE.

## Layout
- `config.py` — the fixed "now", flags (OFFLINE, LIVE), model + EDGAR settings.
- `ingest/` — `edgar.py` (the ONLY networked module: official EDGAR API + offline snapshot fallback,
  request budget, User-Agent header) · `inject.py` (seeded problem-injector + public log).
- `engine/` — `reference.py` (pinned snapshot) · `models.py` · `contract.py` · `checks.py` (6 plain
  checks) · `router.py` (combine by priority) · `naive.py` (the baseline).
- `store/` — `db.py` (sqlite, parameterised SQL only) · `seed.py`.
- `agent/` — `_llm.py` · `diagnose.py` · `author.py` · `validate.py` · `sandbox.py` · `run_agent.py`.
- `evals/metrics.py` · `api/main.py` (localhost only) · `ui/console.html` (the act-based demo).
- `scripts/` — `smoke.py` · `discover.py` · `snapshot.py` · `preflight.py`.
- `tests/test_spine.py` · `run_demo.py` · `Makefile`.

## Style
Small pure functions. Raw parameterised SQL, no ORM. Type hints. Reasons read like a sharp colleague
wrote them — the number in them, plus the plain-English clause. No dependency without a reason.
