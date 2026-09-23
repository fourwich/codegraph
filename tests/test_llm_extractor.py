"""Tests for LLMExtractor with mocked HTTP (no live Ollama)."""

from __future__ import annotations

import httpx

from codegraph.decisions.llm_extractor import MAX_LLM_CONFIDENCE, LLMExtractor


def test_is_available_false_on_error(monkeypatch) -> None:
    """is_available returns False when Ollama is down."""

    def fake_get(url, timeout=None):  # type: ignore[no-untyped-def]
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", fake_get)
    assert LLMExtractor().is_available() is False


def test_is_available_true(monkeypatch) -> None:
    """is_available returns True on HTTP 200."""

    def fake_get(url, timeout=None):  # type: ignore[no-untyped-def]
        return httpx.Response(200, json={"models": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    assert LLMExtractor().is_available() is True


def test_extract_decision_parses_json() -> None:
    """extract_decision parses LLM JSON and caps confidence."""
    extractor = LLMExtractor()
    raw = (
        '{"content": "Use SQLite because it is embedded",'
        ' "reason": "zero ops", "alternatives": ["Dgraph"], "confidence": 0.95}'
    )
    decision = extractor._parse_response(
        raw,
        source_ref="commit abc",
        author="a@b.c",
        file_path="src/x.py",
    )
    assert decision is not None
    assert "SQLite" in decision.content
    assert decision.confidence <= MAX_LLM_CONFIDENCE
    assert decision.source_ref == "commit abc"


def test_extract_decision_null_content() -> None:
    """Null content yields None."""
    extractor = LLMExtractor()
    assert (
        extractor._parse_response('{"content": null}', source_ref="", author="", file_path="")
        is None
    )
