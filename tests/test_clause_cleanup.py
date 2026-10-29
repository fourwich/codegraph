"""A clause cut mid-phrase must not ship as a card tail.

Splitting a sentence at "because" / "instead of" can leave "(e.g." hanging and a
trailing conjunction. `clean_clause` trims those without inventing text.
"""

from __future__ import annotations

import pytest

from codegraph.decisions.extractor import clean_clause


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "to avoid errors from version mismatches (e.g.",
            "to avoid errors from version mismatches",
        ),
        ("because it avoids the extra copy and", "because it avoids the extra copy"),
        ("due to encodeurl", "due to encodeurl"),
        ("to fix CVE-2026-12590 (#7390)", "to fix CVE-2026-12590 (#7390)"),
        ("so that the session is not stored", "so that the session is not stored"),
        ("(see", ""),
        ("because the buffer was reused.", "because the buffer was reused"),
        ("  spaced   text  ", "spaced text"),
    ],
)
def test_clean_clause(raw: str, expected: str) -> None:
    assert clean_clause(raw) == expected


def test_a_balanced_parenthesis_is_kept() -> None:
    assert clean_clause("to avoid noise (see #6338)") == "to avoid noise (see #6338)"


def test_a_closed_clause_is_untouched() -> None:
    text = "because a local store needs no server"
    assert clean_clause(text) == text
