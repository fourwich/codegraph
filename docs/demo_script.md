# 60 秒终端 Demo 脚本（CodeGraph）

## 0-10 秒：展示问题

旁白：
> 「git blame 只告诉你是谁改的，不告诉你为什么。」

终端演示：
```bash
git blame src/codegraph/storage.py | sed -n '195,200p'
```

---

## 10-25 秒：运行 codegraph why

旁白：
> 「CodeGraph 能直接回答：这行代码背后的设计决策是什么，以及当时否决了哪些方案。」

```bash
codegraph index . --depth 50
codegraph why docs/adr/001-use-sqlite-default.md:1
```

展示输出：决策卡片（决策 / 原因 / 备选 / 来源 / 状态 / 可信度）。
该仓库自己没有把 ADR 绑定到代码行，所以这里用 ADR 文件本身作为位置；
查询 `src/` 下的行会明确返回「No decision record found」，而不是猜一个。

---

## 25-40 秒：运行 codegraph graph --at

旁白：
> 「还能按历史时刻查看当时的代码图。」

```bash
codegraph graph --at 2026-09-23 --scope src
codegraph graph --at 2026-09-28 --scope src
```

展示：节点数、边数、变更摘要（本仓库 2026-09-23 / 2026-09-28 两次快照）。

---

## 40-55 秒：展示 Web 可视化

旁白：
> 「决策和代码在一张图上，可以按时间回放。」

```bash
codegraph serve --port 8080
# 打开 http://127.0.0.1:8080/
```

展示：决策图谱（CodeNode 节点 + Decision 卡片 + Git 时间轴）。

---

## 55-60 秒：一句话收尾

旁白：
> 「CodeGraph：代码的决策记忆层。」

---

## 录屏命令

asciinema：
```bash
asciinema rec codegraph-demo.cast
# 演示结束后 Ctrl+D
asciinema upload codegraph-demo.cast
```

terminalizer：
```bash
terminalizer record codegraph-demo
terminalizer render codegraph-demo
```

## 演示用示例仓库

本脚本直接在本仓库上演示（`codegraph index . --depth 50`）：

- 决策示例：`docs/adr/001-use-sqlite-default.md`（含原因与两个被否决方案）
- 变更时间线：`codegraph decisions --file CHANGELOG.md --timeline`
- 历史快照：`codegraph graph --at 2026-09-23 --scope src`

`src/auth/session.ts` 与 `examples/demo_repo` 是早期版本留下的占位示例，
仓库里并不存在，不要出现在录屏里。
