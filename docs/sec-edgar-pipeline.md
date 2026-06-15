# SEC EDGAR Pipeline

Touchstone uses the SEC's official EDGAR data API through one networked module: `ingest/edgar.py`.

## Source

- Submissions: `https://data.sec.gov/submissions/CIK##########.json`
- Ticker map: `https://www.sec.gov/files/company_tickers.json`
- Filing archive info table: `https://www.sec.gov/Archives/edgar/data/.../infotable.xml`

Every request sends `User-Agent = config.EDGAR_UA` and respects `config.EDGAR_REQUEST_BUDGET`.

## Offline Snapshot

The demo defaults to offline mode:

```text
OFFLINE=1
LIVE=0
```

If live access is disabled or a request fails, EDGAR functions fall back to JSON snapshots in `data/live_cache/`. Successful live calls are saved there for repeatable runs.

## Parsing And Normalization

`ingest/edgar.py` parses 13F info-table XML with the Python standard library. It normalizes issuer name, CUSIP, ticker, shares, and value. For post-2023 filings it asserts values are full dollars rather than thousands.

## Planted Problems

`ingest/inject.py` reads the pinned filing, applies deterministic seeded changes, and writes:

- `data/sample_records.json`
- `data/novel_record.json`
- `data/injection_log.json`

The public log records which rows are real, which fields were changed, and which rows were synthetic. That lets the demo catch known lies without pretending the source data was naturally broken.

Data comes from the SEC's official EDGAR data API and a pinned, hand-verified snapshot; the demo runs offline from the snapshot. No web scraping.

