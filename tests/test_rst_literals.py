"""reStructuredText marks a literal with two backticks, markdown with one.

Flask's changelog is `CHANGES.rst`, where every symbol is written ``like this``.
Matching only the single-backtick form meant the binder never saw most of the
identifiers a Python project's release notes name, so `why` answered "no record"
for decisions that were right there in the text.
"""

from __future__ import annotations

from codegraph.commands.index import BACKTICKED_IDENT, BACKTICKED_PATH


def test_rst_double_backticks_are_read() -> None:
    # A bare number is a literal in rst too, but it is not an identifier, so the
    # pattern correctly keeps only the symbol.
    assert BACKTICKED_IDENT.findall("``redirect`` returns a ``303``") == ["redirect"]


def test_markdown_single_backticks_still_work() -> None:
    assert BACKTICKED_IDENT.findall("`insert_nodes` is the entry point") == ["insert_nodes"]


def test_mixed_styles_in_one_line() -> None:
    text = "`storage.py` uses ``insert_nodes`` and `query_decisions_for_line_links`"
    found = BACKTICKED_IDENT.findall(text)
    assert "insert_nodes" in found
    assert "query_decisions_for_line_links" in found


def test_rst_path_literal_is_recognised() -> None:
    assert BACKTICKED_PATH.findall("see ``src/flask/app.py``") == ["src/flask/app.py"]


def test_markdown_path_literal_is_recognised() -> None:
    assert BACKTICKED_PATH.findall("see `src/codegraph/index.py`") == ["src/codegraph/index.py"]


def test_prose_inside_backticks_does_not_become_an_identifier() -> None:
    """A literal with a space is prose, not a symbol."""
    assert BACKTICKED_IDENT.findall("``use flit_core instead``") == []


def test_dotted_identifier_is_kept_whole() -> None:
    assert BACKTICKED_IDENT.findall("``Flask.select_jinja_autoescape``") == [
        "Flask.select_jinja_autoescape"
    ]
