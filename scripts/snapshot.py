import sys
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from ingest import edgar


RENAISSANCE_CIK = 1037389


def _live_required():
    if not config.LIVE or config.OFFLINE:
        print("refusing to warm live caches without live EDGAR")
        print("run: OFFLINE=0 LIVE=1 python scripts/snapshot.py")
        return False
    return True


def _latest_13f_accession(submissions):
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    for index, form in enumerate(forms):
        if form in {"13F-HR", "13F-HR/A"} and index < len(accessions):
            return accessions[index]
    return "pinned"


def main():
    if not _live_required():
        return 1

    ticker_data, ticker_provenance = edgar.ticker_map()
    print("ticker_map:", ticker_provenance, len(ticker_data))

    submissions, submissions_provenance = edgar.submissions(RENAISSANCE_CIK)
    print("submissions:", submissions_provenance, RENAISSANCE_CIK)

    accession = _latest_13f_accession(submissions)
    table, table_provenance = edgar.infotable(RENAISSANCE_CIK, accession)
    print("infotable:", table_provenance, accession, len(table.get("rows", [])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
