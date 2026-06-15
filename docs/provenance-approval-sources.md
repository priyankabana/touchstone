# Provenance, Approval, And Trusted Sources

This document addresses the product question: "Why should I believe this fix?"

## Verification Log

`engine.finalize` now writes `data/verification_log.json` alongside the corrected dataset and correction report.

Each row includes:

- original row fields
- source family and source contract
- trusted lookups used from the pinned reference
- recompute formula when a price exists
- final executed check name
- final decision and plain-English reason
- correction object when the row was auto-fixed

API access:

```text
GET /api/verification-log
GET /api/report
POST /api/finalize
```

The key idea is that the UI can show not only "FIXED", but the exact source contract and calculation that made the fix safe.

## Approval Lifecycle

```text
UNKNOWN
  -> agent diagnosis
  -> candidate Python check
  -> AST validator
  -> subprocess sandbox replay
  -> gate result saved as proposal
  -> human approve
  -> check registered active
  -> future rows can be HELD/FIXED by that rule
```

The lower-level agent files cannot import `store` or `ingest`; `tests/test_spine.py` enforces that. Only `agent/run_agent.py` can save or approve proposals.

## Trusted Source Boundary

Touchstone treats each source as a contract:

- `sec_13f`: identity comes from CUSIP; value must reconcile to shares times price; amendments supersede older filings.
- `finra_trace`: a daily feed must be fresh, not just HTTP 200.
- `krx_adapter`: values may arrive in KRW and need a unit rule before they are trusted.
- `news_claim`: a headline claim must match the official filing.

New connectors should add a source contract first, then checks. If there is no contract, the row is not auto-fixed.

## Auto-Fix Boundary Tests

`tests/test_safety_boundaries.py` covers two near misses:

- an arbitrary ticker mismatch is HELD for a human, not renamed automatically
- a currency-like 1,200x mismatch stays UNKNOWN because it does not match a trusted FX rate

