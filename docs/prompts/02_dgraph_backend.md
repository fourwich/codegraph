# Prompt 2 — Dgraph backend (optional)

Skip if quota is tight. Copy everything below into the agent.

```text
# Task: add a Dgraph backend to CodeGraph (keep SQLite as fallback)

Working directory: D:\CodeGraph

Context: tree-sitter parsing and SQLite storage work. CLI has index / why / graph / decisions. 16 tests passing.

Stack to add: Dgraph v23+ (docker compose), pydgraph. Keep tree-sitter, Typer, Rich, pydantic, pytest.

Implement:
1. docker-compose.yml for dgraph zero + alpha (v23.1.0), ports 5080/6080/8080/9080
2. .env.example: DGRAPH_ALPHA=localhost:9080, DGRAPH_BACKEND=sqlite
3. src/codegraph/graph/__init__.py exporting DgraphClient
4. src/codegraph/graph/schema.py — DQL schema for CodeNode + Decision with indexes and @reverse edges; get_schema(); get_drop_all_query()
5. src/codegraph/graph/client.py — DgraphClient with:
   __init__(alpha from DGRAPH_ALPHA or localhost:9080)
   ping, init_schema, drop_all
   upsert_node(node), upsert_edge(edge), upsert_decision(decision)
   query_node_at(file_path, line), query_decisions_for(file_path, line)
   query_graph_at(at_date, scope) -> {nodes, edge_count, decision_count}
   close()
   Raise DgraphConnectionError on connection failure. Parameterized queries only ($vars), no string concatenation into DQL.
6. src/codegraph/graph/mutations.py — build_node_json, build_edge_json, build_decision_json
7. commands/index.py — add --backend sqlite|dgraph (default sqlite). On dgraph: ping (exit 3 on fail), init_schema, upsert nodes/edges/SAMPLE_DECISIONS, print counts + http://localhost:8080/?latest
8. commands/why.py — add --backend; same output format for both backends
9. commands/graph.py — add --backend; time-travel query on dgraph
10. tests/test_graph_mutations.py — structure asserts only (no live Dgraph)
11. tests/test_cli.py — connection failure exit code 3; why --backend flag parse
12. README "Optional: Dgraph backend" section

Rules: English docstrings, type hints, functions <= 50 lines, no bare except, do not change SQLite behavior.

Verify:
pip install -e ".[dev]"
docker compose up -d
codegraph index . --backend dgraph
codegraph why src/auth/session.ts:42 --backend dgraph
codegraph graph --at 2024-11-02 --backend dgraph
pytest -q
codegraph index . --backend sqlite   # must still work

Paste full file contents in order and verification output. No omissions, no pseudocode.
```
