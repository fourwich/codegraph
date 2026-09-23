# Prompt 4 — 60-second demo voiceover

Copy everything below into the agent.

```text
# Task: write a 60-second CodeGraph demo voiceover script

Record a 60s demo video of the CLI and product site. Need English read-aloud lines.

Shot list (strict timing):
0-8s: show the problem
8-15s: run git blame
15-30s: run codegraph why
30-42s: run codegraph graph
42-52s: run codegraph index
52-60s: switch to the product site page

Rules:
- Full English
- Conversational; each sentence <= 15 words
- Total 130-150 words (~55-60s at speaking pace)
- Tag every segment with timestamp and command
- Voiceover lines only (no stage directions in the script body)
- Do not use words like "revolutionary" or "game-changing"

Format:
[0-8s]
Screen: typing in terminal
Command: none
Voiceover: "..."

[8-15s]
Screen: run git blame
Command: git blame src/auth/session.ts | head -5
Voiceover: "..."

(continue in the same pattern)

Output the script only. No explanations.
```
