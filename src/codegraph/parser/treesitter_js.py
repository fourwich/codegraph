"""JavaScript parser reusing the TypeScript grammar."""

from __future__ import annotations

from codegraph.parser.treesitter_ts import TypeScriptParser


class JavaScriptParser(TypeScriptParser):
    """Parse .js / .mjs / .cjs with the TypeScript (non-JSX) grammar.

    JavaScript is a subset of TypeScript syntax, so tree-sitter-typescript
    can parse it without a separate grammar package.
    """

    language = "javascript"
