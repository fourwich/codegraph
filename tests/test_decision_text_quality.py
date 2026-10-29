"""Decision text has to read like a statement, not like a clause fragment.

Two rounds of output showed the same problem: cards whose content was "Changed:
Index walks…", "now bracket the range" or "Update". The reader learns to ignore
the feature. These tests pin the polish and the fragment filter.
"""

from __future__ import annotations

from datetime import datetime, timezone

from codegraph.decisions.extractor import (
    decision_from_sentence,
    is_usable_decision_content,
    polish_alternative,
    polish_decision_content,
)
from codegraph.models import DecisionSource, DecisionTier

TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_structural_heading_is_dropped() -> None:
    assert (
        polish_decision_content("Changed: Index walks real Git history")
        == "Index walks real Git history"
    )
    assert polish_decision_content("Removed: the bundled samples") == "The bundled samples"


def test_version_heading_is_kept() -> None:
    """A version tells the reader which release introduced the change."""
    text = "Version 3.2.0: ``redirect`` returns ``303`` by default"
    assert polish_decision_content(text) == text


def test_sentence_is_capitalised_unless_it_starts_with_a_name() -> None:
    assert polish_decision_content("use sqlite as the store") == "Use sqlite as the store"
    assert polish_decision_content("demo.html plays the recording") == (
        "demo.html plays the recording"
    )
    assert polish_decision_content("`codegraph serve` opens the browser") == (
        "`codegraph serve` opens the browser"
    )


def test_trailing_punctuation_is_trimmed() -> None:
    assert polish_decision_content("Use SQLite;") == "Use SQLite"
    assert polish_decision_content("Use SQLite.") == "Use SQLite"


def test_alternative_spelling_is_not_changed() -> None:
    """`safe-buffer` and `setuptools` are package names, not sentences."""
    assert polish_alternative("safe-buffer (#6071)") == "safe-buffer (#6071)"
    assert polish_alternative("  setuptools.  ") == "setuptools"


def test_fragment_leads_are_rejected() -> None:
    for fragment in ("now bracket the range", "also bump the version", "thus the fix"):
        assert not is_usable_decision_content(fragment), fragment


def test_one_word_and_debris_are_rejected() -> None:
    assert not is_usable_decision_content("Update")
    assert not is_usable_decision_content("same run")


def test_statements_survive_the_filter() -> None:
    for statement in (
        "use sqlite",
        "use IO[bytes]",
        "--file is now a filter",
        "Index walks real Git history and versions CodeNodes",
    ):
        assert is_usable_decision_content(statement), statement


def _decision(sentence: str):
    return decision_from_sentence(
        sentence,
        source=DecisionSource.COMMIT,
        source_ref="commit abc",
        timestamp=TS,
        file_path="src/a.py",
    )


def test_fragment_decision_is_dropped() -> None:
    """A decision whose content is a fragment is not stored at all."""
    assert _decision("now bracket the range instead of illustrating one end of it.") is None


def test_event_is_kept_even_when_terse() -> None:
    """Plain history is still history; only decisions must stand on their own."""
    decision = _decision("Update")
    assert decision is not None
    assert decision.tier is DecisionTier.EVENT


def test_polished_decision_keeps_its_reason_and_alternative() -> None:
    decision = _decision("use node:buffer instead of safe-buffer.")
    assert decision is not None
    assert decision.content == "Use node:buffer"
    assert decision.alternatives == ["safe-buffer"]
    assert decision.tier is DecisionTier.DECISION
