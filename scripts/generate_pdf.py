#!/usr/bin/env python3
"""Generate CodeGraph architecture overview PDF (one A4 page) for Creator Colosseum.

Uses ReportLab Platypus (Paragraph / Preformatted / Spacer / Table), not canvas
drawString, so line breaks and monospace ASCII stay intact.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission" / "codegraph-architecture.pdf"

INK = HexColor("#111827")
MUTED = HexColor("#374151")
ACCENT = HexColor("#1D4ED8")
DONE = HexColor("#047857")
WIP = HexColor("#B45309")
PLAN = HexColor("#6B7280")

MARGIN = 1.27 * cm


def register_fonts() -> tuple[str, str, str]:
    """Return (body, body_bold, mono). Prefer real TTFs; fall back to builtins."""
    body, body_bold, mono = "Helvetica", "Helvetica-Bold", "Courier"
    try:
        pdfmetrics.registerFont(TTFont("Body", r"C:\Windows\Fonts\arial.ttf"))
        pdfmetrics.registerFont(TTFont("BodyBold", r"C:\Windows\Fonts\arialbd.ttf"))
        body, body_bold = "Body", "BodyBold"
    except Exception:
        pass
    for path in (
        r"C:\Windows\Fonts\consola.ttf",
        r"C:\Windows\Fonts\cour.ttf",
        r"C:\Windows\Fonts\DejaVuSansMono.ttf",
    ):
        p = Path(path)
        if p.exists():
            try:
                pdfmetrics.registerFont(TTFont("Mono", str(p)))
                mono = "Mono"
                break
            except Exception:
                continue
    return body, body_bold, mono


BODY, BODY_BOLD, MONO = register_fonts()

# Hyphenated terms are written with NO spaces around "-" (tree-sitter, zero-config, --at).
# ParagraphStyle.splitLongWords=0 keeps those tokens intact.

ARCH = """\
Source files (.ts/.py)  ->  tree-sitter parsers  ->  CodeNode + Edge
                                                          |
Git history (all commits)  ->  GitHistory  ->  SQLite / Dgraph
                                                          |
Commit msgs / ADRs / CHANGELOG  ->  Decision extractor
                                                          |
                                    CLI: index / why / graph / ...
                                                          |
                          Terminal card + Web viz + AI context pack"""

DATA_MODEL = """\
CodeNode: uid, kind, name, file_path, line_start, line_end,
          language, valid_from, valid_to, parent_uid
