"""Compose a clean architecture PDF (fixed markup and table headers)."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path("submission") / "codegraph-architecture.pdf"

INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#4B5563")
ACCENT = colors.HexColor("#0F766E")
LINE = colors.HexColor("#D1D5DB")
BG = colors.HexColor("#F3F4F6")
HEAD_BG = colors.HexColor("#111827")


def esc(text: str) -> str:
    """Escape HTML specials and prevent -- → en-dash in Paragraph."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("--", "&#45;&#45;")
    )


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "T",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=20,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "tag": ParagraphStyle(
            "Tag",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            leading=12,
            textColor=ACCENT,
            spaceAfter=8,
        ),
        "h": ParagraphStyle(
            "H",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=INK,
            spaceBefore=6,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "B",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=MUTED,
            spaceAfter=2,
        ),
        "mono": ParagraphStyle(
            "M",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7.2,
            leading=9.5,
            textColor=INK,
            backColor=BG,
            borderPadding=5,
            spaceAfter=4,
        ),
        "cell": ParagraphStyle(
            "C",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.8,
            leading=10,
            textColor=INK,
        ),
        "small": ParagraphStyle(
            "S",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.8,
            leading=10,
            textColor=MUTED,
        ),
    }


def md_table(header: list[str], rows: list[list[str]], col_widths: list[float]) -> Table:
    """Build a table with light header text (plain strings, not Paragraphs)."""
    data = [list(header)]
    s = styles()
    for row in rows:
        data.append([Paragraph(esc(c), s["cell"]) for c in row])
    table = Table(data, hAlign="LEFT", colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("GRID", (0, 0), (-1, -1), 0.3, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def build_story() -> list:
    s = styles()
    story: list = []
    story.append(Paragraph("CodeGraph — Architecture Overview", s["title"]))
    story.append(
        Paragraph(
            "Git blame tells you who changed it. CodeGraph tells you why.",
            s["tag"],
        )
    )

    story.append(Paragraph("Problem", s["h"]))
    story.append(
        Paragraph(
            "Developers constantly ask “why is this code written this way?” "
            "git blame shows authorship. GitHub search shows text matches. "
            "ADR tools require manual writing. AI coding assistants see only the "
            "current file. No existing tool connects a line of code to the design "
            "decisions that shaped it.",
            s["body"],
        )
    )

    story.append(Paragraph("Solution — three layers, one graph", s["h"]))
    story.append(
        Paragraph(
            "<b>1. Structure</b> — tree-sitter parses TypeScript/Python into AST nodes "
            "and edges (uses / defined_by / contains)",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "<b>2. Time</b> — every node carries valid_from / valid_to from real Git history",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "<b>3. Decisions</b> — extracted from commit messages, ADRs, and CHANGELOG, "
            "linked to the code lines they justify",
            s["body"],
        )
    )

    story.append(Paragraph("Architecture", s["h"]))
    diagram = (
        "Source files (.ts / .py) --&gt; tree-sitter --&gt; CodeNode + Edge<br/>"
        "Git history (commits)   --&gt; GitHistory  --&gt; SQLite / Dgraph<br/>"
        "Commit/ADR/CHANGELOG    --&gt; Decision extractor<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|<br/>"
        "CLI: index / why / graph / ...<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|<br/>"
        "Terminal card + Web viz + AI context pack"
    )
    story.append(Paragraph(diagram, s["mono"]))

    story.append(Paragraph("Data model", s["h"]))
    story.append(
        Paragraph(
            "<b>CodeNode</b> — uid, kind, name, file_path, line_start, line_end, "
            "language, valid_from, valid_to, parent_uid",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Edge</b> — from_uid, to_uid, kind (uses / defined_by / contains)",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Decision</b> — content, reason, alternatives, status, source, "
            "source_ref, timestamp, author, constraints, confidence",
            s["body"],
        )
    )

    story.append(Paragraph("Seven commands", s["h"]))
    story.append(
        md_table(
            ["Command", "Purpose"],
            [
                ["codegraph index <path>", "Parse + ingest Git history + store"],
                ["codegraph why <file>:<line>", "Decision card for that line"],
                ["codegraph graph --at <date>", "Code graph at a past moment"],
                ["codegraph decisions --timeline", "Decision evolution chain"],
                ["codegraph conflicts", "Detect contradictory decisions"],
                ["codegraph export --for-ai", "Export AI agent context"],
                ["codegraph serve", "Local web visualization"],
            ],
            [62 * mm, 108 * mm],
        )
    )

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Tech choices", s["h"]))
    story.append(
        md_table(
            ["Layer", "Choice", "Reason"],
            [
                ["Parsing", "tree-sitter", "Multi-language, incremental"],
                ["Git", "GitPython", "Read-only real Git history"],
                ["Graph DB", "Dgraph", "Multi-hop decision tracing"],
                ["CLI", "Typer + Rich", "Fast CLI, readable output"],
                ["Models", "pydantic", "Typed data models"],
                ["Storage", "SQLite", "Zero-config local default"],
            ],
            [28 * mm, 38 * mm, 104 * mm],
        )
    )

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Status (as of submission)", s["h"]))
    story.append(
        md_table(
            ["Status", "Item"],
            [
                ["Done", "Product site · CLI (6 commands) · SQLite · real Git history"],
                ["Done", "Decision extraction · time-travel graph --at · 48 tests"],
                ["Done", "tree-sitter TS/Py/Java/Go/Rust/C++ · Web · VSCode · LLM hook"],
                ["In progress", "Dgraph backend (optional live cluster)"],
            ],
            [28 * mm, 142 * mm],
        )
    )

    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            "Built by a 15-year-old self-taught developer.<br/>"
            "MIT License · https://github.com/fourwich/codegraph",
            s["small"],
        )
    )
    return story


def main() -> None:
    """Write the architecture PDF under submission/."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="CodeGraph — Architecture Overview",
        author="CodeGraph",
    )
    doc.build(build_story())
    print(f"wrote {OUT.resolve()} bytes={OUT.stat().st_size}")


if __name__ == "__main__":
    main()
