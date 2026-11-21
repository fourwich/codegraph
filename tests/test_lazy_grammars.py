"""A missing grammar must disable one language, not the package.

Importing `codegraph.parser` used to build every `Language` at module scope, so a missing
`tree-sitter-python` raised before any command parsed anything. A JavaScript repository
should not need the Python grammar to be installed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GRAMMARS = (
    "tree_sitter_python",
    "tree_sitter_typescript",
    "tree_sitter_java",
    "tree_sitter_go",
    "tree_sitter_rust",
    "tree_sitter_cpp",
)


def _run_blocked(blocks: tuple[str, ...], body: str) -> subprocess.CompletedProcess[str]:
    script = f"""
import sys
BLOCKED = {blocks!r}

class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError(f"No module named {{name!r}}")
        return None

sys.meta_path.insert(0, Blocker())
sys.path.insert(0, {str(ROOT / "src")!r})

{body}
"""
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
        timeout=180,
    )


def test_parser_package_imports_with_every_grammar_blocked() -> None:
    """The registry must load without any grammar present."""
    result = _run_blocked(
        GRAMMARS,
        "import codegraph.parser\nprint('ok')",
    )
    assert result.returncode == 0, result.stderr[-900:]
    assert "ok" in result.stdout


def test_why_still_works_with_every_grammar_blocked() -> None:
    """`why` reads the database; it does not parse source."""
    result = _run_blocked(
        GRAMMARS,
        "from codegraph.commands.why import why_command\nprint('ok')",
    )
    assert result.returncode == 0, result.stderr[-900:]
    assert "ok" in result.stdout


def test_a_missing_grammar_names_the_extra() -> None:
    """The failure has to say what to install, not just that something is absent."""
    result = _run_blocked(
        ("tree_sitter_python",),
        (
            "from codegraph.parser.treesitter_py import _grammar_language\n"
            "try:\n"
            "    _grammar_language()\n"
            "except ImportError as exc:\n"
            "    print('raised:', exc)\n"
        ),
    )
    assert result.returncode == 0, result.stderr[-900:]
    assert "raised:" in result.stdout
    assert "codegraphx[python]" in result.stdout


def test_grammar_still_loads_when_present() -> None:
    """Laziness must not change behaviour when the dependency is there."""
    result = _run_blocked(
        (),
        (
            "from codegraph.parser.treesitter_py import _grammar_language\n"
            "lang = _grammar_language()\n"
            "print('language:', type(lang).__name__)\n"
        ),
    )
    assert result.returncode == 0, result.stderr[-900:]
    assert "language: Language" in result.stdout
