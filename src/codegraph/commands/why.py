"""codegraph why：查询某行代码背后的决策来源。"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from codegraph.models import (
    CodeNode,
    Decision,
    find_decisions_for_file,
    find_decisions_for_location,
    normalize_location_path,
)
from codegraph.storage import connect, db_path_for_root, find_node_at_line

console = Console()

LOCATION_RE = re.compile(r"^(?P<file>.+):(?P<line>\d+)$")


class LocationError(ValueError):
    """User-supplied file:line is invalid."""


def parse_location(raw: str) -> tuple[str, int]:
    """Parse `file:line` into (path, line)."""
    value = raw.strip()
    if not value:
        raise LocationError("位置不能为空，请使用 形如 src/auth/session.ts:42 的格式")
    match = LOCATION_RE.match(value)
    if not match:
        raise LocationError(
            f"无法解析位置「{raw}」。正确格式：相对路径:行号，例如 src/auth/session.ts:42"
        )
    line_no = int(match.group("line"))
    if line_no < 1:
        raise LocationError(f"行号必须大于等于 1，收到：{line_no}")
    return normalize_location_path(match.group("file")), line_no


def format_status_label(status_value: str) -> str:
    """Map decision status to a Chinese label."""
    mapping = {
        "accepted": "✅ 现行有效",
        "superseded": "🔁 已被取代",
        "rejected": "⛔ 已否决",
    }
    return mapping.get(status_value, status_value)


def format_confidence(confidence: float) -> str:
    """Format 0-1 confidence as stars and percent."""
    percent = int(round(confidence * 100))
    stars = "★" * int(round(confidence * 5)) + "☆" * (5 - int(round(confidence * 5)))
    return f"{stars}  {percent}%"


def load_code_node(file_path: str, line: int, root: Path | None = None) -> CodeNode | None:
    """Load covering CodeNode from SQLite if an index exists."""
    db_path = db_path_for_root(root or Path.cwd())
    if not db_path.exists():
        return None
    try:
        conn = connect(db_path)
    except sqlite3.Error as exc:
        console.print(f"[yellow]warn[/] 无法打开图数据库 {db_path}: {exc}")
        return None
    try:
        return find_node_at_line(conn, file_path, line)
    finally:
        conn.close()


def render_code_node_header(node: CodeNode) -> None:
    """Render hit CodeNode summary at the top of the card."""
    panel = Panel(
        Text(
            f"  kind: {node.kind}    name: {node.name}\n"
            f"  range: {node.file_path}:{node.line_start}-{node.line_end}\n"
            f"  language: {node.language}",
            style="cyan",
        ),
        title="[bold]命中 CodeNode[/]",
        border_style="cyan",
        padding=(0, 2),
    )
    console.print(panel)


def build_decision_panel(decision: Decision, file_path: str, line: int) -> Panel:
    """Render one decision as a Rich Panel card."""
    body = Text()
    body.append("【代码位置】\n", style="bold cyan")
    body.append(f"  {file_path}:{line}\n")
    body.append("【决策摘要】\n", style="bold yellow")
    body.append(f"  {decision.content}\n")
    body.append("【原因】\n", style="bold yellow")
    body.append(f"  {decision.reason or '（未记录）'}\n")
    body.append("【替代方案】\n", style="bold yellow")
    if decision.alternatives:
        for item in decision.alternatives:
            body.append(f"  · {item}\n")
    else:
        body.append("  （无）\n")
    body.append("【决策来源】\n", style="bold yellow")
    body.append(f"  {decision.source.value} · {decision.source_ref}\n")
    body.append(
        f"  作者：{decision.author or '未知'} · 时间：{decision.timestamp.date().isoformat()}\n"
    )
    body.append("【当前状态】\n", style="bold yellow")
    body.append(f"  {format_status_label(decision.status.value)}\n")
    body.append("【相关约束】\n", style="bold yellow")
    if decision.constraints:
        for item in decision.constraints:
            body.append(f"  · {item}\n")
    else:
        body.append("  （无）\n")
    body.append("【可信度】\n", style="bold yellow")
    body.append(f"  {format_confidence(decision.confidence)}\n")
    return Panel(
        body,
        title=f"[bold]Decision {decision.uid}[/]",
        border_style="yellow",
        padding=(1, 2),
    )


def render_decision_card(file_path: str, line: int, decisions: list[Decision]) -> None:
    """Render decision cards for a location."""
    console.print(
        f"[bold cyan]查询[/] {file_path}:{line} → 命中 [bold]{len(decisions)}[/] 条决策\n"
    )
    for decision in decisions:
        console.print(build_decision_panel(decision, file_path, line))


def render_not_found(file_path: str, line: int | None = None) -> None:
    """Render empty-result hint."""
    location = f"{file_path}:{line}" if line is not None else file_path
    console.print("[bold yellow]未找到足够决策记录[/]")
    console.print(f"[dim]位置 {location} 暂无绑定的 Decision。可尝试：[/]")
    console.print("[dim]  codegraph index <repo>   # 先建立索引[/]")
    console.print("[dim]  codegraph decisions --file <path> --timeline[/]")


def why_command(location: str) -> None:
    """Query decision cards for a source location.

    Args:
        location: Location string like `src/auth/session.ts:42`.
    """
    try:
        file_path, line = parse_location(location)
    except LocationError as exc:
        console.print(f"[bold red]参数错误[/] {exc}")
        raise typer.Exit(code=2) from exc

    node = load_code_node(file_path, line)
    if node is not None:
        render_code_node_header(node)

    decisions = find_decisions_for_location(file_path, line)
    if not decisions:
        render_not_found(file_path, line)
        raise typer.Exit(code=1)

    render_decision_card(file_path, line, decisions)


def decisions_command(
    file: str = typer.Option(..., "--file", help="文件路径", metavar="PATH"),
    timeline: bool = typer.Option(False, "--timeline", help="按时间顺序展示演化链"),
) -> None:
    """List decision evolution for a file.

    Args:
        file: Target file path.
        timeline: Emit oldest-first when true.
    """
    rows = find_decisions_for_file(file)
    if not rows:
        render_not_found(file)
        raise typer.Exit(code=1)

    table = Table(title=f"决策演化 · {file}")
    table.add_column("时间", style="cyan")
    table.add_column("状态")
    table.add_column("摘要", overflow="fold")
    table.add_column("来源", style="dim")
    ordered = list(rows) if timeline else list(reversed(rows))
    for decision in ordered:
        table.add_row(
            decision.timestamp.date().isoformat(),
            decision.status.value,
            decision.content,
            decision.source_ref,
        )
    console.print(table)


app = typer.Typer(help="查询某行代码背后的决策来源")

if __name__ == "__main__":
    app()
