# Decision extraction recall (before → after)

Rules stay non-LLM. Changes:

1. More rationale keywords (chose / switched to / migrated to / due to / to fix / ...)
2. `build(...)` conventional commits emit weak subject decisions (0.55)
3. Commit body bullets/paragraphs with keywords → confidence 0.7
4. `Merge pull request` messages counted as PR-sourced decisions

## Comparison

| Project | Before | After | Change |
|---|---|---|---|
| CodeGraph self (depth 100) | 50 | 50 | 0% (already covered by ADR + subjects) |
| Express (depth 200) | **109** | **174** | **+60%** |
| got (depth 200, earlier) | 14 | not re-run | — |

## Sample Express subjects now captured

- `build(deps): bump qs minimum to 6.16.0`
- `build(deps): bump body-parser to ^2.3.0 to fix CVE-...`

## Notes

Many Express commits are dependency bumps — they are weak decisions, not architectural rationales. Body bullets and explicit “because / to fix / switched to” phrasing produce higher-confidence hits.


## Quality split (Express, after category field)

| Category | Count | Share |
|---|---|---|
| design | 120 | 69% |
| dependency (bump / build(deps)) | 54 | 31% |
| **Total** | **174** | |

`why` hides dependency rows by default (`--include-dependency` to show them).
