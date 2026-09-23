"""CodeGraph Typer CLI 入口。"""

from __future__ import annotations

import typer

from codegraph import __version__
from codegraph.commands.graph import graph_command
from codegraph.commands.index import index_command
from codegraph.commands.why import decisions_command, why_command

app = typer.Typer(
    name="codegraph",
    help=(
        "CodeGraph：把代码结构、历史变更和设计决策变成一张可查询的图。\n\n"
        "MVP 阶段使用内置假数据演示完整命令流程。"
    ),
    add_completion=True,
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _version_callback(value: bool) -> None:
    """打印版本号并退出。"""
    if value:
        typer.echo(f"codegraph {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="显示版本号并退出",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """CodeGraph 命令行工具入口。"""


app.command(
    name="index",
    help="解析代码 + 摄取 Git 历史 + 写入图（MVP 模拟索引）",
    rich_help_panel="核心命令",
)(index_command)

app.command(
    name="why",
    help="查询某行代码背后的决策来源卡片，例如 why src/auth/session.ts:42",
    rich_help_panel="核心命令",
)(why_command)

app.command(
    name="graph",
    help="输出指定时刻的代码图摘要，例如 graph --at 2024-11-02 --scope src",
    rich_help_panel="核心命令",
)(graph_command)

app.command(
    name="decisions",
    help="返回文件的决策演化链，例如 decisions --file src/auth/session.ts --timeline",
    rich_help_panel="核心命令",
)(decisions_command)


if __name__ == "__main__":
    app()
