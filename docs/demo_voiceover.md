# CodeGraph — 60-second demo voiceover (English)

Use this as the read-aloud script for the screen recording.

---

[0-6s]
Screen: terminal typing
Command: none
Voiceover: "Why is this code written this way? Usually you cannot tell."

[6-12s]
Screen: run git blame
Command: `git blame src/codegraph/cli.py | head -5`
Voiceover: "git blame only shows who touched a line, not why it exists."

[12-24s]
Screen: run codegraph why
Command: `codegraph why src/codegraph/cli.py:24`
Voiceover: "CodeGraph returns a decision card: the choice, the reason, and the source."

[24-36s]
Screen: run codegraph graph
Command: `codegraph graph --at 2026-09-01 --scope src`
Then: `codegraph graph --at 2026-09-23 --scope src`
Voiceover: "Time travel shows the graph at a past date — nodes and live edges change."

[36-46s]
Screen: run codegraph serve
Command: `codegraph serve --port 8080 --no-open-browser`
Then: open http://127.0.0.1:8080/ and click a node
Voiceover: "The local web view makes the code and decision graph clickable."

[46-56s]
Screen: VSCode right-click a line
Command: none (editor)
Menu: CodeGraph: Show decision
Voiceover: "In VS Code, one click shows the same decision card for the current line."

[56-60s]
Screen: product site hero
Command: none
Voiceover: "CodeGraph — the decision memory layer for your codebase."

---

## Word count check
Target: 130-150 words at ~2.5 words/sec. Trim any line over 15 words before recording.

## Recording tips
- Terminal font large enough for 1080p
- Pause 0.5s after each command before showing output
- For `serve`, start it before recording so the UI is warm
- VS Code: install `vscode-extension/codegraph-vscode-0.1.0.vsix` first
- Keep cursor visible on the click that opens the decision panel
