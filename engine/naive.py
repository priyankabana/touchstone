from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_rows() -> list[dict[str, Any]]:
    with (DATA_DIR / "sample_records.json").open("r", encoding="utf-8") as handle:
        rows = json.load(handle)
    with (DATA_DIR / "novel_record.json").open("r", encoding="utf-8") as handle:
        rows.append(json.load(handle))
    return rows


def main() -> None:
    rows = _load_rows()
    print("id  filer                         entity                         STATUS   reason")
    print("--  ----------------------------  -----------------------------  -------- -----------------------")
    for row in rows:
        print(
            f"{row['id']:<3} "
            f"{row['filer'][:28]:<28} "
            f"{row['entity_name'][:29]:<29} "
            "HEALTHY  row loaded successfully"
        )
    print(f"naive pipeline: {len(rows)}/{len(rows)} healthy — shipped ✓")


if __name__ == "__main__":
    main()
