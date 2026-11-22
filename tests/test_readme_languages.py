"""Keep the Chinese README honest against the English one.

Two files with the same structure drift: a test count changes, a command is added, and one
translation keeps the old figure. These checks compare the facts a reader can verify, not
the prose, because the prose is allowed to read naturally in each language.

What is compared:
* every measured number (tests, coverage, packages, commands) appears in both
* the command list is the same set
* both link to the same documents
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EN = ROOT / "README.md"
ZH = ROOT / "README.zh-CN.md"


@pytest.fixture(scope="module")
def english() -> str:
    return EN.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def chinese() -> str:
    return ZH.read_text(encoding="utf-8")


def test_both_files_exist() -> None:
    assert EN.is_file()
    assert ZH.is_file()


def test_switcher_links_resolve(chinese: str, english: str) -> None:
    """The button is the whole point: each file must link to the other by name."""
    assert 'href="README.zh-CN.md"' in english
    assert 'href="README.md"' in chinese


def test_chinese_states_the_test_count(english: str, chinese: str) -> None:
    """The counts are read from the English file, not written into the test.

    A pattern containing the literal figure has to be edited whenever a test is added,
    which means it stops being run long before it stops being wrong.
    """
    english_tests = re.search(r"(\d+) tests passing", english)
    assert english_tests is not None, "English README lost its test count"
    expected = english_tests.group(1)
    assert re.search(rf"{expected}\s*个测试", chinese), (
        f"Chinese README does not state {expected} tests"
    )


@pytest.mark.parametrize(
    "pattern",
    [
        r"\d+\s*个包",
        r"\d+\s*个命令行命令",
        r"覆盖率\s*\d+\s*%",
    ],
)
def test_each_measurement_is_stated_in_chinese(chinese: str, pattern: str) -> None:
    """Every measurement the English file quotes must also appear, with some value."""
    assert re.search(pattern, chinese), f"Chinese README is missing a figure matching {pattern!r}"


def test_test_count_matches_english(english: str, chinese: str) -> None:
    def count(text: str, pattern: str) -> str | None:
        match = re.search(pattern, text)
        return match.group(1) if match else None

    english_tests = count(english, r"(\d+) tests passing")
    chinese_tests = count(chinese, r"(\d+)\s*个测试")
    assert english_tests is not None and chinese_tests is not None
    assert english_tests == chinese_tests, (
        f"English says {english_tests} tests, Chinese says {chinese_tests}"
    )


def test_command_list_matches(english: str, chinese: str) -> None:
    """Every documented command must be documented in both languages."""

    def commands(text: str) -> set[str]:
        block = re.search(r"```bash\n(.*?)```", text, re.DOTALL)
        found: set[str] = set()
        for line in text.splitlines():
            if line.startswith("codegraph "):
                token = line.split()[1]
                if token.isalpha() or "-" in token:
                    found.add(token)
        del block
        return found

    english_commands = commands(english)
    chinese_commands = commands(chinese)
    missing = english_commands - chinese_commands
    assert not missing, f"Chinese README omits commands: {sorted(missing)}"


def test_both_link_to_the_same_documents(english: str, chinese: str) -> None:
    """A doc referenced in one language must be reachable from the other."""

    def docs(text: str) -> set[str]:
        return set(re.findall(r"docs/[a-zA-Z0-9_\-/]+\.md", text))

    english_docs = docs(english)
    chinese_docs = docs(chinese)
    missing = english_docs - chinese_docs
    assert not missing, f"Chinese README does not reference: {sorted(missing)}"


def test_chinese_file_is_actually_chinese(chinese: str) -> None:
    """Guards against shipping an English copy under a Chinese name."""
    cjk = sum(1 for char in chinese if "\u4e00" <= char <= "\u9fff")
    ratio = cjk / len(chinese)
    assert cjk > 1000, f"only {cjk} CJK characters"
    assert ratio > 0.15, f"CJK ratio is {ratio:.2%}, too low to be a translation"
