"""Measure conflict-detection precision and explain rejected candidates.

`codegraph conflicts` reports nothing when two decisions merely share a folder or a
generic word. This script separates "no contradiction exists" from "the detector
cannot see it": it prints the conflicts it found, plus every same-place pair that
matched an opposite term but was rejected by the topic gate, with the overlap that
decided it.

Usage:
    python scripts/eval_conflict_precision.py <repo>        # needs an indexed repo
    python scripts/eval_conflict_precision.py <repo> --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codegraph.commands.conflicts import load_decisions  # noqa: E402
from codegraph.decisions.conflicts import (  # noqa: E402
    TOPIC_SIMILARITY,
    _comparable,
    _opposite_hits,
    _overlap,
    _same_place,
    detect_all,
)


def measure(repo: Path) -> dict:
    """Return counts and rejected candidates for one indexed repository."""
    previous = Path.cwd()
    os.chdir(repo)
    try:
        decisions = load_decisions()
    finally:
        os.chdir(previous)

    conflicts = detect_all(decisions)

    same_place = 0
    with_opposites = 0
    rejected = []
    for index, a in enumerate(decisions):
        for b in decisions[index + 1 :]:
            if not _same_place(a, b):
                continue
            same_place += 1
            matched = _opposite_hits(a, b)
            if not matched:
                continue
            with_opposites += 1
            if _comparable(a, b, matched):
                continue
            rejected.append(
                {
                    "a": a.content[:120],
                    "b": b.content[:120],
                    "matched": matched,
                    "overlap": round(_overlap(a, b), 2),
                }
            )

    return {
        "repo": str(repo),
        "decisions": len(decisions),
        "conflicts": [
            {
                "type": c.type,
                "location": c.location,
                "a": c.decision_a.content[:120],
                "b": c.decision_b.content[:120],
                "matched": list(c.matched_words),
            }
            for c in conflicts
        ],
        "same_place_pairs": same_place,
        "pairs_with_opposite_terms": with_opposites,
        "rejected_by_topic_gate": rejected,
        "topic_threshold": TOPIC_SIMILARITY,
    }


def main() -> int:
    """Print a human-readable or JSON report for one repository."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="Repository root (indexed)")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not (repo / ".codegraph" / "graph.db").is_file():
        print(f"No index found at {repo}. Run codegraph index first.", file=sys.stderr)
        return 2

    result = measure(repo)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"# Conflict precision — {result['repo']}")
    print()
    print(f"decisions            : {result['decisions']}")
    print(f"conflicts reported   : {len(result['conflicts'])}")
    print(f"same-place pairs     : {result['same_place_pairs']}")
    print(f"... with opposite terms: {result['pairs_with_opposite_terms']}")
    print(f"... rejected by topic gate: {len(result['rejected_by_topic_gate'])}"
          f" (threshold {result['topic_threshold']})")
    print()
    print("## Reported conflicts")
    if not result["conflicts"]:
        print("(none)")
    for conflict in result["conflicts"]:
        print(f"- [{conflict['type']}] {conflict['location']} {conflict['matched']}")
        print(f"  A: {conflict['a']}")
        print(f"  B: {conflict['b']}")
    print()
    print("## Rejected candidates (opposite words, different topic)")
    if not result["rejected_by_topic_gate"]:
        print("(none)")
    for pair in result["rejected_by_topic_gate"]:
        print(f"- matched={pair['matched']} overlap={pair['overlap']}")
        print(f"  A: {pair['a']}")
        print(f"  B: {pair['b']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
