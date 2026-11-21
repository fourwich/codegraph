"""Translation belongs to prose only, and the environment decides the locale.

The distinction matters because `binding` values and JSON keys are read by scripts and
editors. Translating those would break the contract in `docs/json-contract.md`, so the
tests pin both halves: labels move, tokens do not.
"""

from __future__ import annotations

import os
from importlib import reload

import pytest

ENV_KEYS = ("CODEGRAPH_LANG", "LANG", "LC_ALL", "LC_MESSAGES")


@pytest.fixture(autouse=True)
def _clear_locale_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _reload(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import codegraph.i18n as i18n

    reload(i18n)
    return i18n


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, "en"),
        ({"CODEGRAPH_LANG": "en"}, "en"),
        ({"CODEGRAPH_LANG": "zh"}, "zh"),
        ({"CODEGRAPH_LANG": "zh-CN"}, "zh"),
        ({"CODEGRAPH_LANG": "zh_TW"}, "zh"),
        ({"LANG": "zh_CN.UTF-8"}, "zh"),
        ({"LANG": "en_US.UTF-8"}, "en"),
        ({"LC_ALL": "zh_CN.UTF-8"}, "zh"),
        ({"CODEGRAPH_LANG": "en", "LANG": "zh_CN.UTF-8"}, "en"),
    ],
)
def test_locale_detection(monkeypatch, env, expected) -> None:
    i18n = _reload(monkeypatch, **env)
    assert i18n.detect_locale() == expected


def test_explicit_setting_outranks_the_environment(monkeypatch) -> None:
    i18n = _reload(monkeypatch, CODEGRAPH_LANG="en", LANG="zh_CN.UTF-8")
    assert i18n.detect_locale() == "en"


@pytest.mark.parametrize(
    ("key", "english", "chinese"),
    [
        ("card.decision", "Decision", "决策"),
        ("card.reason", "Reason", "理由"),
        ("card.alternatives", "Alternatives", "备选方案"),
        ("status.active", "active", "生效中"),
        ("empty.no_decision", "No decision record found", "没有找到决策记录"),
        ("query.file", "file-level decision(s)", "条文件级决策"),
    ],
)
def test_both_locales_are_present(monkeypatch, key, english, chinese) -> None:
    i18n = _reload(monkeypatch, CODEGRAPH_LANG="en")
    assert i18n.t(key) == english
    i18n = _reload(monkeypatch, CODEGRAPH_LANG="zh")
    assert i18n.t(key) == chinese


def test_unknown_key_returns_the_key_itself(monkeypatch) -> None:
    """A missing translation must not raise: the answer is still correct."""
    i18n = _reload(monkeypatch, CODEGRAPH_LANG="zh")
    assert i18n.t("no.such.key") == "no.such.key"


def test_binding_values_are_never_translated(monkeypatch) -> None:
    """`line`/`file`/`commit`/`dir`/`none` are data, not prose."""
    i18n = _reload(monkeypatch, CODEGRAPH_LANG="zh")
    for value in ("line", "file", "commit", "dir", "none"):
        # The key space has query.* entries, but there is deliberately no
        # `binding.line`-style translation to look up.
        assert i18n.t(f"binding.{value}") == f"binding.{value}"


def test_help_text_picks_the_active_locale(monkeypatch) -> None:
    i18n = _reload(monkeypatch, CODEGRAPH_LANG="zh")
    assert i18n.help_text("Path scope", "路径范围") == "路径范围"
    i18n = _reload(monkeypatch, CODEGRAPH_LANG="en")
    assert i18n.help_text("Path scope", "路径范围") == "Path scope"


def test_cjk_console_selects_chinese(monkeypatch) -> None:
    """A GBK console reports cp936; that reader expects Chinese."""
    i18n = _reload(monkeypatch)
    monkeypatch.setattr(i18n.sys, "stdout", type("S", (), {"encoding": "cp936"})())
    assert i18n.detect_locale() == "zh"


def test_utf8_console_stays_english(monkeypatch) -> None:
    """A UTF-8 console says nothing about language, so it keeps English."""
    i18n = _reload(monkeypatch)
    monkeypatch.setattr(i18n.sys, "stdout", type("S", (), {"encoding": "utf-8"})())
    assert i18n.detect_locale() == "en"
