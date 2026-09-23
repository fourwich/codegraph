"""codegraph why：查询某行代码背后的决策来源。"""

from __future__ import annotations

import re
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from codegraph.data import find_decisions_for_location, normalize_location_path
from codegraph.models import Decision

console = Console()

# file:line 允许路径里有冒号盘符，因此用右侧最后一次冒号切分
LOCATION_RE = re.compile(r"^(?P<file>.+):(?P<line>\d+)$")


class LocationError(ValueError):
    """用户传入的 file:line 不合法。"""


def parse_location(raw: str) -> tuple[str, int]:
    """解析 `file:line`，失败时抛出 LocationError。

    Args:
        raw: 用户输入的位置字符串。

    Returns:
        (规范化路径, 行号) 元组。
    """
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
    """把决策状态映射为中文标签。"""
    mapping = {
        "accepted": "✅ 现行有效",
        "superseded": "🔁 已被取代",
        "rejected": "⛔ 已否决",
    }
    return mapping.get(status_value, status_value)


def format_confidence(confidence: float) -> str:
    """把 0-1 可信度格式化为百分比与星级。"""
    percent = int(round(confidence * 100))
    stars = "★" * int(round(confidence * 5)) + "☆" * (5 - int(round(confidence * 5)))
    return f"{stars}  {percent}%"


def build_decision_panel(decision: Decision, file_path: str, line: int) -> Panel:
    """把单条决策渲染成 Rich Panel 卡片。"""
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
    body.append(f"  作者：{decision.author or '未知'} · 时间：{decision.timestamp.date().isoformat()}\n")
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
    return Panel(body, title=f"[bold]Decision {decision.uid}[/]", border_style="yellow", padding=(1, 2))


def render_decision_card(file_path: str, line: int, decisions: list[Decision]) -> None:
    """渲染决策卡片；多条决策时依次输出。"""
    console.print(f"[bold cyan]查询[/] {file_path}:{line} → 命中 [bold]{len(decisions)}[/] 条决策\n")
    for decision in decisions:
        console.print(build_decision_panel(decision, file_path, line))


def why_command(location: str) -> None:
    """查询某行代码的决策来源卡片。

    Args:
        location: 形如 `src/auth/session.ts:42` 的位置。
    """
    try:
        file_path, line = parse_location(location)
    except LocationError as exc:
        console.print(f"[bold red]参数错误[/] {exc}")
        raise typer.Exit(code=2) from exc

    decisions = find_decisions_for_location(file_path, line)
    if not decisions:
        console.print("[bold yellow]未找到足够决策记录[/]")
        console.print(f"[dim]位置 {file_path}:{line} 暂无绑定的 Decision。可尝试：[/]")
        console.print("[dim]  codegraph index <repo>   # 先建立索引[/]")
        console.print("[dim]  codegraph decisions --file <path> --timeline[/]")
        raise typer.Exit(code=1)

    render_decision_card(file_path, line, decisions)


app = typer.Typer(help="查询某行代码背后的决策来源")

if __name__ == "__main__":
    app()
