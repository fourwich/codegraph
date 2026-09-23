# Ollama

Optional local LLM extraction.

```bash
codegraph index . --use-llm --llm-model llama3.2
```

Gracefully degrades to rules-only when Ollama is offline. LLM confidence is capped at 0.7.
