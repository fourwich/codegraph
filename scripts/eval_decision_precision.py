#!/usr/bin/env python
"""Measure decision-extraction precision on a real repository.

Reports how many extracted records are actual decisions (they state a reason or
a rejected alternative) versus plain history events, so the headline number in
the docs is a measured quality figure rather than a raw record count.

Usage:
    python scripts/eval_decision_precision.py <repo-path> [--depth N] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codegraph.decisions.sources import extract_all  # noqa: E402
from codegraph.models import Decision, DecisionTier  # noqa: E402


def summarize(decisions: list[Decision]) -> dict:
    """Build a precision summary for a list of extracted records."""
    decisions_only = [d for d in decisions if d.tier is DecisionTier.DECISION]
    events = [d for d in decisions if d.tier is not DecisionTier.DECISION]
    total = len(decisions) or 1
    return {
        "records": len(decisions),
        "decisions": len(decisions_only),
        "events": len(events),
        "decision_share": round(len(decisions_only) / total, 4),
        "decisions_with_reason": sum(1 for d in decisions_only if (d.reason or "").strip()),
        "decisions_with_alternative": sum(1 for d in decisions_only if d.alternatives),
        "decision_categories": dict(Counter(d.category for d in decisions_only)),
        "decision_sources": dict(Counter(d.source.value for d in decisions_only)),
        "event_categories": dict(Counter(d.category for d in events)),
        "by_confidence": dict(Counter(round(d.confidence, 2) for d in decisions_only)),
        "sample_decisions": [
            {
                "content": d.content,
                "reason": d.reason[:80],
                "alternatives": d.alternatives,
                "category": d.category,
                "confidence": d.confidence,
                "source_ref": d.source_ref,
            }
            for d in decisions_only[:15]
        ],
        "sample_events": [d.content for d in events[:10]],
    }


def render(repo: str, depth: int, summary: dict) -> str:
    """Render a human-readable report."""
    lines = [
        f"# Decision extraction precision — {repo} (depth {depth})",
        "",
        f"records extracted      : {summary['records']}",
        f"  tier=decision        : {summary['decisions']} "
        f"({summary['decision_share'] * 100:.1f}%)",
        f"  tier=event           : {summary['events']}",
        "",
        f"decisions with reason  : {summary['decisions_with_reason']}",
        f"decisions with rejected alternative: {summary['decisions_with_alternative']}",
        f"decision categories    : {summary['decision_categories']}",
        f"decision sources       : {summary['decision_sources']}",
        f"decision confidence    : {summary['by_confidence']}",
        f"event categories       : {summary['event_categories']}",
        "",
        "## Sample decisions",
        "",
    ]
    for item in summary["sample_decisions"]:
        lines.append(f"- [{item['confidence']}] ({item['category']}) {item['content']}")
        if item["reason"]:
            lines.append(f"    reason: {item['reason']}")
        if item["alternatives"]:
            lines.append(f"    alternatives: {item['alternatives']}")
    lines += ["", "## Sample events (hidden by default)", ""]
    lines += [f"- {c}" for c in summary["sample_events"]]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="Repository path")
    parser.add_argument("--depth", type=int, default=200, help="Commits to walk")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--out", default="", help="Write the report to this file")
    args = parser.parse_args()

    root = Path(args.repo).expanduser().resolve()
    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        return 2

    decisions = extract_all(root, depth=args.depth)
    summary = summarize(decisions)
    report = json.dumps(summary, indent=2, ensure_ascii=False) if args.json else render(
        str(root), args.depth, summary
    )
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
