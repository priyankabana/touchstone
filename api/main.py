from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError

import config
from agent import run_agent
from engine import finalize as finalizer
from engine import router
from engine.models import Record, Verdict
from ingest import inject
from store import db


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
UI_PATH = ROOT / "ui" / "console.html"
ALLOWED_ORIGINS = ["http://127.0.0.1:8000", "http://localhost:8000"]

app = FastAPI(title="Touchstone", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)


class ApprovalRequest(BaseModel):
    proposal_id: int


class FinalizeRequest(BaseModel):
    records: list[dict[str, Any]] | None = None
    reference: dict[str, Any] | None = None
    as_of_date: str | None = None


def _injection_line() -> str:
    path = DATA_DIR / "injection_log.json"
    if not path.exists():
        return inject.write_outputs()
    with path.open("r", encoding="utf-8") as handle:
        return str(json.load(handle)["line"])


def _ensure_db() -> None:
    try:
        conn = db.connect()
        try:
            db.count(conn, "records")
            db.count(conn, "checks")
            return
        finally:
            conn.close()
    except (sqlite3.Error, ValueError):
        pass

    conn, _records = router.seed_silent()
    conn.close()


def _state_counts() -> tuple[int, int]:
    _ensure_db()
    conn = db.connect()
    try:
        return db.count(conn, "records"), db.count(conn, "checks")
    finally:
        conn.close()


def _record_response(record: Record, verdict: Verdict) -> dict[str, Any]:
    return {
        "id": record.id,
        "filer": record.filer,
        "entity": record.entity_name,
        "outcome": verdict.outcome,
        "reason": verdict.reason,
        "evidence": verdict.evidence,
    }


def _load_proposal(proposal_id: int) -> dict[str, Any]:
    conn = db.connect()
    try:
        proposal = db.get_proposal(conn, proposal_id)
    finally:
        conn.close()
    if proposal is None:
        raise HTTPException(status_code=404, detail="proposal not found")
    return proposal


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(str(value).replace(",", "").replace("$", ""))


def _normalize_upload_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    source = row.get("record") if isinstance(row.get("record"), dict) else row
    as_of = source.get("as_of_date") or source.get("period") or "2026-03-31"
    price = source.get("price")
    claimed_value = source.get("claimed_value")
    return {
        "id": str(source.get("id") or f"upload-{index + 1}"),
        "source": str(source.get("source") or "uploaded"),
        "filer": str(source.get("filer") or source.get("owner") or "Uploaded file"),
        "form": str(source.get("form") or "UPLOAD"),
        "period": str(source.get("period") or as_of),
        "as_of_date": str(as_of),
        "entity_name": str(
            source.get("entity_name")
            or source.get("entity")
            or source.get("company")
            or source.get("name")
            or "Uploaded row"
        ),
        "ticker": str(source.get("ticker") or source.get("symbol") or ""),
        "cusip": str(source.get("cusip") or ""),
        "shares": int(_number(source.get("shares"), 0.0)),
        "value_usd": _number(
            source.get("value_usd")
            if source.get("value_usd") is not None
            else source.get("value")
            if source.get("value") is not None
            else source.get("market_value"),
            0.0,
        ),
        "price": None if price is None or price == "" else _number(price),
        "accession": source.get("accession"),
        "claimed_value": None
        if claimed_value is None or claimed_value == ""
        else _number(claimed_value),
    }


@app.get("/")
def console() -> FileResponse:
    return FileResponse(UI_PATH)


@app.get("/api/state")
def state() -> dict[str, Any]:
    record_count, check_count = _state_counts()
    return {
        "record_count": record_count,
        "check_count": check_count,
        "injection_log": _injection_line(),
    }


@app.post("/api/run")
def run_batch() -> dict[str, Any]:
    inject.write_outputs()
    conn, records = router.seed_silent()
    try:
        rows = [
            _record_response(record, verdict)
            for record, verdict in router.run_batch(records, conn)
        ]
    finally:
        conn.close()
    return {"records": rows}


@app.post("/api/novel")
def run_novel() -> dict[str, Any]:
    inject.write_outputs()
    conn, _records = router.seed_silent()
    try:
        record = router.load_novel()
        verdict = router.run_record(record, conn)
        return _record_response(record, verdict)
    finally:
        conn.close()


@app.post("/api/agent/propose")
def propose_agent_check() -> dict[str, Any]:
    result = run_agent.propose()
    proposal_id = int(result["proposal_id"])
    proposal = _load_proposal(proposal_id)
    diff_lines = ["+ " + line for line in proposal["check_code"].splitlines()]
    return {
        "proposal_id": proposal_id,
        "diagnosis": proposal["diagnosis"],
        "diff_lines": diff_lines,
        "backtest": proposal["gate"],
    }


@app.post("/api/agent/approve")
def approve_agent_check(body: ApprovalRequest) -> dict[str, Any]:
    result = run_agent.approve(body.proposal_id)
    if not result.get("approved"):
        raise HTTPException(status_code=400, detail=result["reason"])
    return {
        "outcome": result["outcome"],
        "reason": result["reason"],
        "library": result["library"],
    }


@app.post("/api/finalize")
def finalize_dataset(body: FinalizeRequest | None = None) -> dict[str, Any]:
    records = None
    reference_snapshot = None
    write_files = True
    if body is not None and body.records is not None:
        try:
            records = [
                Record.from_json(_normalize_upload_row(row, index))
                for index, row in enumerate(body.records)
            ]
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail="uploaded JSON rows do not match the Touchstone record schema") from exc
        reference_snapshot = dict(body.reference or {})
        if body.as_of_date and "as_of_date" not in reference_snapshot:
            reference_snapshot["as_of_date"] = body.as_of_date
        write_files = False
    result = finalizer.process(
        records=records,
        reference_snapshot=reference_snapshot,
        write_files=write_files,
    )
    return {
        "summary": result["summary"],
        "rows": result["rows"],
        "corrected_rows": result["corrected_rows"],
        "report": result["report"],
    }


@app.get("/api/report")
def correction_report() -> dict[str, Any]:
    if not finalizer.CORRECTION_REPORT.exists():
        result = finalizer.process()
        return {"changes": result["report"]}
    with finalizer.CORRECTION_REPORT.open("r", encoding="utf-8") as handle:
        return {"changes": json.load(handle)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
