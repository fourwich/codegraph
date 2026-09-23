"""Select a language parser from the file extension."""

from __future__ import annotations

from pathlib import Path

from codegraph.parser.base import BaseParser
from codegraph.parser.treesitter_py import PythonParser
from codegraph.parser.treesitter_ts import TypeScriptParser

TS_SUFFIXES = {".ts", ".tsx"}
PY_SUFFIXES = {".py"}
SUPPORTED_SUFFIXES = TS_SUFFIXES | PY_SUFFIXES


def get_parser_for_path(path: Path) -> BaseParser | None:
    """Return the parser for a path, or None when unsupported.

    Args:
        path: Source file path.

    Returns:
        A BaseParser instance, or None.
    """
    suffix = path.suffix.lower()
    if suffix in TS_SUFFIXES:
        return TypeScriptParser()
    if suffix in PY_SUFFIXES:
        return PythonParser()
    return None


def is_supported_source(path: Path) -> bool:
    """Return True when the path is a supported source file."""
    return path.suffix.lower() in SUPPORTED_SUFFIXES


def language_of(path: Path) -> str:
    """Return the logical language name for a path."""
    suffix = path.suffix.lower()
    if suffix in TS_SUFFIXES:
        return "typescript"
    if suffix in PY_SUFFIXES:
        return "python"
    return "unknown"
