from __future__ import annotations

from engine import finalize, router
from engine.models import Record


def test_unknown_ticker_mismatch_is_not_auto_fixed() -> None:
    record = Record(
        id="near-miss-identity",
        source="sec_13f",
        filer="Uploaded fund",
        form="13F-HR",
        period="2026-03-31",
        as_of_date="2026-03-31",
        entity_name="Mystery Block row",
        ticker="NOTSQ",
        cusip="852234103",
        shares=1000,
        value_usd=62500.0,
        price=None,
        accession=None,
        claimed_value=None,
    )
    result = finalize.process(records=[record], write_files=False)
    row = result["rows"][0]
    assert row["outcome"] == "held"
    assert "needs a human" in row["reason"].lower()
    assert result["summary"]["auto_fixed"] == 0


def test_currency_near_miss_is_unknown_until_a_rule_covers_it() -> None:
    record = Record(
        id="near-miss-currency",
        source="krx_adapter",
        filer="Uploaded fund",
        form="UPLOAD",
        period="2026-03-31",
        as_of_date="2026-03-31",
        entity_name="Samsung Electronics Co., Ltd.",
        ticker="005930.KS",
        cusip="KR7005930003",
        shares=130000,
        value_usd=130000 * 52.00 * 1200,
        price=None,
        accession=None,
        claimed_value=None,
    )
    conn, _records = router.seed_silent()
    try:
        verdict = router.run_record(record, conn)
    finally:
        conn.close()
    assert verdict.outcome == "unknown"
    assert "no existing check explains it" in verdict.reason


def test_finalize_includes_verification_log() -> None:
    result = finalize.process(write_files=False)
    log = result["verification_log"]
    assert len(log) == 8
    r3 = next(row for row in log if row["row"] == "r3")
    assert r3["decision"] == "FIXED"
    assert r3["correction"]["field"] == "identity"
    assert "source_contract" in r3

