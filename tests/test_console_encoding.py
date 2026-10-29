"""`why` must not crash on consoles that cannot encode the card's symbols.

Chinese Windows consoles default to GBK; the status label used to contain
U+2705, which raised UnicodeEncodeError mid-card.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from codegraph.models import CodeNode, Decision, DecisionSource, DecisionStatus
from codegraph.storage import (
    connect,
    db_path_for_root,
    init_schema,
    insert_decision_links,
    insert_decisions,
    insert_nodes,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _seed_graph(root: Path) -> None:
    conn = connect(db_path_for_root(root))
    try:
        init_schema(conn)
        code = CodeNode(
            uid="n1",
            kind="function",
            name="f",
            file_path="src/x.py",
            line_start=1,
            line_end=5,
            language="python",
        )
        decision = Decision(
            uid="d1",
            content="Use a cached slice because of allocation cost",
            reason="because of allocation cost",
            status=DecisionStatus.ACCEPTED,
            source=DecisionSource.COMMIT,
            source_ref="commit abc",
            timestamp=NOW,
            file_path="src/x.py",
            line=3,
        )
        insert_nodes(conn, [code])
        insert_decisions(conn, [decision])
        insert_decision_links(conn, [("d1", "n1", "src/x.py", 3)])
    finally:
        conn.close()


def test_why_handles_non_utf8_stdout(tmp_path: Path) -> None:
    """A GBK console must render the card instead of raising.

    The stream is reconfigured to UTF-8, so the bytes come back as UTF-8 even
    though the console was asked for GBK. That is the fix: the card used to die
    on `UnicodeEncodeError` when it hit an emoji, and once that was swallowed the
    separators arrived as mojibake (`·` read as `路`).
    """
    _seed_graph(tmp_path)
    env = {
        **os.environ,
        "PYTHONIOENCODING": "gbk",
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }
    result = subprocess.run(
        [sys.executable, "-m", "codegraph.cli", "why", "src/x.py:3"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
    )
    text = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")

    assert "UnicodeEncodeError" not in stderr, stderr
    assert result.returncode == 0, stderr
    assert "\ufffd" not in text, "output was not encodable as UTF-8"
    assert "active" in text
    assert "cached slice" in text


def test_index_output_on_a_gbk_console_has_no_mojibake(tmp_path: Path) -> None:
    """`·` must not arrive as `路` when the console is GBK."""
    _seed_graph(tmp_path)
    env = {
        **os.environ,
        "PYTHONIOENCODING": "gbk",
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }
    result = subprocess.run(
        [sys.executable, "-m", "codegraph.cli", "index", ".", "--depth", "3", "--full"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
    )
    text = result.stdout.decode("utf-8", errors="replace") + result.stderr.decode(
        "utf-8", errors="replace"
    )

    assert result.returncode == 0, text
    assert "\ufffd" not in text
    assert "路" not in text, "middle dot decoded as a Chinese character"
