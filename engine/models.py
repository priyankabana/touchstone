from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Record(BaseModel):
    id: str
    source: str
    filer: str
    form: str
    period: str
    as_of_date: str
    entity_name: str
    ticker: str
    cusip: str
    shares: int
    value_usd: float
    price: float | None = None
    accession: str | None = None
    claimed_value: float | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Record":
        return cls.model_validate(data)


class Verdict(BaseModel):
    outcome: Literal["true", "held", "unknown", "fixed"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence: dict[str, Any]
    check_name: str


class Proposal(BaseModel):
    diagnosis: str
    check_code: str
    rationale: str
    test_plan: str
    source: str
