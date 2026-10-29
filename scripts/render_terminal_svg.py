"""Render captured terminal output into a faithful SVG for README screenshots.

The SVG embeds the exact captured text, so it cannot drift from what the tool
actually printed. Input is plain text (ANSI already stripped) plus a title.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

MONO_W = 8.4  # advance width of the mono font at 14px, close enough for a box
LINE_H = 20
PAD = 18
TITLE_H = 30


def render(text: str, title: str, out: Path, max_lines: int | None = None) -> None:
    lines = text.replace("\t", "    ").splitlines()
    if max_lines:
        lines = lines[:max_lines]
    lines = [line.rstrip() for line in lines]
    width_chars = max((len(line) for line in lines), default=40)
    width = int(width_chars * MONO_W) + PAD * 2
    height = LINE_H * len(lines) + PAD * 2 + TITLE_H

    body = []
    for i, line in enumerate(lines):
        y = PAD + TITLE_H + LINE_H * (i + 1) - 5
        body.append(
            f'<text x="{PAD}" y="{y}" xml:space="preserve">'
            f'{html.escape(line) or " "}</text>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" font-family="ui-monospace, SFMono-Regular,
     Menlo, Consolas, 'DejaVu Sans Mono', monospace" font-size="14">
  <rect width="{width}" height="{height}" rx="8" fill="#1e2126"/>
  <rect width="{width}" height="{TITLE_H}" rx="8" fill="#2b3038"/>
  <rect y="{TITLE_H - 8}" width="{width}" height="8" fill="#2b3038"/>
  <circle cx="18" cy="{TITLE_H // 2}" r="5" fill="#ff5f57"/>
  <circle cx="36" cy="{TITLE_H // 2}" r="5" fill="#febc2e"/>
  <circle cx="54" cy="{TITLE_H // 2}" r="5" fill="#28c840"/>
  <text x="{width // 2}" y="{TITLE_H // 2 + 5}" text-anchor="middle"
        fill="#a9b1bd" font-size="12">{html.escape(title)}</text>
  <g fill="#d7dce3">{"".join(body)}</g>
</svg>
"""
    out.write_text(svg, encoding="utf-8", newline="")
    print(f"  {out.name}: {len(lines)} lines, {width}x{height}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    captures = root / "docs" / "assets" / "captures"
    assets = root / "docs" / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    jobs = [
        ("why.txt", "codegraph why src/codegraph/storage.py:200", "why.svg", None),
        ("index.txt", "codegraph index . --depth 50", "index.svg", None),
        ("decisions.txt", "codegraph decisions --timeline", "decisions.svg", 22),
        ("conflicts.txt", "codegraph conflicts", "conflicts.svg", None),
    ]
    for src, title, name, limit in jobs:
        path = captures / src
        if not path.is_file():
            print(f"  missing capture: {path}", file=sys.stderr)
            continue
        text = path.read_text(encoding="utf-8")
        # Keep the terminal chrome honest: drop a trailing blank line only.
        render(text.rstrip("\n"), title, assets / name, limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
