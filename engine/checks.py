from __future__ import annotations

from typing import Any, Callable

import config
from engine.models import Record, Verdict


CheckFn = Callable[[Record, Any], Verdict]


def _true(check_name: str, reason: str, evidence: dict[str, Any] | None = None) -> Verdict:
    return Verdict(
        outcome="true",
        confidence=1.0,
        reason=reason,
        evidence=evidence or {},
        check_name=check_name,
    )


def _held(
    check_name: str,
    tag: str,
    reason: str,
    evidence: dict[str, Any] | None = None,
) -> Verdict:
    payload = dict(evidence or {})
    payload["tag"] = tag
    return Verdict(
        outcome="held",
        confidence=1.0,
        reason=reason,
        evidence=payload,
        check_name=check_name,
    )


def _not_applicable(check_name: str) -> Verdict:
    return _true(check_name, "not applicable to this source", {"applicable": False})


def _money(value: float) -> str:
    sign = "-" if value < 0 else ""
    absolute = abs(value)
    if absolute >= 1_000_000_000:
        return f"{sign}${absolute / 1_000_000_000:.1f}B"
    if absolute >= 1_000_000:
        return f"{sign}${absolute / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"{sign}${absolute / 1_000:.1f}K"
    return f"{sign}${absolute:,.2f}"


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _source_family(source: str) -> str:
    suffix = "_synthetic"
    if source.endswith(suffix):
        return source[: -len(suffix)]
    return source


def _days_from_civil(year: int, month: int, day: int) -> int:
    adjusted_year = year - 1 if month <= 2 else year
    era = adjusted_year // 400
    year_of_era = adjusted_year - era * 400
    adjusted_month = month + 9 if month <= 2 else month - 3
    day_of_year = (153 * adjusted_month + 2) // 5 + day - 1
    day_of_era = (
        year_of_era * 365
        + year_of_era // 4
        - year_of_era // 100
        + day_of_year
    )
    return era * 146_097 + day_of_era


def _days_between(start: str, end: str) -> int:
    start_year, start_month, start_day = (int(part) for part in start.split("-"))
    end_year, end_month, end_day = (int(part) for part in end.split("-"))
    return _days_from_civil(end_year, end_month, end_day) - _days_from_civil(
        start_year,
        start_month,
        start_day,
    )


def check_structural(record: Record, ref: Any) -> Verdict:
    if record.source != "sec_13f":
        return _not_applicable("check_structural")

    problems: list[str] = []
    if record.shares <= 0:
        problems.append(f"shares is {record.shares}")
    if record.value_usd <= 0:
        problems.append(f"value is {_money(record.value_usd)}")
    if len(record.cusip) != 9:
        problems.append(f"CUSIP '{record.cusip}' has {len(record.cusip)} characters")

    if problems:
        reason = "BROKEN: the row itself is malformed; " + ", ".join(problems) + "."
        return _held(
            "check_structural",
            "BROKEN",
            reason,
            {"problems": problems},
        )

    return _true(
        "check_structural",
        (
            f"structure confirmed: {record.shares:,} shares, "
            f"{_money(record.value_usd)} value, 9-character CUSIP {record.cusip}."
        ),
        {"cusip": record.cusip, "shares": record.shares, "value_usd": record.value_usd},
    )


def check_identity(record: Record, ref: Any) -> Verdict:
    if record.source != "sec_13f":
        return _not_applicable("check_identity")

    resolved = ref.resolve(record.cusip)
    if resolved is None:
        reason = (
            f"RENAMED: CUSIP {record.cusip} is not in the pinned reference, "
            f"so ticker '{record.ticker}' cannot be trusted."
        )
        return _held(
            "check_identity",
            "RENAMED",
            reason,
            {"cusip": record.cusip, "ticker": record.ticker},
        )

    expected_ticker = resolved["ticker"]
    if expected_ticker == record.ticker:
        return _true(
            "check_identity",
            (
                f"identity confirmed: CUSIP {record.cusip} -> "
                f"{resolved['name']} ({expected_ticker})."
            ),
            {
                "cusip": record.cusip,
                "name": resolved["name"],
                "ticker": expected_ticker,
            },
        )

    former = resolved.get("former")
    if former and former.get("ticker") == record.ticker:
        retired = former["retired"]
        reason = (
            "RENAMED: this company changed its name and ticker "
            f"({former['ticker']}->{expected_ticker}); this row uses the dead old "
            f"ticker '{record.ticker}', retired {retired}."
        )
        return _held(
            "check_identity",
            "RENAMED",
            reason,
            {
                "cusip": record.cusip,
                "expected_ticker": expected_ticker,
                "former_ticker": former["ticker"],
                "retired": retired,
            },
        )

    reason = (
        "RENAMED: the CUSIP points to "
        f"{resolved['name']} ({expected_ticker}), but this row says "
        f"ticker '{record.ticker}'."
    )
    return _held(
        "check_identity",
        "RENAMED",
        reason,
        {
            "cusip": record.cusip,
            "expected_ticker": expected_ticker,
            "actual_ticker": record.ticker,
        },
    )


