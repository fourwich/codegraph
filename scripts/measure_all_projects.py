"""Re-measure every project after the edge-dedup fix.

Prints one line per repository with the numbers the documents quote, so the docs
can be updated from measurement instead of arithmetic.
"""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CG = str(ROOT / ".venv/Scripts/codegraph.exe")

REPOS = {
    "express": (ROOT / ".review/express", 200),
    "got": (ROOT / ".review/got", 200),
    "flask": (ROOT / ".review/flask", 200),
    "cobra": (ROOT / ".review/cobra", 200),
    "gson": (ROOT / ".review/gson", 200),
    "ripgrep": (ROOT / ".review/ripgrep", 200),
    "fmt": (ROOT / ".review/fmt", 200),
    "self": (ROOT, 50),
}

print(
    f"{'repo':9s} {'idx_nodes':>9s} {'live':>6s} {'idx_edges':>9s} "
    f"{'records':>8s} {'dec':>4s} {'reason':>7s} {'alt':>4s} {'bound':>6s}"
)
for label, (repo, depth) in REPOS.items():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [CG, "index", ".", "--full", "--depth", str(depth)],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if result.returncode != 0:
        print(f"  {label}: index failed rc={result.returncode}")
        continue

    # Two different node counts are in play and the docs quote both:
    # the index reports total stored versions, a `valid_to is null` query reports
    # live symbols. Printing both keeps a table honest about which it means.
    printed_nodes = re.search(r"Nodes:\s+(\d+)", result.stdout)
    printed_edges = re.search(r"Edges:\s+(\d+)", result.stdout)

    con = sqlite3.connect(str(repo / ".codegraph/graph.db"))
    live = con.execute("select count(*) from nodes where valid_to is null").fetchone()[0]
    edges = con.execute("select count(*) from edges").fetchone()[0]
    records = con.execute("select count(*) from decisions").fetchone()[0]
    decisions = con.execute(
        "select count(*) from decisions where tier='decision'"
    ).fetchone()[0]
    reason = con.execute(
        "select count(*) from decisions where tier='decision' and reason != ''"
    ).fetchone()[0]
    alt = con.execute(
        "select count(*) from decisions where tier='decision' and alternatives != '[]'"
    ).fetchone()[0]
    bound = con.execute(
        "select count(distinct l.decision_uid) from decision_code_links l "
        "join decisions d on d.uid = l.decision_uid where d.tier='decision'"
    ).fetchone()[0]
    con.close()

    total_nodes = int(printed_nodes.group(1)) if printed_nodes else live
    total_edges = int(printed_edges.group(1)) if printed_edges else edges
    print(
        f"{label:9s} {total_nodes:>9d} {live:>6d} {total_edges:>9d} "
        f"{records:>8d} {decisions:>4d} {reason:>7d} {alt:>4d} {bound:>6d}"
    )
