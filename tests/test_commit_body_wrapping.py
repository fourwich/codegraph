"""A hard-wrapped commit body must not become a mid-clause fragment.

Git wraps a body at ~72 columns, so a reason lands across lines:

    We want to have the "completion" command for such programs because it
    will allow the completion of flags and of arguments (if provided
    by the program).

Splitting per line produced a card whose entire Reason was "because it", which
reads as a bug to anyone looking at the output. `join_wrapped_lines` reattaches
the wrap before sentences are split.
"""

from __future__ import annotations

from codegraph.decisions.extractor import (
    join_wrapped_lines,
    split_commit_parts,
    split_sentences,
)

WRAPPED = """Remove the default "completion" cmd if it is alone (#1559)

When a program has no sub-commands, its root command can accept
arguments.  If we add the default "completion" command to such programs
they will now have a sub-command and will no longer accept arguments.

We want to have the "completion" command for such programs because it
will allow the completion of flags and of arguments (if provided
by the program).

Signed-off-by: Marc Khouzam"""


def test_wrapped_reason_is_rejoined() -> None:
    _subject, parts = split_commit_parts(WRAPPED)

    assert any("because it will allow the completion" in p for p in parts), parts


def test_no_part_ends_on_a_dangling_conjunction() -> None:
    """`because it` on its own is the defect this fixes."""
    _subject, parts = split_commit_parts(WRAPPED)

    for part in parts:
        assert not part.strip().endswith("because it"), part


def test_paragraphs_stay_separate() -> None:
    joined = join_wrapped_lines("first para line one\nline two\n\nsecond para")

    assert "first para line one line two" in joined
    assert "second para" in joined
    assert "\n\n" in joined


def test_bullets_start_their_own_paragraph() -> None:
    joined = join_wrapped_lines("prose line\n- bullet one\n- bullet two")

    assert "prose line" in joined
    assert "- bullet one" in joined


def test_single_line_is_unchanged() -> None:
    assert join_wrapped_lines("one sentence only") == "one sentence only"


def test_empty_body_is_safe() -> None:
    assert join_wrapped_lines("") == ""
    assert split_commit_parts("just a subject") == ("just a subject", [])


def test_sentence_split_still_splits_on_punctuation() -> None:
    parts = split_sentences("First point. Second point.")

    assert parts == ["First point.", "Second point."]
