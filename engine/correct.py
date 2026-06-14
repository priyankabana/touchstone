from __future__ import annotations

import math
from typing import Any

from engine.models import Record, Verdict


def _money(value: float) -> str:
    absolute = abs(value)
    sign = "-" if value < 0 else ""
    if absolute >= 1_000_000_000:
        return f"{sign}${absolute / 1_000_000_000:.1f}B"
    if absolute >= 1_000_000:
        return f"{sign}${absolute / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"{sign}${absolute / 1_000:.1f}K"
    return f"{sign}${absolute:,.2f}"


def _tag(verdict: Verdict) -> str:
    tag = str(verdict.evidence.get("tag") or "").upper()
    if tag:
        return tag
    reason = verdict.reason.upper()
    for candidate in ("RENAMED", "WRONG UNITS", "RECOMPUTE", "NO PROOF", "OUTDATED", "STUCK"):
        if candidate in reason:
            return candidate
    return ""


def _human_needed() -> dict[str, Any]:
    return {
        "fixed": False,
        "reason": (
            "needs a human (OUTDATED: use the corrected filing / "
            "STUCK: feed is frozen, no fresh data)"
        ),
    }


def _matched_fx(record: Record, verdict: Verdict, ref: Any) -> tuple[str, float, float] | None:
    fx_rate = verdict.evidence.get("fx_rate")
    currency = str(verdict.evidence.get("currency") or "")
    if currency and fx_rate is not None:
        return currency, float(fx_rate), float(verdict.evidence.get("ratio") or 0.0)

    price = ref.PRICE_FEED.get((record.ticker, record.as_of_date))
    if price is None or record.shares <= 0:
        return None
    estimate = record.shares * price
    if estimate <= 0:
        return None
    ratio = record.value_usd / estimate
    for candidate, rate in ref.FX.items():
        if math.isclose(ratio, float(rate), rel_tol=0.02):
            return candidate, float(rate), ratio
    return None


def correct_record(record: Record, verdict: Verdict, ref: Any) -> dict[str, Any]:
    if verdict.outcome != "held":
        return {"fixed": False, "reason": "not held"}

    tag = _tag(verdict)

    if tag == "RENAMED":
        resolved = ref.resolve(record.cusip)
        if resolved is None:
            return {"fixed": False, "reason": "needs a human (CUSIP is not in the reference)"}
        former = resolved.get("former", {})
        if former.get("ticker") != record.ticker:
            return {
                "fixed": False,
                "reason": (
                    "needs a human (CUSIP points to "
                    f"{resolved['name']} / {resolved['ticker']}, but the row says "
                    f"{record.ticker})"
                ),
            }
        explanation = (
            "renamed identity corrected: "
            f"{former.get('ticker', record.ticker)} -> {resolved['ticker']} "
            f"({resolved['name']})"
        )
        return {
            "fixed": True,
            "field": "identity",
            "old_value": {"ticker": record.ticker, "entity_name": record.entity_name},
            "new_value": {"ticker": resolved["ticker"], "entity_name": resolved["name"]},
            "explanation": explanation,
        }

    if tag == "WRONG UNITS":
        match = _matched_fx(record, verdict, ref)
        if match is None:
            return {"fixed": False, "reason": "needs a human (FX multiple is not provable)"}
        currency, fx_rate, ratio = match
        new_value = record.value_usd / fx_rate
        return {
            "fixed": True,
            "field": "value_usd",
            "old_value": record.value_usd,
            "new_value": new_value,
            "explanation": f"converted from {currency} to USD: {_money(new_value)}",
            "currency": currency,
            "fx_rate": fx_rate,
            "ratio": ratio,
        }

    if tag == "RECOMPUTE":
        estimate = verdict.evidence.get("estimate")
        if estimate is None:
            price = ref.PRICE_FEED.get((record.ticker, record.as_of_date))
            if price is None or record.shares <= 0:
                return {"fixed": False, "reason": "needs a human (no pinned price to recompute)"}
            estimate = record.shares * price
        new_value = float(estimate)
        return {
            "fixed": True,
            "field": "value_usd",
            "old_value": record.value_usd,
            "new_value": new_value,
            "explanation": f"value recomputed from shares x price: {_money(new_value)}",
        }

    if tag == "NO PROOF":
        official_value = verdict.evidence.get("official_value")
        if official_value is None:
            return {"fixed": False, "reason": "needs a human (official filed value is missing)"}
        new_value = float(official_value)
        return {
            "fixed": True,
            "field": "claimed_value",
            "old_value": record.claimed_value,
            "new_value": new_value,
            "explanation": f"claim corrected to the filed figure: {_money(new_value)}",
        }

    if tag in {"OUTDATED", "STUCK"}:
        return _human_needed()

    return {"fixed": False, "reason": "needs a human (no provable correction rule)"}
