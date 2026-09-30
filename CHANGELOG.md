# Changelog

## Changed

- Index walks real Git history and versions CodeNodes with valid_from / valid_to because time travel must reflect actual commits rather than a static snapshot.
- Decision extraction prefers commit messages, ADRs, and CHANGELOG over bundled samples because provenance should point at real sources.
- A second `index` merges into the stored graph instead of clearing it, so re-running the command no longer destroys Git history.
- Decision records carry a `decision` / `event` tier, and only records that state a reason or a rejected alternative are shown as decisions.

## Removed

- Hard dependency on SAMPLE_DECISIONS for the happy path because extracted decisions replace them when present.
- Conventional-commit subjects are no longer presented as decisions; they stay queryable as events with `--include-events`.
