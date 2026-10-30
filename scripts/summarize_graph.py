"""Summarize a graph: languages, decision quality, and structure sanity."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main() -> int:
    """Print one repository's graph facts."""
    db = Path(sys.argv[1] if len(sys.argv) > 1 else ".codegraph/graph.db")
    if not db.is_file():
        print(f"  no database at {db}", file=sys.stderr)
        return 2
    con = sqlite3.connect(str(db))
    q = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731

    print(f"# {db.parent.parent.name}")
    print("  languages:")
    for language, count in con.execute(
        "select language, count(*) from nodes where valid_to is null "
        "group by language order by 2 desc"
    ):
        print(f"    {language:12s} {count}")

    print(f"  live nodes       : {q('select count(*) from nodes where valid_to is null')}")
    print(f"  edges            : {q('select count(*) from edges')}")
    print(f"  records          : {q('select count(*) from decisions')}")
    tier_count = con.execute(
        "select count(*) from decisions where tier = ?", ("decision",)
    ).fetchone()[0]
    print(f"  decisions        : {tier_count}")

    bound = q(
        "select count(distinct l.decision_uid) from decision_code_links l "
        "join decisions d on d.uid = l.decision_uid where d.tier='decision'"
    )
    print(f"  decisions bound  : {bound}")

    stubs = q(
        "select count(*) from decisions where tier='decision' "
        "and reason != '' and length(reason) < 12"
    )
    print(f"  stub reasons     : {stubs}")

    empty = q("select count(*) from nodes where name is null or name = ''")
    bad = q("select count(*) from nodes where line_end < line_start")
    print(f"  empty names      : {empty}")
    print(f"  bad line ranges  : {bad}")

    print("  largest spans:")
    for name, path, start, end in con.execute(
        "select name, file_path, line_start, line_end from nodes "
        "where valid_to is null order by (line_end - line_start) desc limit 3"
    ):
        print(f"    {str(name)[:30]:30s} {path[:34]:34s} {start}-{end}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
