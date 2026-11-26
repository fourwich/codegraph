"""Three fixes that came out of dogfooding CodeGraph on flask.

I indexed a repository I had never read and looked at what the tool produced. These pin
what was wrong.

**A bare value is not a rejected alternative.** `redirect returns 303 instead of 302`
produced the alternative `302`, which made a changelog line pass as a decision. On flask
that was 36 of 54 "decisions": cards that read like release notes.

**A version heading is metadata, not content.** 54 cards opened with `Version 3.2.0:` and
answered "what changed in 3.2" instead of "why is this line here".

**A changelog date is not the index date.** Every record carried the moment `index` ran,
so flask 0.2 (2011) displayed as 2026.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from codegraph.decisions.extractor import (
    decision_from_sentence,
    polish_decision_content,
    split_decision_parts,
    version_heading,
)
from codegraph.models import DecisionSource, DecisionTier

NOW = datetime(2026, 11, 26, tzinfo=timezone.utc)


# --- fix 1: a bare value is not a rejected alternative -------------------------------


@pytest.mark.parametrize(
    "clause",
    ["302", "300", "``302``", "`302`", "**200**", "0", "100%"],
)
def test_a_bare_number_is_not_a_rejected_alternative(clause: str) -> None:
    """`instead of 302` describes a previous value, not a design that was turned down."""
    _content, _reason, alternatives = split_decision_parts(
        f"``redirect`` returns a ``303`` status code by default instead of {clause}."
    )
    assert alternatives == [], f"{clause!r} was accepted as an alternative"


@pytest.mark.parametrize(
    "clause",
    [
        "``setuptools``",
        "safe-buffer",
        "node:buffer",
        "127.0.0.1",
        "0.0.0.0",
        "``None``",
        "silently coercing the value",
        "only switching ``POST`` to ``GET``",
    ],
)
def test_a_named_approach_survives_as_an_alternative(clause: str) -> None:
    """Identifiers, addresses, keywords and behaviours are concrete proposals."""
    _content, _reason, alternatives = split_decision_parts(
        f"Use the new path instead of {clause}."
    )
    assert alternatives, f"{clause!r} should be a rejected alternative"


def test_a_single_english_word_is_not_an_approach() -> None:
    """`instead of fast` is a property of the choice, not a design."""
    _content, _reason, alternatives = split_decision_parts("Store it instead of fast.")
    assert alternatives == []


def test_the_302_case_no_longer_becomes_a_decision() -> None:
    """The exact line from flask's CHANGES.rst that produced a false card."""
    decision = decision_from_sentence(
        "``redirect`` returns a ``303`` status code by default instead of ``302``.",
        source=DecisionSource.COMMIT,
        source_ref="CHANGES.rst",
        timestamp=NOW,
        file_path="CHANGES.rst",
    )
    assert decision is not None
    assert decision.tier is DecisionTier.EVENT


def test_a_real_rejection_still_becomes_a_decision() -> None:
    decision = decision_from_sentence(
        "Use ``flit_core`` instead of ``setuptools`` as build backend.",
        source=DecisionSource.COMMIT,
        source_ref="CHANGES.rst",
        timestamp=NOW,
        file_path="CHANGES.rst",
    )
    assert decision is not None
    assert decision.tier is DecisionTier.DECISION
    assert any("setuptools" in alternative for alternative in decision.alternatives)


# --- fix 2: the version heading is metadata ------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "Version 3.2.0: ``redirect`` returns ``303`` by default",
            "``redirect`` returns ``303`` by default",
        ),
        ("Version 0.2: Server listens on 127.0.0.1 by default", "Server listens on 127.0.0.1 by default"),
        ("v3.2.0: Drop Python 3.9", "Drop Python 3.9"),
        ("0.2 (2011-05-06): Server listens on 127.0.0.1", "Server listens on 127.0.0.1"),
    ],
)
def test_version_heading_is_stripped(raw: str, expected: str) -> None:
    assert polish_decision_content(raw) == expected


def test_a_structural_heading_is_still_stripped() -> None:
    assert polish_decision_content("Changed: Drop support for Python 3.9") == (
        "Drop support for Python 3.9"
    )


# --- fix 3: a changelog date is recoverable -----------------------------------------


def test_a_dated_heading_yields_the_release_date() -> None:
    release, date = version_heading("0.2 (2011-05-06): Server listens on 127.0.0.1")
    assert release == "0.2"
    assert date is not None
    assert date.date().isoformat() == "2011-05-06"


def test_an_undated_heading_yields_no_date() -> None:
    """`Version 3.2.0` alone says which release, not when."""
    release, date = version_heading("Version 3.2.0: Something changed")
    assert release == "3.2.0"
    assert date is None


def test_a_sentence_without_a_heading_yields_nothing() -> None:
    assert version_heading("Fix parsing IPv6 with port in run.") == ("", None)


def test_the_malformed_date_is_rejected_rather_than_guessed() -> None:
    """A month 13 is not a date; the caller keeps its own timestamp instead."""
    _release, date = version_heading("0.2 (2011-13-45): Something changed")
    assert date is None
