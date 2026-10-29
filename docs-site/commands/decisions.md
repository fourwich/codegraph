# codegraph decisions

Decision evolution timeline, for one file or for everything.

```bash
codegraph decisions --timeline                        # every decision, oldest first
codegraph decisions --file src/codegraph/cli.py --timeline
codegraph decisions --timeline --include-events        # plain history too
```

`--file` is a filter, not a requirement: omitting it lists decisions across the
whole graph, which is the useful first look after `codegraph index`.
