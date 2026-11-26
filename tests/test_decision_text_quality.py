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
    version_heading,
)
from codegraph.models import DecisionSource, DecisionTier

TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_structural_heading_is_dropped() -> None:
    assert (
        polish_decision_content("Changed: Index walks real Git history")
        == "Index walks real Git history"
    )
    assert polish_decision_content("Removed: the bundled samples") == "The bundled samples"


def test_version_heading_is_stripped_from_the_card() -> None:
    """The heading names a release; on the card it read like a changelog line.

    Dogfooding on flask: 54 of 229 cards opened with `Version X.Y:` and answered
    "what changed in 3.2" instead of "why is this line here". The release is still
    available through `version_heading`, which the next test covers.
    """
    text = "Version 3.2.0: ``redirect`` returns ``303`` by default"
    assert polish_decision_content(text) == "``redirect`` returns ``303`` by default"


def test_version_heading_is_recoverable() -> None:
    """Stripping the heading must not lose which release introduced the change."""
    release, date = version_heading("Version 3.2.0: ``redirect`` returns ``303``")
    assert release == "3.2.0"
    assert date is None


def test_version_heading_carries_a_date_when_the_changelog_states_one() -> None:
    """A dated heading is the only source of a real decision date in a changelog."""
    release, date = version_heading("0.2 (2011-05-06): Server listens on 127.0.0.1")
    assert release == "0.2"
    assert date is not None
    assert date.date().isoformat() == "2011-05-06"


def test_a_non_version_heading_yields_no_release() -> None:
    assert version_heading("Changed: Drop support for Python 3.9") == ("", None)


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
