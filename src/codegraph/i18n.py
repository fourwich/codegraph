"""Bilingual strings for the text a person reads.

Two kinds of string live in this package and they are treated differently:

* **Interface** — command names, flag names, JSON keys, and the `binding` values
  (`line`, `file`, `commit`, `dir`, `none`). These stay English in every locale: a
  script or editor reads them, and translating them would break the contract in
  `docs/json-contract.md`.
* **Prose** — card labels, table headers, status words, error messages, and help text.
  These are translated.

The locale comes from `CODEGRAPH_LANG`, then `LC_ALL`/`LANG`, then the console's own
encoding. Chinese is selected only when the caller asks for it or the environment is
plainly Chinese; an English terminal keeps English output so a log stays readable to
whoever else opens it.

    CODEGRAPH_LANG=zh codegraph why src/app.py:42
    codegraph why src/app.py:42           # follows LANG / console encoding
"""

from __future__ import annotations

import os
import sys
from typing import Final

#: Locales this package ships text for. Anything else falls back to English.
SUPPORTED: Final = ("en", "zh")

#: Keyed by a stable identifier, not by the English text, so a reworded English string
#: cannot silently orphan its translation.
_MESSAGES: Final[dict[str, dict[str, str]]] = {
    "card.decision": {"en": "Decision", "zh": "决策"},
    "card.reason": {"en": "Reason", "zh": "理由"},
    "card.alternatives": {"en": "Alternatives", "zh": "备选方案"},
    "card.source": {"en": "Source", "zh": "来源"},
    "card.status": {"en": "Status", "zh": "状态"},
    "card.constraints": {"en": "Constraints", "zh": "约束"},
    "card.location": {"en": "Location", "zh": "位置"},
    "card.confidence": {"en": "Confidence", "zh": "置信度"},
    "card.author": {"en": "Author", "zh": "作者"},
    "card.date": {"en": "Date", "zh": "日期"},
    "card.matched_node": {"en": "Matched CodeNode", "zh": "匹配到的代码节点"},
    "status.active": {"en": "active", "zh": "生效中"},
    "status.superseded": {"en": "superseded", "zh": "已被取代"},
    "status.rejected": {"en": "rejected", "zh": "已否决"},
    "empty.no_decision": {"en": "No decision record found", "zh": "没有找到决策记录"},
    "empty.no_node": {
        "en": "No active code node covers this line",
        "zh": "没有代码节点覆盖这一行",
    },
    "empty.hidden_events": {
        "en": "record(s) hidden — add --include-events to see plain history",
        "zh": "条记录已隐藏 — 加 --include-events 查看纯历史",
    },
    "query.label": {"en": "Query", "zh": "查询"},
    "query.matched": {"en": "matched", "zh": "匹配到"},
    "query.line": {"en": "line-level decision(s)", "zh": "条行级决策"},
    "query.file": {"en": "file-level decision(s)", "zh": "条文件级决策"},
    "query.dir": {"en": "directory-level decision(s)", "zh": "条目录级决策"},
    "query.commit": {"en": "commit-level decision(s)", "zh": "条提交级决策"},
    "query.none": {"en": "decision(s)", "zh": "条决策"},
}

_ENGLISH_CONSOLE_HINTS: Final = ("utf-8", "utf8", "cp65001")
_CHINESE_LOCALE_PREFIXES: Final = ("zh", "cmn", "yue")


def _normalize(code: str) -> str:
    """Reduce a locale tag to `en` or `zh`, defaulting to `en`."""
    if not code:
        return "en"
    lowered = code.strip().lower().replace("_", "-")
    for prefix in _CHINESE_LOCALE_PREFIXES:
        if lowered == prefix or lowered.startswith(prefix + "-"):
            return "zh"
    return "en"


def detect_locale() -> str:
    """Choose the output locale from the environment.

    `CODEGRAPH_LANG` wins because it is explicit and per-invocation. Then the standard
    locale variables. Last, the console encoding: a Chinese Windows console reports
    `cp936`, which is a reliable signal that the reader expects Chinese, while a
    UTF-8 console says nothing about language and therefore stays English.
    """
    explicit = os.environ.get("CODEGRAPH_LANG", "").strip()
    if explicit:
        return _normalize(explicit)

    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(name, "").strip()
        if value:
            return _normalize(value)

    encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    if encoding and encoding not in _ENGLISH_CONSOLE_HINTS:
        if encoding.startswith(("cp936", "gbk", "gb2312", "gb18030", "big5")):
            return "zh"
    return "en"


#: The locale for this process, resolved once at import.
LOCALE: str = detect_locale()


def t(key: str, locale: str | None = None) -> str:
    """Return the text for `key` in `locale`, falling back to English then to the key.

    Falling back to the key rather than raising keeps a missing translation from
    breaking a command whose answer is still correct.
    """
    table = _MESSAGES.get(key)
    if table is None:
        return key
    return table.get(locale or LOCALE) or table["en"]


def is_chinese(locale: str | None = None) -> bool:
    """True when the active locale is Chinese."""
    return (locale or LOCALE) == "zh"


def help_text(english: str, chinese: str) -> str:
    """Pick a help string for the active locale.

    Help text is written inline at the option that uses it, so there is no key to look
    up; passing both languages keeps the pairing visible where it matters.
    """
    return chinese if is_chinese() else english


__all__ = ["LOCALE", "SUPPORTED", "detect_locale", "help_text", "is_chinese", "t"]
