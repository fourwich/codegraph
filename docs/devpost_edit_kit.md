# Devpost 修改清单（可直接粘贴）

登录后在 https://devpost.com/software/codegraph-6u4qx0 操作。三件事，约 3 分钟。

---

## 1. 删除两个标签

在项目编辑页的 **Technology tags**（技术标签）里，找到并删除：

- `dgraph`
- `graph-database`

理由：Dgraph 后端已在 ADR-006 中移除，代码里不存在，保留标签会让人以为用了图数据库。
删除后保留的标签应包含：`python`、`typescript`，以及你实际用到的（`sqlite`、`tree-sitter`、`fastapi`、`git` 等）。

> 注意：Devpost 的标签有时是下拉搜索框，删除后要点保存才会生效。

---

## 2. 更新项目描述（Story / description）

把下面这段**整段替换**原有 "About CodeGraph" 正文。它保留了原来的故事（15 岁、`retryLimit = 3` 的困惑），删掉了已经过时的表述，并加入本轮实测与两处修复。

```text
About CodeGraph

What inspired me

I'm 15, and I keep running into the same problem when I read code. I'll open a file,
see a weird line like `const retryLimit = 3`, and ask: why 3? why not 5? why retry at
all? `git blame` tells me who changed it. GitHub search tells me where it appears.
But nobody tells me why it was written that way.

So I built CodeGraph: one queryable graph of code structure, git history, and the
design decisions behind both.

What it does

You point it at a repository and it answers, for a line:

    $ codegraph why src/codegraph/storage.py:200

    Query src/codegraph/storage.py:200 → 1 matched line-level decision(s)
      Decision #1: Use SQLite (stdlib `sqlite3`) as the store under `.codegraph/graph.db`
        Reason: judges and developers must run the CLI without operating a database
        Alternatives: Dgraph first (rejected for MVP: requires Docker and ops setup)
        Source: adr · ADR 001-use-sqlite-default

It also shows the graph as of any past date (`codegraph graph --at`), and reports
contradictions between decisions (`codegraph conflicts`).

The honest part

A commit subject is not a reason. CodeGraph only shows a decision card when the record
states a reason or a rejected alternative; everything else is stored as history you can
ask for explicitly. That is why the numbers below are small.

Measured on five real repositories, five languages, no per-repository configuration:

    express (JavaScript) : 5920 nodes /  1460 edges / 242 records /  22 decisions
    got     (TypeScript) : 19142     / 65878      / 237         /  36
    flask   (Python)     : 7546      / 19840      / 229         /  54
    cobra   (Go)         : 5218      / 20989      / 217         /  12
    gson    (Java)       : 8439      / 78211      / 223         /  29

The spread is the point: the tool reads the rationale a project already writes down.
Flask documents every release in `CHANGES.rst` (54 decisions); cobra writes short
commit subjects (12). Same extractor, no tuning.

Bugs that testing on real projects found

- `codegraph index` crashed on Express with an IntegrityError: the decision-code link
  table is unique on (decision, file, line), and a class and its first method share a
  start line. Duplicate links are now collapsed at the write boundary.
- Changelog discovery compared file names case-sensitively. Express ships `History.md`,
  so the same checkout read it on Windows and ignored it on macOS/Linux. Now
  case-insensitive: Express went from 5 decisions to 22.
- On Chinese Windows (GBK) the CLI printed `·` as a Chinese character in redirected
  logs, and characters GBK cannot encode crashed the card with UnicodeEncodeError.
  Console streams are now reconfigured to UTF-8.

How it's built

Python + tree-sitter (7 languages) for structure, GitPython for real history, SQLite for
versioned nodes with `valid_from` / `valid_to`. Plus a FastAPI + Cytoscape web UI with a
timeline slider, and a VSCode extension that reads `codegraph why --json`.

Verification

221 tests, over 80% coverage, CI green on a 6-job matrix (Ubuntu/Windows/macOS ×
Python 3.10/3.12). Every test count in the README is checked against the run that
produced it by a script in CI, so a stale number fails the build. The README
screenshots are
generated from captured CLI output, and CI re-renders them and fails if they drift.

Repository: https://github.com/fourwich/codegraph
Live demo: https://fourwich.github.io/codegraph
```

---

## 3. 核对提交表单

在 Devpost 的 **Submit** 页面逐项确认：

| 项目 | 应该是什么 |
|---|---|
| Project name | CodeGraph |
| Elevator pitch | 「Turn code structure, git history, and design decisions into one queryable graph — ask why a line exists, get a decision card.」 |
| GitHub repo URL | `https://github.com/fourwich/codegraph` |
| Live demo URL | `https://fourwich.github.io/codegraph` |
| Video demo link | 你的 5 分钟视频（脚本见仓库 `docs/pitch_5min.md`） |
| Built with | python, typescript, sqlite, tree-sitter, fastapi, git — **不要** dgraph |
| 附件 / 补充文档 | `docs/competition_submission.md`（仓库内，169 行） |

---

## 如果某项改不了

Devpost 在评审期可能锁定表单。如果「Submit」页显示只读或无法保存：

1. 先试 `Edit project`（项目名下方的编辑按钮），项目本身通常仍可编辑
2. 若确实锁定，把第 2 段文案作为一条 **Update** 发出去（项目页已有 "Updates" 区，说明你之前发过），评审仍能看到

---

## 我不做的事（说明边界）

- 不读你的浏览器 cookie、不读登录凭据
- 不在你未授权时启动/关闭浏览器（你已明确要求）
- 不伪造「已修改成功」——如果改不动我会直接说

当前这个 Edge 窗口没有调试端口，所以我无法程序化操作它；上面三步需要你在窗口里完成。
