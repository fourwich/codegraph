# codegraph why

Show the decision provenance card for a source line.

```bash
codegraph why <file>:<line> [--backend sqlite|dgraph] [--json]
```

## Example

```bash
codegraph why src/auth/session.ts:42
codegraph why src/codegraph/cli.py:24 --json
```

## Output fields

Location, Decision, Reason, Alternatives, Source, Status, Constraints, Confidence.
