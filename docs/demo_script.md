# 60 秒终端 Demo 脚本（CodeGraph）

## 0-10 秒：展示问题

旁白：
> 「git blame 只告诉你是谁改的，不告诉你为什么。」

终端演示：
```bash
git blame src/auth/session.ts | sed -n '40,45p'
```

---

## 10-25 秒：运行 codegraph why

旁白：
> 「CodeGraph 能直接回答：这行代码背后的设计决策是什么。」

```bash
codegraph why src/auth/session.ts:42
```

展示输出：决策卡片（摘要 / 原因 / 备选 / 来源 / 约束 / 可信度）。

---

## 25-40 秒：运行 codegraph graph --at

旁白：
> 「还能按历史时刻查看当时的代码图。」

```bash
codegraph graph --at 2024-11-02 --scope src
```

展示：节点数、边数、变更摘要。

---

## 40-55 秒：展示 Web 可视化

旁白：
> 「决策和代码在一张图上，关联可多跳查询。」

```bash
codegraph serve
# 打开 http://localhost:3000
```

展示：决策图谱（CodeNode 节点 + Decision 琥珀色卡片 + Git 时间轴）。

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

- 路径：`examples/demo_repo`
- 关键文件：`src/auth/session.ts:42`
- 预置决策：PR #48 / Issue #31 / ADR-003（有状态 JWT + 黑名单）