def check_value_reconciles(record: Record, ref: Any) -> Verdict:
    if record.shares <= 0:
        return _not_applicable("check_value_reconciles")

    price = ref.PRICE_FEED.get((record.ticker, record.as_of_date))
    if price is None:
        return _true(
            "check_value_reconciles",
            f"not applicable: no pinned price for {record.ticker} on {record.as_of_date}.",
            {"applicable": False, "ticker": record.ticker, "as_of_date": record.as_of_date},
        )

    estimate = record.shares * price
    delta = abs(record.value_usd - estimate)
    delta_pct = delta / estimate if estimate else 0.0
    evidence = {
        "estimate": estimate,
        "reported": record.value_usd,
        "delta": delta,
        "delta_pct": delta_pct,
        "price": price,
        "ratio": record.value_usd / estimate if estimate else None,
    }

    if delta_pct <= 0.02:
        return _true(
            "check_value_reconciles",
            (
                f"recompute {_money(estimate)} matches reported "
                f"{_money(record.value_usd)} (delta {_pct(delta_pct)})."
            ),
            evidence,
        )

    ratio = record.value_usd / estimate if estimate else 0.0
    reason = (
        "RECOMPUTE: shares times the pinned price gives "
        f"{_money(estimate)}, but the row reports {_money(record.value_usd)} "
        f"({ratio:,.1f}x the estimate)."
    )
    return _held(
        "check_value_reconciles",
        "RECOMPUTE",
        reason,
        evidence,
    )


def check_supersession(record: Record, ref: Any) -> Verdict:
    correction = (
        ref.AMENDMENT_INDEX.get((record.filer, record.period, record.cusip))
        or ref.AMENDMENT_INDEX.get((record.filer, record.period, record.id))
        or ref.AMENDMENT_INDEX.get((record.filer, record.period))
    )
    if correction and record.form == "13F-HR":
        reason = (
            f"OUTDATED: an officially corrected version ({correction['form']}) "
            f"was filed {correction['filed']} - holding the outdated one."
        )
        return _held(
            "check_supersession",
            "OUTDATED",
            reason,
            {
                "accession": correction["accession"],
                "filed": correction["filed"],
                "form": correction["form"],
            },
        )

    return _true(
        "check_supersession",
        "no later official amendment is listed for this filer and period.",
        {"filer": record.filer, "period": record.period},
    )


def check_freshness(record: Record, ref: Any) -> Verdict:
    family = _source_family(record.source)
    status = ref.FEED_STATUS.get(family)
    if status is None:
        return _not_applicable("check_freshness")

    age_days = _days_between(status["last_new_record"], config.DEMO_TODAY)
    cadence_days = int(status["expected_cadence_days"])
    if age_days > cadence_days:
        reason = (
            f"STUCK: the source says HTTP {status['http_status']} but the newest "
            f"record is {age_days} days old on a {cadence_days}-day feed - "
            "it's stuck, not fine."
        )
        return _held(
            "check_freshness",
            "STUCK",
            reason,
            {
                "age_days": age_days,
                "expected_cadence_days": cadence_days,
                "http_status": status["http_status"],
                "last_new_record": status["last_new_record"],
            },
        )

    return _true(
        "check_freshness",
        (
            f"freshness confirmed: newest record is {age_days} days old "
            f"on a {cadence_days}-day feed."
        ),
        {
            "age_days": age_days,
            "expected_cadence_days": cadence_days,
            "last_new_record": status["last_new_record"],
        },
    )


def check_claim_matches_source(record: Record, ref: Any) -> Verdict:
    if record.source != "news_claim":
        return _not_applicable("check_claim_matches_source")

    if record.claimed_value is None:
        return _held(
            "check_claim_matches_source",
            "NO PROOF",
            "NO PROOF: the headline has no claimed dollar number to verify.",
            {"claimed_value": None},
        )

    price = ref.PRICE_FEED.get((record.ticker, record.as_of_date))
    if price is not None and record.shares > 0:
        official_value = record.shares * price
    else:
        apple_price = ref.PRICE_FEED[("AAPL", ref.AS_OF)]
        official_value = 250_000 * apple_price
    delta_pct = abs(record.claimed_value - official_value) / official_value
    ratio = record.claimed_value / official_value
    evidence = {
        "claimed_value": record.claimed_value,
        "official_value": official_value,
        "ratio": ratio,
        "delta_pct": delta_pct,
    }

    if delta_pct <= 0.05:
        return _true(
            "check_claim_matches_source",
            (
                f"headline claim {_money(record.claimed_value)} matches the "
                f"official filing value {_money(official_value)}."
            ),
            evidence,
        )

    reason = (
        "NO PROOF: the headline's number doesn't match the official filing - "
        f"{_money(record.claimed_value)} claimed vs {_money(official_value)} "
        f"filed, about {ratio:.0f}x too high."
    )
    return _held(
        "check_claim_matches_source",
        "NO PROOF",
        reason,
        evidence,
    )


CHECKS: list[tuple[str, str, CheckFn]] = [
    ("structure", "structural", check_structural),
    ("identity", "identity", check_identity),
    ("value", "value_reconciles", check_value_reconciles),
    ("amendment", "supersession", check_supersession),
    ("freshness", "freshness", check_freshness),
    ("claim", "claim_matches_source", check_claim_matches_source),
]
