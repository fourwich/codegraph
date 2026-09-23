"""按文件扩展名选择语言解析器。"""

from __future__ import annotations

from pathlib import Path

from codegraph.parser.base import BaseParser
from codegraph.parser.treesitter_py import PythonParser
from codegraph.parser.treesitter_ts import TypeScriptParser

TS_SUFFIXES = {".ts", ".tsx"}
PY_SUFFIXES = {".py"}
SUPPORTED_SUFFIXES = TS_SUFFIXES | PY_SUFFIXES


def get_parser_for_path(path: Path) -> BaseParser | None:
    """根据扩展名返回对应解析器；不支持则返回 None。

    Args:
        path: 源文件路径。

    Returns:
        BaseParser 实例，或 None。
    """
    suffix = path.suffix.lower()
    if suffix in TS_SUFFIXES:
        return TypeScriptParser()
    if suffix in PY_SUFFIXES:
        return PythonParser()
    return None


def is_supported_source(path: Path) -> bool:
    """判断是否为受支持的源文件。"""
    return path.suffix.lower() in SUPPORTED_SUFFIXES


def language_of(path: Path) -> str:
    """返回文件对应的逻辑语言名。"""
    suffix = path.suffix.lower()
    if suffix in TS_SUFFIXES:
        return "typescript"
    if suffix in PY_SUFFIXES:
        return "python"
    return "unknown"
