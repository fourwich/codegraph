# CodeGraph

把代码结构、历史变更和设计决策变成一张可查询的图。

当前阶段：**MVP CLI 骨架**（假数据流程已跑通，尚未接入 tree-sitter / Dgraph）。

## 快速开始

```bash
# 推荐：uv
uv venv
uv pip install -e ".[dev]"

# 或：venv + pip
python -m venv .venv
.venv/bin/pip install -e ".[dev]"   # Windows: .venv\Scripts\pip install -e ".[dev]"
```

## 命令

```bash
codegraph --help
codegraph index .
codegraph why src/auth/session.ts:42
codegraph graph --at 2024-11-02 --scope src
codegraph decisions --file src/auth/session.ts --timeline
```

## 测试

```bash
pytest
# 或
pytest --cov=src/codegraph
```

## 技术栈

| 层 | 选型 |
|---|---|
| CLI | Python + Typer |
| 终端输出 | Rich |
| 数据模型 | pydantic |
| 包管理 | uv 或 pip + venv |

## 目录

```
src/codegraph/
  cli.py          # Typer 入口
  models.py       # Decision / CodeNode
  data.py         # MVP 假数据
  commands/       # index / why / graph / decisions
tests/test_cli.py
```

## 许可证

MIT
