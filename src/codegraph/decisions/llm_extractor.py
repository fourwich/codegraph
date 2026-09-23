"""Optional local LLM decision extraction via Ollama HTTP API."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx

from codegraph.models import Decision, DecisionSource, DecisionStatus

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are analyzing a Git commit to extract a design decision.
Commit message:
{commit_message}

Diff summary:
{diff_summary}

Extract one decision if present. Output JSON with fields:
- content: one sentence
- reason: why
- alternatives: list (may be empty)
- confidence: 0.0-1.0
If no decision is present, output {{"content": null}}.
"""

MAX_LLM_CONFIDENCE = 0.7


class LLMExtractor:
    """Rule-engine fallback that talks to a local Ollama server."""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        timeout: float = 8.0,
    ) -> None:
        """Store model settings.

        Args:
            model: Ollama model name.
            base_url: Ollama HTTP root.
            timeout: Request timeout seconds.
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        """Return True when Ollama answers /api/tags."""
        try:
            res = httpx.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            return res.status_code == 200
        except httpx.HTTPError as exc:
            logger.debug("Ollama unavailable: %s", exc)
            return False

    def extract_decision(
        self,
        commit_message: str,
        diff_summary: str,
        *,
        source_ref: str = "",
        author: str = "",
        file_path: str = "",
    ) -> Decision | None:
        """Ask the LLM for one structured decision.

        Args:
            commit_message: Full commit message.
            diff_summary: Short diff summary text.
            source_ref: Provenance string (usually a commit sha).
            author: Commit author.
            file_path: Related file path.

        Returns:
            A Decision with confidence capped at 0.7, or None.
        """
        prompt = PROMPT_TEMPLATE.format(
            commit_message=commit_message[:2000],
            diff_summary=diff_summary[:1000] or "(none)",
        )
        raw = self._generate(prompt)
        if not raw:
            return None
        return self._parse_response(
            raw,
            source_ref=source_ref,
            author=author,
            file_path=file_path,
        )

    def _generate(self, prompt: str) -> str | None:
        """Call Ollama /api/generate and return response text."""
        try:
            res = httpx.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=self.timeout,
            )
            if res.status_code != 200:
                logger.warning("Ollama HTTP %s", res.status_code)
                return None
            data = res.json()
            return str(data.get("response") or "")
        except httpx.HTTPError as exc:
            logger.warning("Ollama request failed: %s", exc)
            return None
        except ValueError as exc:
            logger.warning("Ollama JSON failed: %s", exc)
            return None

    def _parse_response(
        self,
        raw: str,
        *,
        source_ref: str,
        author: str,
        file_path: str,
    ) -> Decision | None:
        """Parse LLM JSON into a Decision."""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON output")
            return None
        content = payload.get("content")
        if not content:
            return None
        try:
            confidence = float(payload.get("confidence") or 0.5)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = min(max(confidence, 0.0), MAX_LLM_CONFIDENCE)
        alternatives = payload.get("alternatives") or []
        if isinstance(alternatives, str):
            alternatives = [alternatives]
        return Decision(
            uid=f"llm::{hash(str(content)) & 0xFFFFFFFF:08x}",
            content=str(content)[:220],
            reason=str(payload.get("reason") or content)[:500],
            alternatives=[str(a) for a in alternatives][:5],
            status=DecisionStatus.ACCEPTED,
            source=DecisionSource.COMMIT,
            source_ref=source_ref or "llm",
            timestamp=datetime.now(timezone.utc),
            author=author,
            file_path=file_path,
            line=None,
            constraints=[],
            confidence=confidence,
        )
