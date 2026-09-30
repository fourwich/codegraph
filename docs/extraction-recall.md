# Decision extraction: recall and precision

Rules stay non-LLM. The extractor produces two kinds of record:

| Tier | Meaning | Shown by default |
|---|---|---|
| `decision` | States a reason (`because …`, `to fix …`) or a rejected alternative (`instead of X`) | yes |
| `event` | Plain history: a commit subject, a release-note line | no (`--include-events`) |

Dependency records carry `category = dependency` and are hidden too, unless they
state a reason — in which case they are dependency **decisions**.

## What changed in the precision pass

1. A commit subject is no longer a decision by default. It becomes one only when
   it states a reason or a rejected alternative. `feat: use the new logo` is an
   event; `refactor: use node:buffer instead of safe-buffer` is a decision.
2. Reasons are required, not implied. A fragment with a keyword but no
   `because / so that / to fix / …` clause is an event.
3. Keywords were narrowed. `since`, `reason`, `must be`, `should not`,
   `to support`, `to keep`, `to match`, `to improve`, bare `avoid`, bare
   `replaced` matched ordinary English and were removed.
4. A dependency bump that says why is upgraded:
   `deps: bump body-parser to ^2.3.0 to fix CVE-2026-12590` → dependency
   decision at 0.65; `bump morgan from 1.12.0 to 1.12.1` → dependency event.
5. `instead of X` / `rather than X` populate `alternatives` instead of being
   folded into the decision text.
6. The whole commit message is no longer scanned *and* its subject *and* its
   body: that triple emission double counted the same sentence. Records are now
   de-duplicated by `(source_ref, content)` keeping the richer of the two.
7. uids use a blake2b fingerprint, so they are reproducible across processes.

## Measured (reproduce with `scripts/eval_decision_precision.py`)

| Project | Depth | Records | Decisions | Decision share | With reason | With alternative |
|---|---|---|---|---|---|---|
| expressjs/express | 200 | 204 | **5** | 2.5% | 2 | 3 |
| CodeGraph self | 50 | 56 | **9** | 16.1% | 8 | 6 |

The Express row is the stable reference. The self row was measured on this
repository at commit `54f034b`, and drifts by roughly one record per commit made
to this repository — re-run the script to get the current figure.

The old headline was "174 decisions on Express". Under the tier model the same
run yields 204 records of which **5** are decisions: precision went up, and the
number went down, which is the point.

The self repo's 9 decisions are 5 ADRs plus 4 CHANGELOG entries — sources that
are handwritten rather than scraped from commit subjects.

## Recall note

Earlier work raised Express recall from 109 to 174 records (+60%) by treating
every conventional-commit subject as a decision. That traded precision for a
bigger number and has been reverted: those 199 extra records are now events,
still stored, still queryable with `--include-events`, but never presented as
answers.

## Sample decisions now captured on Express

- `use node:buffer` — alternative: `safe-buffer (#6071)`
- `values at parser initialization` — alternative: `failing open`
- `deps: bump body-parser to ^2.3.0` — reason: `to fix CVE-2026-12590 (#7390)`
- `Configure dependabot … to reduce noise` — reason: `to avoid errors from version mismatches`
- `Update multiple links to use `https`` — alternative: `` `http` (#6338)`
