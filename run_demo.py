from __future__ import annotations

from engine import router
from ingest import inject


def _status(verdict) -> str:
    return verdict.outcome.upper()


def _print_row(record, verdict) -> None:
    print(
        f"{record.id:<3} "
        f"{record.filer[:28]:<28} "
        f"{record.entity_name[:30]:<30} "
        f"{_status(verdict):<7} "
        f"{verdict.reason}"
    )


def _print_table(rows) -> None:
    print("id  filer                         entity                         STATUS  reason")
    print("--  ----------------------------  -----------------------------  ------- ------------------------------------------------------------")
    for record, verdict in rows:
        _print_row(record, verdict)


def _counts(rows) -> tuple[int, int, int, int]:
    true_count = sum(1 for _record, verdict in rows if verdict.outcome == "true")
    fixed_count = sum(1 for _record, verdict in rows if verdict.outcome == "fixed")
    held_count = sum(1 for _record, verdict in rows if verdict.outcome == "held")
    unknown_count = sum(1 for _record, verdict in rows if verdict.outcome == "unknown")
    return true_count, fixed_count, held_count, unknown_count


def main() -> None:
    injection_line = inject.write_outputs()
    conn, records = router.seed_silent()
    try:
        print(injection_line)
        print()

        batch_rows = router.run_batch(records, conn)
        _print_table(batch_rows)

        print()
        novel = router.load_novel()
        novel_row = (novel, router.run_record(novel, conn))
        print("new record")
        _print_table([novel_row])

        all_rows = batch_rows + [novel_row]
        true_count, fixed_count, held_count, unknown_count = _counts(all_rows)
        print()
        print(
            f"result: {true_count} TRUE · {fixed_count} FIXED · "
            f"{held_count} HELD · {unknown_count} UNKNOWN"
        )
        print("model calls this run: 0")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
