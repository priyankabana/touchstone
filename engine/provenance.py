from __future__ import annotations

from typing import Any

from engine import contract
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


def _price_trace(record: Record, ref: Any) -> dict[str, Any] | None:
    price = ref.PRICE_FEED.get((record.ticker, record.as_of_date))
    if price is None:
        return None
    estimate = record.shares * price
    return {
        "lookup": "PRICE_FEED[(ticker, as_of_date)]",
        "key": [record.ticker, record.as_of_date],
        "price": price,
        "shares": record.shares,
        "estimate": estimate,
        "formula": "shares * price",
        "explanation": (
            f"{record.shares:,} shares * {_money(price)} = {_money(estimate)}"
        ),
    }


def _identity_trace(record: Record, ref: Any) -> dict[str, Any] | None:
    resolved = ref.resolve(record.cusip)
    if resolved is None:
        return None
    return {
        "lookup": "CUSIP_MAP[cusip]",
        "key": record.cusip,
        "name": resolved.get("name"),
        "ticker": resolved.get("ticker"),
        "former": resolved.get("former"),
    }


def _amendment_trace(record: Record, ref: Any) -> dict[str, Any] | None:
    correction = (
        ref.AMENDMENT_INDEX.get((record.filer, record.period, record.cusip))
        or ref.AMENDMENT_INDEX.get((record.filer, record.period, record.id))
        or ref.AMENDMENT_INDEX.get((record.filer, record.period))
    )
    if correction is None:
        return None
    return {
        "lookup": "AMENDMENT_INDEX",
        "keys_checked": [
            [record.filer, record.period, record.cusip],
            [record.filer, record.period, record.id],
            [record.filer, record.period],
        ],
        "correction": correction,
    }


def _freshness_trace(record: Record, ref: Any) -> dict[str, Any] | None:
    family = contract.source_family(record.source)
    status = ref.FEED_STATUS.get(family)
    if status is None:
        return None
    return {
        "lookup": "FEED_STATUS[source_family]",
        "key": family,
        "status": status,
    }


def _trusted_inputs(record: Record, ref: Any) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "reference_as_of": getattr(ref, "AS_OF", None),
        "identity": _identity_trace(record, ref),
        "price_recompute": _price_trace(record, ref),
        "amendment": _amendment_trace(record, ref),
        "freshness": _freshness_trace(record, ref),
    }
    return {key: value for key, value in inputs.items() if value is not None}


def trace_record(record: Record, verdict: Verdict, ref: Any) -> dict[str, Any]:
    family = contract.source_family(record.source)
    correction = verdict.evidence.get("correction")
    return {
        "row": record.id,
        "source": record.source,
        "source_family": family,
        "source_contract": contract.get_contract(record.source),
        "input": {
            "filer": record.filer,
            "form": record.form,
            "period": record.period,
            "entity_name": record.entity_name,
            "ticker": record.ticker,
            "cusip": record.cusip,
            "shares": record.shares,
            "value_usd": record.value_usd,
            "claimed_value": record.claimed_value,
        },
        "trusted_inputs": _trusted_inputs(record, ref),
        "executed_check": verdict.check_name,
        "decision": verdict.outcome.upper(),
        "reason": verdict.reason,
        "evidence": verdict.evidence,
        "correction": correction if isinstance(correction, dict) else None,
        "safety": (
            "auto-fix only when the corrected value is derivable from the trusted "
            "reference; otherwise the row stays HELD for a human"
        ),
    }
