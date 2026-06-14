import sys
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from ingest import edgar


CANDIDATES = [
    ("Renaissance Technologies LLC", 1037389),
]


def _live_required():
    if not config.LIVE or config.OFFLINE:
        print("refusing to run discovery without live EDGAR")
        print("run: OFFLINE=0 LIVE=1 python scripts/discover.py")
        return False
    return True


def _recent_filings(submissions):
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filed = recent.get("filingDate", [])
    report = recent.get("reportDate", [])
    rows = []
    for index, form in enumerate(forms):
        if form not in {"13F-HR", "13F-HR/A"}:
            continue
        filing_date = filed[index] if index < len(filed) else ""
        if filing_date < "2025-01-01":
            continue
        rows.append(
            {
                "form": form,
                "filed": filing_date,
                "period": report[index] if index < len(report) else "",
                "accession": accessions[index] if index < len(accessions) else "",
            }
        )
    return rows


def _print_filings(name, cik, filings):
    print(f"{name} CIK {cik}")
    if not filings:
        print("  no 13F-HR / 13F-HR/A filings since 2025 found")
        return
    for filing in filings:
        print(
            "  "
            + filing["filed"]
            + " · "
            + filing["form"]
            + " · "
            + filing["accession"]
            + " · period "
            + filing["period"]
        )


def _print_rows(rows):
    print()
    print("first 25 rows of chosen filing")
    print("issuer | ticker | cusip | shares | value_usd")
    for row in rows[:25]:
        print(
            str(row.get("name", ""))
            + " | "
            + str(row.get("ticker", ""))
            + " | "
            + str(row.get("cusip", ""))
            + " | "
            + str(row.get("shares", ""))
            + " | "
            + str(row.get("value_usd", ""))
        )


def main():
    if not _live_required():
        return 1

    chosen = None
    for name, cik in CANDIDATES:
        data, provenance = edgar.submissions(cik)
        filings = _recent_filings(data)
        _print_filings(name, cik, filings)
        if filings and chosen is None:
            chosen = (cik, filings[0])
        print("  provenance:", provenance)

    if chosen is None:
        return 0

    cik, filing = chosen
    table, provenance = edgar.infotable(cik, filing["accession"])
    print()
    print("chosen:", filing["accession"], "·", provenance)
    _print_rows(table.get("rows", []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