Edge: from_uid, to_uid, kind (uses / defined_by / contains)
Decision: content, reason, alternatives, status, source,
          source_ref, timestamp, author, constraints, confidence"""

COMMANDS = [
    ("codegraph index <path>", "Parse + ingest Git history + store"),
    ("codegraph why <file>:<line>", "Decision card for that line"),
    ("codegraph graph --at <date>", "Code graph at a past moment"),
    ("codegraph decisions --timeline", "Decision evolution chain"),
    ("codegraph conflicts", "Detect contradictory decisions"),
    ("codegraph export --for-ai", "Export AI agent context"),
    ("codegraph serve", "Local web visualization"),
]

TECH = [
    ("tree-sitter", "Multi-language parsing, incremental, industry standard"),
    ("GitPython", "Read-only access to real Git history"),
    ("Dgraph", "Native graph queries for multi-hop decision tracing"),
    ("Typer + Rich", "Fast CLI, readable terminal output"),
    ("pydantic", "Typed data models"),
    ("SQLite", "Default backend; zero-config, local-first"),
]

STATUS = [
    ("Done", "Product site (HTML/CSS/JS)", DONE),
    ("Done", "CLI with 6 commands", DONE),
    ("Done", "tree-sitter parsing for TypeScript and Python", DONE),
    ("Done", "SQLite storage", DONE),
    ("Done", "Real Git history traversal", DONE),
    ("Done", "Decision extraction from commits, ADRs, CHANGELOG", DONE),
    ("Done", "Real time-travel queries (graph --at)", DONE),
    ("Done", "25 tests passing", DONE),
    ("In progress", "Dgraph backend", WIP),
    ("Planned", "Web visualization (Cytoscape.js)", PLAN),
    ("Planned", "VSCode extension", PLAN),
]

ROADMAP = [
    ("v0.1.0", "CLI + SQLite (current)"),
    ("v0.2.0", "Real Git history + decision extraction"),
    ("v0.3.0", "Dgraph backend + time-travel queries"),
    ("v0.4.0", "Web visualization"),
    ("v0.5.0", "LLM-based decision extraction (local-first, Ollama)"),
    ("v0.6.0", "VSCode extension"),
]


def make_styles(body_size: float, mono_size: float) -> dict[str, ParagraphStyle]:
    body_lead = body_size + 1.5
    mono_lead = mono_size + 1.2
    return {
        "title": ParagraphStyle(
            "title",
            fontName=BODY_BOLD,
            fontSize=18,
            leading=20,
            textColor=INK,
            spaceAfter=2,
            alignment=TA_LEFT,
        ),
        "tagline": ParagraphStyle(
            "tagline",
            fontName=BODY_BOLD,
            fontSize=body_size,
            leading=body_lead,
            textColor=ACCENT,
            spaceAfter=4,
            splitLongWords=0,
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName=BODY_BOLD,
            fontSize=13,
            leading=15,
            textColor=INK,
            spaceBefore=3,
            spaceAfter=1.5,
        ),
        "body": ParagraphStyle(
            "body",
            fontName=BODY,
            fontSize=body_size,
            leading=body_lead,
            textColor=MUTED,
            spaceAfter=1,
            splitLongWords=0,
        ),
        "num": ParagraphStyle(
            "num",
            fontName=BODY,
            fontSize=body_size,
            leading=body_lead,
            textColor=MUTED,
            leftIndent=12,
            firstLineIndent=-12,
            spaceAfter=0.5,
            splitLongWords=0,
        ),
        "mono": ParagraphStyle(
            "mono",
            fontName=MONO,
            fontSize=mono_size,
            leading=mono_lead,
            textColor=INK,
            splitLongWords=0,
        ),
        "cmd": ParagraphStyle(
            "cmd",
            fontName=MONO,
            fontSize=mono_size,
            leading=mono_lead,
            textColor=INK,
            splitLongWords=0,
        ),
        "desc": ParagraphStyle(
            "desc",
            fontName=BODY,
            fontSize=body_size - 0.5,
            leading=body_lead - 1.5,
            textColor=MUTED,
            splitLongWords=0,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName=BODY,
            fontSize=8,
            leading=9.5,
            textColor=PLAN,
            spaceBefore=4,
            splitLongWords=0,
        ),
    }


def esc(text: str) -> str:
    """Escape Paragraph markup so <path> / <file>:<line> render literally."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def kv_table(rows, col0: float, col1: float, s, status_colors=None) -> Table:
    """Two-column key/value table. Keys mono, or colored bold when status_colors set."""
    data = []
    for i, (a, b) in enumerate(rows):
        key_style = ParagraphStyle(
            f"key{i}",
            fontName=BODY_BOLD if status_colors else MONO,
            fontSize=s["cmd"].fontSize,
            leading=s["cmd"].leading,
            textColor=(status_colors[i] if status_colors else INK),
            splitLongWords=0,
        )
        data.append([Paragraph(esc(a), key_style), Paragraph(esc(b), s["desc"])])
    t = Table(data, colWidths=[col0, col1], hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 0.4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.4),
            ]
        )
    )
    return t


