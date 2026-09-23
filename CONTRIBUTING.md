# Contributing to CodeGraph

Thanks for stopping by. I am a 15-year-old self-taught developer maintaining this project. Clear, kind contributions help a lot.

## Ways to contribute

- Report bugs with steps I can reproduce
- Suggest features with the problem first, not only the solution
- Send pull requests for code, tests, or docs
- Improve examples and wording on the product site

## Development setup

```bash
git clone https://github.com/fourwich/codegraph.git
cd codegraph

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -e ".[dev]"
pytest -q
```

Optional lint (if you install ruff):

```bash
ruff check src/ tests/
```

## Code style

- Python 3.10+, type hints on functions, English docstrings
- Keep user-facing CLI strings in English
- Prefer `pathlib` over `os.path`
- Keep functions small and focused
- Run tests before you open a PR

Commit messages:

```text
type(scope): short summary
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`  
Scopes: `parser`, `cli`, `graph`, `storage`, `docs`, `ci`

Example: `fix(parser): handle empty TypeScript files`

## Pull request process

1. Fork and create a branch: `feature/...`, `fix/...`, or `docs/...`
2. Keep one logical change per PR
3. Include a short description: what changed, why, how you tested
4. Make sure `pytest -q` passes
5. Be ready to iterate on review comments

## Code of conduct (short version)

Be respectful. Assume good intent. No harassment, hate, or personal attacks. Disagree about code, not people. Maintainers may close issues or PRs that break this.

## Questions

Open a GitHub issue with the `question` context in the title, or start a discussion on the repo. I read everything, even if replies take a bit.

— the maintainer
