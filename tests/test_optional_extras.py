"""A base install must answer `why` without the optional extras.

`fastapi`/`uvicorn` moved to `[serve]` and `httpx` to `[llm]`. Those imports live inside
the modules that need them, so a missing extra degrades a feature instead of breaking the
command that most users run.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run_blocked(blocks: tuple[str, ...], body: str) -> subprocess.CompletedProcess[str]:
    """Run `body` with the named top-level packages unimportable."""
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
        timeout=120,
    )


def test_why_imports_without_httpx_or_the_web_stack() -> None:
    """The base install must load every module `why` needs."""
    result = _run_blocked(
        ("httpx", "fastapi", "uvicorn", "starlette"),
        "from codegraph.commands.why import why_command\nprint('ok')",
    )
    assert result.returncode == 0, result.stderr[-800:]
    assert "ok" in result.stdout


def test_translator_reports_unavailable_without_httpx() -> None:
    """A missing extra makes translation unavailable, not fatal."""
    result = _run_blocked(
        ("httpx",),
        (
            "from codegraph.translate import Translator\n"
            "t = Translator()\n"
            "print('available:', t.is_available())\n"
            "print('translate:', t.translate('hello'))\n"
        ),
    )
    assert result.returncode == 0, result.stderr[-800:]
    assert "available: False" in result.stdout
    assert "translate: None" in result.stdout


def test_serve_names_the_extra_when_the_web_stack_is_absent() -> None:
    """The error must say which install command fixes it, with the brackets intact."""
    result = _run_blocked(
        ("fastapi", "uvicorn", "starlette"),
        (
            "from typer.testing import CliRunner\n"
            "from codegraph.cli import app\n"
            "r = CliRunner().invoke(app, ['serve', '--no-open-browser'])\n"
            "print('exit:', r.exit_code)\n"
            "print('out:', r.output.strip())\n"
        ),
    )
    assert result.returncode == 0, result.stderr[-800:]
    assert "exit: 1" in result.stdout
    # Rich parses `[serve]` as markup; the hint escapes it so the extra name survives.
    assert "codegraphx[serve]" in result.stdout


def test_core_dependencies_exclude_the_extras() -> None:
    """The split is a packaging promise, so it is asserted against the manifest."""
    import tomllib

    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    core = " ".join(config["project"]["dependencies"])
    assert "fastapi" not in core
    assert "uvicorn" not in core
    assert "httpx" not in core

    extras = config["project"]["optional-dependencies"]
    assert any("fastapi" in dep for dep in extras["serve"])
    assert any("httpx" in dep for dep in extras["llm"])
