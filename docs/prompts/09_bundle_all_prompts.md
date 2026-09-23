# Prompt 9 — Rebundle this pack (meta)

Copy everything below into the agent if you need to regenerate the pack.

```text
# Task: rebundle CodeGraph prompt pack

Working directory: D:\CodeGraph

Regenerate docs/prompts/ so each prompt is standalone and copy-paste ready.

Required files (keep names):
01_pre_submit_acceptance.md
02_dgraph_backend.md          # optional if quota is tight
03_architecture_pdf.md
04_demo_voiceover.md
05_release_notes.md
06_github_actions_ci.md
07_contributing_and_templates.md
08_competition_submission.md
09_bundle_all_prompts.md      # this file
README.md                     # index + execution order + manual steps

Rules:
- Each prompt is independent
- Chinese labels OK in the pack index; prompt bodies stay as provided
- Do not invent product facts
- Execution order: acceptance → PDF → demo → submission → CI → release notes → contributing/templates → Dgraph (optional)

Manual steps for the human (include in README):
1. Enable GitHub Pages: Settings → Pages → main → / (root) → Save
2. Upload PDF and demo video to the competition form

Output the files only.
```
