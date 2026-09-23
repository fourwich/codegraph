# Prompt 1 — Pre-submit acceptance (CodeGraph)

Copy everything below into the agent.

```text
# Task: final pre-submit acceptance for CodeGraph

Working directory: D:\CodeGraph

Run and report with ✅ / ⚠️ / ❌ per section. Do not summarize as "all good".

1. Repo structure
   List root files. Confirm present:
   index.html, styles.css, main.js, README.md, LICENSE, pyproject.toml,
   .gitignore, docker-compose.yml (if added), src/codegraph/, tests/, docs/
   (demo_script.md / translate_prompt.txt). Mark missing or extra files.

2. README check
   - Links clickable (GitHub repo, live demo)
   - No YOUR_USERNAME placeholders
   - Status section accurate
   - No broken image references

3. Code quality
   - pytest -q
   - ruff check src/ tests/ (if installed)
   - python -m compileall src/codegraph
   Report pass/fail.

4. Run every CLI command and paste output
   codegraph --version
   codegraph --help
   codegraph index .
   codegraph why src/auth/session.ts:42
   codegraph why badformat
   codegraph graph --at 2024-11-02 --scope src
   codegraph decisions --file src/auth/session.ts --timeline
   Confirm English-only output and no tracebacks.

5. Chinese leftovers
   git grep -n -P "[\x{4e00}-\x{9fa5}]" -- "*.py" "*.js" "*.html" "*.css" "*.toml"
   Expect no hits in src/ tests/ index.html main.js styles.css pyproject.toml.

6. Git state
   - git status clean (or list dirty files)
   - git log --oneline -10
   - .env not tracked
   - .codegraph/ not tracked

7. Product site
   Open index.html. Check terminal typing, Replay button, hero graph nodes, console errors.

8. Submission checklist
   For each item mark ready / missing / needs-fix:
   - GitHub repo link
   - Live demo link (GitHub Pages)
   - Elevator pitch
   - Project Story
   - Built with tags
   - Try it out links
   - Demo video link (optional)
   - Additional info PDF (optional)

Output format: sections 1-8 with clear marks. Give fix commands when something fails.
Do not omit details.
```
