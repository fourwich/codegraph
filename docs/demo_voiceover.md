# CodeGraph — 60-second demo voiceover (English)

Use this as the read-aloud script for the screen recording.

---

[0-8s]
Screen: terminal typing
Command: none
Voiceover: "Why is this code written this way? Usually you cannot tell."

[8-15s]
Screen: run git blame
Command: `git blame src/auth/session.ts | head -5`
Voiceover: "git blame only shows who touched a line, not why it exists."

[15-30s]
Screen: run codegraph why
Command: `codegraph why src/auth/session.ts:42`
Voiceover: "CodeGraph returns a decision card: the choice, the reason, and rejected alternatives."

[30-42s]
Screen: run codegraph graph
Command: `codegraph graph --at 2024-11-02 --scope src`
Voiceover: "You can also query the code graph at a past date and see what changed."

[42-52s]
Screen: run codegraph index
Command: `codegraph index .`
Voiceover: "Indexing parses TypeScript and Python with tree-sitter into a local graph."

[52-60s]
Screen: switch to product site (index.html hero + graph)
Command: none
Voiceover: "CodeGraph — the decision memory layer for your codebase."

---

## Word count check
Target: 130-150 words at ~2.5 words/sec. Trim any line over 15 words before recording.

## Recording tips
- Terminal font size large enough for 1080p video
- Pause 0.5s after each command before showing output
- Keep mouse cursor out of frame or use a clean terminal theme