def cmd_table(rows, s: dict[str, ParagraphStyle]) -> Table:
    """Commands as monospace Preformatted lines so <args> and --flags never wrap or vanish."""
    lines = []
    width = max(len(c) for c, _ in rows) + 2
    for cmd, desc in rows:
        lines.append(f"{cmd.ljust(width)}{desc}")
    pre = Preformatted("\n".join(lines), s["mono"])
    t = Table([[pre]], hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return t


def section_heading(text: str, s: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(text, s["h2"])


def left_right_columns(left: list, right: list, col_w: float, gap: float) -> Table:
    """Two-column layout so the dense lower half fits on one A4 page."""
    t = Table([[left, right]], colWidths=[col_w, col_w + gap], hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), gap),
                ("LEFTPADDING", (1, 0), (1, 0), 0),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return t


def build_story(s: dict[str, ParagraphStyle], page_w: float) -> list:
    content_w = page_w - 2 * MARGIN
    story = []

    story.append(Paragraph(esc("CodeGraph — Architecture Overview"), s["title"]))
    story.append(
        Paragraph(
            esc("Git blame tells you who changed it. CodeGraph tells you why."),
            s["tagline"],
        )
    )

    story.append(section_heading("Problem", s))
    story.append(
        Paragraph(
            esc(
                'Developers constantly ask "why is this code written this way?" '
                "git blame shows authorship. GitHub search shows text matches. "
                "ADR tools require manual writing. AI coding assistants see only "
                "the current file. No existing tool connects a line of code to "
                "the design decisions that shaped it."
            ),
            s["body"],
        )
    )

    story.append(section_heading("Solution — three layers, one graph", s))
    story.append(
        Paragraph(
            "<b>1. Structure:</b> "
            + esc(
                "tree-sitter parses TypeScript/Python into AST nodes "
                "and edges (uses / defined_by / contains)"
            ),
            s["num"],
        )
    )
    story.append(
        Paragraph(
            "<b>2. Time:</b> "
            + esc(
                "Every node carries valid_from / valid_to, derived from "
                "real Git history"
            ),
            s["num"],
        )
    )
    story.append(
        Paragraph(
            "<b>3. Decisions:</b> "
            + esc(
                "Extracted from commit messages, ADRs, and CHANGELOG, "
                "linked to the exact code lines they justify"
            ),
            s["num"],
        )
    )

    story.append(section_heading("Architecture", s))
    story.append(Preformatted(ARCH, s["mono"]))

    story.append(section_heading("Data model", s))
    story.append(Preformatted(DATA_MODEL, s["mono"]))

    story.append(section_heading("Seven commands", s))
    story.append(cmd_table(COMMANDS, s))

    # Lower half in two columns: left = tech, right = status + roadmap.
    gap = 10
    col_w = (content_w - gap) / 2

    left: list = [
        section_heading("Tech choices", s),
        kv_table(TECH, 68, col_w - 68, s),
    ]
    colors = [c for _, _, c in STATUS]
    status_rows = [(a, b) for a, b, _ in STATUS]
    right: list = [
        section_heading("Status (as of submission)", s),
        kv_table(status_rows, 58, col_w - 58, s, status_colors=colors),
        section_heading("Roadmap", s),
        kv_table(ROADMAP, 42, col_w - 42, s),
    ]
    story.append(Spacer(1, 2))
    story.append(left_right_columns(left, right, col_w, gap))

    story.append(
        Paragraph(
            esc(
                "Built by a 15-year-old self-taught developer.  ·  MIT License.  ·  "
                "https://github.com/fourwich/codegraph"
            ),
            s["footer"],
        )
    )
    return story


def render(out_path: Path, body_size: float, mono_size: float) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    s = make_styles(body_size=body_size, mono_size=mono_size)
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title="CodeGraph — Architecture Overview",
        author="fourwich",
        subject="Creator Colosseum submission — architecture overview",
        pageCompression=1,
    )
    doc.build(build_story(s, A4[0]))
    return out_path


def build() -> Path:
    """Build at 10pt body; if content spills past one page, rebuild at 9pt."""
    from pypdf import PdfReader

    OUT.parent.mkdir(parents=True, exist_ok=True)
    chosen = 10
    render(OUT, body_size=10, mono_size=8)
    n = len(PdfReader(str(OUT)).pages)
    if n > 1:
        chosen = 9
        render(OUT, body_size=9, mono_size=7.5)
        n = len(PdfReader(str(OUT)).pages)
    print(f"Wrote {OUT}")
    print(f"pages={n} body_size={chosen}pt")
    return OUT


if __name__ == "__main__":
    path = build()
    size = path.stat().st_size
    print(f"Size: {size} bytes ({size / 1024:.1f} KB)")
