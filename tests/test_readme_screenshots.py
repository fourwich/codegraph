"""The README screenshots must come from the tool, not from a drawing tool.

`docs/assets/*.svg` are generated from `docs/assets/captures/*.txt`, which are
real output from this repository. These tests fail if the two drift, so a
screenshot cannot quietly show something the CLI no longer prints.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "docs" / "assets" / "captures"
SVGS = ROOT / "docs" / "assets"

PAIRS = [
    ("why.txt", "why.svg"),
    ("index.txt", "index.svg"),
    ("conflicts.txt", "conflicts.svg"),
]


def _svg_body_lines(svg: Path, title: str) -> list[str]:
    """Return the rendered text lines of an SVG, excluding the title bar."""
    raw = svg.read_text(encoding="utf-8")
    texts = [html.unescape(t) for t in re.findall(r"<text[^>]*>(.*?)</text>", raw, re.S)]
    return [line for line in texts if line != title]


def test_svgs_are_well_formed() -> None:
    for svg in sorted(SVGS.glob("*.svg")):
        ET.parse(svg)  # raises on malformed XML


def test_captures_are_present_and_non_empty() -> None:
    for name, _ in PAIRS:
        path = CAPTURES / name
        assert path.is_file(), f"missing capture {name}"
        assert len(path.read_text(encoding="utf-8").strip()) > 40, name


def test_svg_matches_its_capture() -> None:
    """Every rendered line is the captured line, blank lines aside."""
    titles = {
        "why.svg": "codegraph why src/codegraph/storage.py:200",
        "index.svg": "codegraph index . --depth 50",
        "conflicts.svg": "codegraph conflicts",
    }
    for capture, svg in PAIRS:
        captured = [
            line.rstrip()
            for line in (CAPTURES / capture).read_text(encoding="utf-8").rstrip("\n").splitlines()
        ]
        rendered = _svg_body_lines(SVGS / svg, titles[svg])
        assert len(rendered) == len(captured), f"{svg}: line count drifted"
        for index, (want, got) in enumerate(zip(captured, rendered)):
            # A blank line is rendered as a single space to keep the row height.
            assert (want or " ") == got, f"{svg} line {index}: {want!r} != {got!r}"


def test_readme_references_the_screenshots() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in ("why.svg", "index.svg", "decisions.svg", "conflicts.svg"):
        assert name in readme, f"README does not show {name}"


def test_captures_quote_real_identifiers() -> None:
    """A capture has to mention something that exists in this repository."""
    why = (CAPTURES / "why.txt").read_text(encoding="utf-8")
    assert "src/codegraph/storage.py" in why
    assert "insert_nodes" in why, "the capture is from a real `why` run"
