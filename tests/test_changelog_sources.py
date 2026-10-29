"""Changelog extraction must read the file names real projects actually use.

Python projects ship `CHANGES.rst` with reStructuredText headings. Reading only
`CHANGELOG.md` made the tool blind to them: Flask's release notes produced one
decision instead of the 56 that state a reason or a rejected alternative.
"""

from __future__ import annotations

from pathlib import Path

from codegraph.decisions.sources import extract_from_changelog
from codegraph.models import DecisionTier

MARKDOWN = """# Changelog

## Changed

- Drop the legacy flag because it was unused.
- Rename the helper for clarity.

## Removed

- The old exporter, replaced by the streaming one.
"""

RST = """Version 3.2.0
-------------

-   Use ``flit_core`` instead of ``setuptools`` as build backend.
-   Fix parsing IPv6 with port in ``run``.
-   ``redirect`` returns a ``303`` status code by default instead of ``302``.
"""


def _decisions(repo: Path):
    return extract_from_changelog(repo)


def test_markdown_changelog_yields_decisions(tmp_path: Path) -> None:
    (tmp_path / "CHANGELOG.md").write_text(MARKDOWN, encoding="utf-8")

    decisions = _decisions(tmp_path)

    assert decisions
    assert all(d.source_ref.startswith("CHANGELOG.md · ") for d in decisions)
    assert all(d.file_path == "CHANGELOG.md" for d in decisions)
    assert any("legacy flag" in d.content for d in decisions)


def test_rst_changelog_is_read(tmp_path: Path) -> None:
    """CHANGES.rst is the common Python layout and used to be ignored."""
    (tmp_path / "CHANGES.rst").write_text(RST, encoding="utf-8")

    decisions = _decisions(tmp_path)

    assert decisions
    assert all(d.source_ref.startswith("CHANGES.rst · Version 3.2.0") for d in decisions)
    assert any(d.alternatives for d in decisions)
    assert {d.tier for d in decisions} == {DecisionTier.DECISION}


def test_any_conventional_changelog_name_is_found(tmp_path: Path) -> None:
    (tmp_path / "NEWS.rst").write_text(RST, encoding="utf-8")

    decisions = _decisions(tmp_path)

    assert decisions
    assert all(d.file_path == "NEWS.rst" for d in decisions)


def test_markdown_wins_when_several_exist(tmp_path: Path) -> None:
    (tmp_path / "CHANGELOG.md").write_text(MARKDOWN, encoding="utf-8")
    (tmp_path / "CHANGES.rst").write_text(RST, encoding="utf-8")

    decisions = _decisions(tmp_path)

    assert {d.file_path for d in decisions} == {"CHANGELOG.md"}


def test_wrapped_bullets_are_joined(tmp_path: Path) -> None:
    (tmp_path / "CHANGES.rst").write_text(
        "Version 1.0\n-----------\n\n"
        "-   The session is marked as accessed for operations that only\n"
        "    read keys, because that matches user expectations.\n",
        encoding="utf-8",
    )

    decisions = _decisions(tmp_path)

    assert len(decisions) == 1
    assert "read keys" in decisions[0].content


def test_plain_release_notes_are_not_stored(tmp_path: Path) -> None:
    """A changelog line without a rationale is already readable in the file.

    Storing every release note as an event record would add hundreds of records
    that answer nothing (Flask has 537 bullets), so only bullets that state a
    reason or a rejected alternative become records at all.
    """
    (tmp_path / "CHANGELOG.md").write_text(
        "## Changed\n\n- Bump the minimum Python version to 3.10.\n", encoding="utf-8"
    )

    assert _decisions(tmp_path) == []


def test_no_changelog_returns_nothing(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# hi\n", encoding="utf-8")
    assert _decisions(tmp_path) == []
