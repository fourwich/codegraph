"""Tests for expanded decision extraction rules."""

from __future__ import annotations

from datetime import datetime, timezone

from codegraph.decisions.extractor import (
    decision_from_commit_subject,
    decisions_from_commit_body,
    looks_like_decision,
    split_commit_parts,
)
from codegraph.models import DecisionSource
from codegraph.decisions.extractor import extract_decisions_from_text

TS = datetime(2026, 9, 23, tzinfo=timezone.utc)


def test_build_commit_type_is_weak_decision() -> None:
    d = decision_from_commit_subject(
        "build(deps): bump qs minimum to 6.16.0",
        source_ref="commit x",
        timestamp=TS,
    )
    assert d is not None
    assert d.confidence == 0.55


def test_looks_like_decision_extended_keywords() -> None:
    assert looks_like_decision("We switched to Redis for latency")
    assert looks_like_decision("This avoids double counting")
    assert looks_like_decision("Migrated to ESM for compatibility")
    assert looks_like_decision("to fix CVE in body-parser")


def test_commit_body_bullets_extracted() -> None:
    msg = (
        "feat: add retry\n\n"
        "- Retry 3 times on Redis timeout because P99 matters\n"
        "- bump readme typo\n"
    )
    found = decisions_from_commit_body(msg, source_ref="commit y", timestamp=TS)
    assert len(found) == 1
    assert "because" in (found[0].reason + found[0].content).lower()
    assert found[0].confidence == 0.7


def test_split_commit_parts() -> None:
    subject, body = split_commit_parts("fix: x\n\n- one\n- two because y\n")
    assert subject.startswith("fix:")
    assert body


def test_extract_decisions_from_text_extended() -> None:
    found = extract_decisions_from_text(
        "Use feature flags due to rollout risk",
        source=DecisionSource.COMMIT,
        source_ref="commit z",
        timestamp=TS,
    )
    assert found and found[0].confidence >= 0.55
