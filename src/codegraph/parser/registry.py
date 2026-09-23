"""Select a language parser from the file extension."""

from __future__ import annotations

from pathlib import Path

from codegraph.parser.base import BaseParser
from codegraph.parser.treesitter_cpp import CppParser
from codegraph.parser.treesitter_go import GoParser
from codegraph.parser.treesitter_java import JavaParser
from codegraph.parser.treesitter_py import PythonParser
from codegraph.parser.treesitter_rust import RustParser
from codegraph.parser.treesitter_ts import TypeScriptParser

TS_SUFFIXES = {".ts", ".tsx"}
PY_SUFFIXES = {".py"}
JAVA_SUFFIXES = {".java"}
GO_SUFFIXES = {".go"}
RUST_SUFFIXES = {".rs"}
CPP_SUFFIXES = {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".h"}
SUPPORTED_SUFFIXES = (
    TS_SUFFIXES | PY_SUFFIXES | JAVA_SUFFIXES | GO_SUFFIXES | RUST_SUFFIXES | CPP_SUFFIXES
)


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
    if suffix in JAVA_SUFFIXES:
        return JavaParser()
    if suffix in GO_SUFFIXES:
        return GoParser()
    if suffix in RUST_SUFFIXES:
        return RustParser()
    if suffix in CPP_SUFFIXES:
        return CppParser()
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
    if suffix in JAVA_SUFFIXES:
        return "java"
    if suffix in GO_SUFFIXES:
        return "go"
    if suffix in RUST_SUFFIXES:
        return "rust"
    if suffix in CPP_SUFFIXES:
        return "cpp"
    return "unknown"
