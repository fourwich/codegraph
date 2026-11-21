"""Machine translation for decision text, with the original always shown.

Decision content and reasons are quoted from the project's own records — an ADR, a
changelog entry, a commit body. Translating them changes what the project said, so the
translation is never presented as the record:

* the original stays exactly as written, and
* a translated line is prefixed and marked as machine output.

That keeps the one property the tool is built on: a reader can always tell whether they
are looking at the project's words or at this tool's rendering of them.

The backend is local Ollama, the same dependency `codegraph index --use-llm` already
uses. When it is unreachable, translation is skipped and the card shows the original —
never a guess, never a partial rendering.
"""

from __future__ import annotations

from typing import Final

try:
    import httpx
except ImportError:  # pragma: no cover - the [llm] extra is absent
    httpx = None  # type: ignore[assignment]

#: Prefix on every machine-translated line, so it cannot be mistaken for the record.
MACHINE_MARK: Final = "机器译"

SYSTEM_PROMPT: Final = (
    "You translate software design records from English to Simplified Chinese. "
    "Translate only what is written; do not summarize, expand, or explain. "
    "Keep code identifiers, file paths, commit hashes, and command names unchanged. "
    "Return the translation and nothing else."
)


class Translator:
    """Translate short English passages to Chinese through a local Ollama server."""

    def __init__(
        self,
        model: str = "qwen2.5:3b",
        base_url: str = "http://localhost:11434",
        timeout: float = 20.0,
    ) -> None:
        """Store the connection settings.

        Args:
            model: Ollama model to use. A small instruct model is enough for short
                passages and keeps the call fast.
            base_url: Ollama HTTP root.
            timeout: Per-request budget in seconds.
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._available: bool | None = None

    def is_available(self) -> bool:
        """True when the server answers; cached after the first check."""
        if self._available is not None:
            return self._available
        if httpx is None:
            # Without the extra there is no HTTP client, so nothing to talk to.
            self._available = False
            return False
        try:
            res = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
            self._available = res.status_code == 200
        except Exception:  # noqa: BLE001 — a reachability probe: any failure means "down"
            self._available = False
        return self._available

    def translate(self, text: str) -> str | None:
        """Return a Chinese rendering of `text`, or None when that is not possible.

        Args:
            text: The original passage.

        Returns:
            The translation, or None when the server is unavailable, refuses, or
            returns something that is clearly not a translation.
        """
        passage = (text or "").strip()
        if not passage or not self.is_available():
            return None

        try:
            res = httpx.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "system": SYSTEM_PROMPT,
                    "prompt": passage,
                    "stream": False,
                    "options": {"temperature": 0},
                },
                timeout=self.timeout,
            )
            if res.status_code != 200:
                return None
            body = res.json()
        except Exception:  # noqa: BLE001 — a missing translation is not an error path
            return None

        translated = (body.get("response") or "").strip()
        if not translated:
            return None
        return translated


__all__ = ["MACHINE_MARK", "SYSTEM_PROMPT", "Translator"]
