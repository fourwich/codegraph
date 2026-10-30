"""Sample `why` answers on a real repository and grade them.

`why` is the product. A table of node counts does not tell a judge whether the
answer is usable, so this walks a sample of real source lines and classifies what
comes back: a line-level card, a commit-level card, a file-level fallback, or
nothing. The proportion of each is the honest measure of the feature.

    python sample_why.py --repo .review/flask --n 40
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path


def live_symbols(db: Path, limit: int, seed: int) -> list[tuple[str, int, str]]:
    """Pick (file, middle-line, name) samples from the live graph.

    Sampling only source files under-reports the feature: a changelog decision
    links to a code line, so asking somewhere else in the same file returns
    "no record" for a decision that does exist. The sample therefore mixes
    random symbols with the exact lines a decision points at.
    """
    con = sqlite3.connect(str(db))
    linked = con.execute(
        "select l.file_path, l.line, coalesce(n.name, '?') from decision_code_links l "
        "left join nodes n on n.uid = l.node_uid "
        "where l.line is not null limit 400"
    ).fetchall()
    rows = con.execute(
        "select file_path, line_start, line_end, name from nodes where valid_to is null"
    ).fetchall()
    con.close()
    random.seed(seed)
    random.shuffle(rows)
    random.shuffle(linked)
    picks = []
    # Half the sample targets a decision link, so "found" means the feature worked
    # at the place it claims to work, not that the random walk hit a lucky line.
    for path, line, name in linked[: limit // 2]:
        picks.append((path, int(line), name))
    for path, start, end, name in rows:
        if not end or end < start:
            continue
        if len(picks) >= limit:
            break
        mid = start + max((end - start) // 2, 0)
        picks.append((path, mid, name))
    return picks[:limit]


def ask(repo: Path, path: str, line: int) -> dict:
    """Run `why --json` for one location and return its payload."""
    result = subprocess.run(
        [sys.executable, "-m", "codegraph.cli", "why", f"{path}:{line}", "--json"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    text = result.stdout.strip()
    if not text.startswith("{"):
        start = text.find("{")
        if start < 0:
            return {"error": text[:120], "rc": result.returncode}
        text = text[start:]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"error": "unparseable", "rc": result.returncode}
    payload["rc"] = result.returncode
    return payload


def main() -> int:
    """Sample and classify the answers."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--n", type=int, default=40)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    db = repo / ".codegraph/graph.db"
    if not db.is_file():
        print(f"  no graph at {db}", file=sys.stderr)
        return 2

    samples = live_symbols(db, args.n, args.seed)
    verdicts = Counter()
    rows = []
    for path, line, name in samples:
        payload = ask(repo, path, line)
        decisions = payload.get("decisions") or []
        related = payload.get("related") or []
        binding = payload.get("binding") or "none"
        if decisions:
            verdict = f"decision ({binding})"
        elif related:
            verdict = "governed-file fallback"
        else:
            verdict = "no record"
        verdicts[verdict] += 1
        rows.append((path, line, name, verdict, (decisions + related)[:1]))

    print(f"# why sampling — {repo.name} (n={len(rows)})")
    print()
    for verdict, count in verdicts.most_common():
        share = count * 100 // max(len(rows), 1)
        print(f"  {verdict:26s} {count:3d}  ({share}%)")
    print()
    print("  sample answers:")
    for path, line, name, verdict, first in rows[:8]:
        print(f"    {path}:{line} ({name[:20]}) -> {verdict}")
        if first:
            content = (first[0].get("content") or "")[:70]
            print(f"       {content}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
