from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

import config
from engine import reference


DATA_SEC = "https://data.sec.gov"
WWW_SEC = "https://www.sec.gov"
ARCHIVES = "https://www.sec.gov/Archives/edgar/data"

_REQUESTS_USED = 0
_PINNED_FILING = "pinned_filing.json"


class EdgarBudgetExceeded(RuntimeError):
    pass


def _cache_path(name: str) -> Path:
    return config.CACHE_DIR / name


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _snapshot_provenance(data: dict[str, Any]) -> str:
    date = data.get("as_of") or data.get("snapshot_date") or reference.AS_OF
    return f"snapshot {date}"


def _pinned() -> dict[str, Any]:
    return _read_json(_cache_path(_PINNED_FILING))


def _request_json(url: str) -> dict[str, Any]:
    raw = _request_bytes(url)
    return json.loads(raw.decode("utf-8"))


def _request_bytes(url: str) -> bytes:
    global _REQUESTS_USED
    if _REQUESTS_USED >= config.EDGAR_REQUEST_BUDGET:
        raise EdgarBudgetExceeded("EDGAR request budget exhausted")
    _REQUESTS_USED += 1

    request = Request(url, headers={"User-Agent": config.EDGAR_UA})
    with urlopen(request, timeout=10) as response:
        return response.read()


def _offline_payload(
    cache_name: str,
    build_from_pinned: Callable[[dict[str, Any]], dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    cache_file = _cache_path(cache_name)
    if cache_file.exists():
        data = _read_json(cache_file)
    else:
        data = build_from_pinned(_pinned())
    return data, _snapshot_provenance(data)


def _live_or_snapshot(
    cache_name: str,
    fetch_live: Callable[[], dict[str, Any]],
    build_from_pinned: Callable[[dict[str, Any]], dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    if config.OFFLINE or not config.LIVE:
        return _offline_payload(cache_name, build_from_pinned)

    try:
        data = fetch_live()
        _write_json(_cache_path(cache_name), data)
        return data, "edgar_live"
    except Exception:
        return _offline_payload(cache_name, build_from_pinned)


def _clean_cik(cik: int | str) -> int:
    return int(str(cik).lstrip("0") or "0")


def _accession_slug(accession: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in accession)


def _xml_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element.iter():
        if _xml_name(child.tag) == name and child.text is not None:
            return child.text.strip()
    return None


def _as_float(value: str | None) -> float:
    if value is None:
        return 0.0
    return float(value.replace(",", ""))


def _as_int(value: str | None) -> int:
    return int(_as_float(value))


def _assert_full_dollar_values(rows: list[dict[str, Any]]) -> None:
    values = [abs(float(row["value_usd"])) for row in rows if "value_usd" in row]
    if not values:
        return
    largest = max(values)
    assert 1_000_000 <= largest <= 10_000_000_000_000


def _parse_infotable_xml(xml_bytes: bytes) -> dict[str, Any]:
    root = ET.fromstring(xml_bytes)
    rows: list[dict[str, Any]] = []
    for info in root.iter():
        if _xml_name(info.tag) != "infoTable":
            continue
        cusip = _child_text(info, "cusip") or ""
        resolved = reference.resolve(cusip)
        rows.append(
            {
                "name": _child_text(info, "nameOfIssuer") or "",
                "cusip": cusip,
                "ticker": resolved["ticker"] if resolved else "",
                "shares": _as_int(_child_text(info, "sshPrnamt")),
                "value_usd": _as_float(_child_text(info, "value")),
            }
        )
    _assert_full_dollar_values(rows)
    return {"as_of": reference.AS_OF, "rows": rows}


def submissions(cik: int | str) -> tuple[dict[str, Any], str]:
    clean_cik = _clean_cik(cik)
    cache_name = f"submissions_{clean_cik}.json"

    def live() -> dict[str, Any]:
        return _request_json(f"{DATA_SEC}/submissions/CIK{clean_cik:010d}.json")

    def snapshot(pinned: dict[str, Any]) -> dict[str, Any]:
        return {
            "as_of": pinned.get("as_of", reference.AS_OF),
            "cik": str(clean_cik),
            "filings": {"recent": []},
            "rows": pinned.get("rows", []),
        }

    return _live_or_snapshot(cache_name, live, snapshot)


def ticker_map() -> tuple[dict[str, Any], str]:
    cache_name = "ticker_map.json"

    def live() -> dict[str, Any]:
        return _request_json(f"{WWW_SEC}/files/company_tickers.json")

    def snapshot(pinned: dict[str, Any]) -> dict[str, Any]:
        return {
            "as_of": pinned.get("as_of", reference.AS_OF),
            "tickers": [
                {
                    "ticker": row["ticker"],
                    "name": row["name"],
                    "cusip": row["cusip"],
                }
                for row in pinned.get("rows", [])
            ],
        }

    return _live_or_snapshot(cache_name, live, snapshot)


def infotable(cik: int | str, accession: str) -> tuple[dict[str, Any], str]:
    clean_cik = _clean_cik(cik)
    accession_path = accession.replace("-", "")
    cache_name = f"infotable_{clean_cik}_{_accession_slug(accession)}.json"

    def live() -> dict[str, Any]:
        xml_bytes = _request_bytes(
            f"{ARCHIVES}/{clean_cik}/{accession_path}/infotable.xml"
        )
        data = _parse_infotable_xml(xml_bytes)
        _assert_full_dollar_values(data["rows"])
        return data

    def snapshot(pinned: dict[str, Any]) -> dict[str, Any]:
        _assert_full_dollar_values(pinned.get("rows", []))
        return pinned

    return _live_or_snapshot(cache_name, live, snapshot)


def pinned_filing_meta() -> dict[str, Any]:
    data = _pinned()
    return {
        "as_of": data.get("as_of", reference.AS_OF),
        "row_count": len(data.get("rows", [])),
        "path": str(_cache_path(_PINNED_FILING)),
    }
