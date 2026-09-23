# Time travel

Query the graph as of a date:

```sql
valid_from <= :date AND (valid_to IS NULL OR valid_to >= :date)
```

Edges count only when **both** endpoints are live. `codegraph graph --at` uses this rule.
