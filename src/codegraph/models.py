"""CodeGraph 核心数据模型与内置示例决策数据。

用 pydantic 描述代码节点、关系边与设计决策；结构数据来自 tree-sitter，
决策 MVP 阶段仍用示例数据。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DecisionStatus(str, Enum):
    """决策生命周期状态。"""

    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class DecisionSource(str, Enum):
    """决策来源类型。"""

    PR = "pr"
    ISSUE = "issue"
    ADR = "adr"
    COMMIT = "commit"
    COMMENT = "comment"


class CodeNode(BaseModel):
    """代码结构节点：函数、类、变量或文件。"""

    uid: str = Field(description="稳定标识")
    kind: str = Field(description="function / class / variable / file / module")
    name: str = Field(description="符号名")
    file_path: str = Field(description="相对仓库根的路径")
    line_start: int = Field(ge=1, description="起始行")
    line_end: int = Field(ge=1, description="结束行")
    language: str = Field(description="源语言")
    commit_sha: str = Field(default="", description="引入该节点的提交")
    parent_uid: str | None = Field(default=None, description="父节点 uid，无则为顶层")

    def contains_line(self, line: int) -> bool:
        """判断行号是否落在该节点范围内（含端点）。"""
        return self.line_start <= line <= self.line_end


class Edge(BaseModel):
    """代码关系边。"""

    from_uid: str = Field(description="起点节点 uid")
    to_uid: str = Field(description="终点节点 uid")
    kind: str = Field(description="uses / defined_by / contains")
    file_path: str = Field(default="", description="边所在文件")
    line: int = Field(default=1, ge=1, description="边所在行")


class Decision(BaseModel):
    """设计决策：为什么这段代码长成这样。"""

    uid: str = Field(description="稳定标识")
    content: str = Field(description="决策摘要")
    reason: str = Field(default="", description="原因")
    alternatives: list[str] = Field(default_factory=list, description="考虑过但否决的方案")
    status: DecisionStatus = Field(default=DecisionStatus.ACCEPTED)
    source: DecisionSource = Field(default=DecisionSource.ADR)
    source_ref: str = Field(default="", description="来源引用，如 PR #48")
    timestamp: datetime = Field(description="决策时间")
    author: str = Field(default="", description="决策者")
    file_path: str = Field(default="", description="关联代码位置")
    line: int | None = Field(default=None, description="关联行号")
    constraints: list[str] = Field(default_factory=list, description="相关约束")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="可信度 0-1")

    def matches_location(self, file_path: str, line: int) -> bool:
        """判断决策是否精确绑定到某文件行。"""
        return self.file_path == file_path and self.line == line


def normalize_location_path(raw: str) -> str:
    """把用户输入的路径规范为正斜杠形式，便于和样例数据比对。"""
    return raw.strip().replace("\\", "/").lstrip("./")


def make_uid(file_path: str, kind: str, name: str, line_start: int) -> str:
    """生成稳定节点 uid。"""
    path = normalize_location_path(file_path)
    return f"{path}::{kind}::{name}@{line_start}"


# 内置示例决策：按 file:line 精确匹配（3-5 条假数据）
SAMPLE_DECISIONS: list[Decision] = [
    Decision(
        uid="dec-001",
        content="会话令牌使用有状态 JWT + 服务端黑名单",
        reason=(
            "登录态需要支持「一键全端下线」；纯无状态 JWT 无法即时失效，"
            "而全量有状态 session 又让网关必须查库。折中：JWT 携带 jti，网关缓存黑名单。"
        ),
        alternatives=[
            "纯无状态 JWT（否决：无法即时踢人）",
            "服务端全量 Session（否决：网关查库成本高）",
        ],
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.PR,
        source_ref="PR #48 · Issue #31 · ADR-003",
        timestamp=datetime(2024, 11, 2, 15, 30, 0),
        author="chen@example.com",
        file_path="src/auth/session.ts",
        line=42,
        constraints=[
            "兼容移动端旧客户端 header 格式",
            "P99 鉴权延迟 < 5ms",
            "密钥轮转不打断进行中会话",
        ],
        confidence=0.92,
    ),
    Decision(
        uid="dec-002",
        content="bcrypt 成本因子固定为 12",
        reason="在当前 CI 机器与登录 QPS 下，12 轮约 80ms，暴力破解成本足够高且登录不卡顿。",
        alternatives=["Argon2id（否决：迁移哈希成本高）", "PBKDF2（否决：库支持与参数约定更弱）"],
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.ADR,
        source_ref="ADR-003",
        timestamp=datetime(2024, 11, 2, 16, 10, 0),
        author="security@example.com",
        file_path="src/auth/password.ts",
        line=18,
        constraints=["与既有 User.password_hash 格式兼容", "登录接口 P95 < 150ms"],
        confidence=0.88,
    ),
    Decision(
        uid="dec-003",
        content="缓存键统一带租户前缀",
        reason="多租户部署时曾出现跨租户脏读；要求所有 Redis key 以 tenant:{id}: 开头，并在写入层强制。",
        alternatives=["仅在业务层拼前缀（否决：容易漏）"],
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.ISSUE,
        source_ref="Issue #77",
        timestamp=datetime(2025, 1, 18, 10, 0, 0),
        author="ops@example.com",
        file_path="src/cache/keys.ts",
        line=7,
        constraints=["禁止手写裸 key", "灰度期间双写旧键 7 天"],
        confidence=0.95,
    ),
    Decision(
        uid="dec-004",
        content="分页游标用 (created_at, id) 而非 offset",
        reason="订单列表深翻页在 offset 大于 10 万后 P99 恶化到 2s；游标分页稳定在 40ms。",
        alternatives=["offset/limit（否决：深翻页不稳定）"],
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.COMMIT,
        source_ref="commit b4c12aa",
        timestamp=datetime(2025, 3, 4, 9, 20, 0),
        author="backend@example.com",
        file_path="src/api/orders.ts",
        line=63,
        constraints=["前端保持「加载更多」交互不变"],
        confidence=0.84,
    ),
    Decision(
        uid="dec-005",
        content="弃用 V1 双写协议",
        reason="V1 双写在灰度结束后无流量，继续保留会增加 schema 兼容成本。",
        alternatives=["永久保留双写（否决：维护成本）"],
        status=DecisionStatus.SUPERSEDED,
        source=DecisionSource.PR,
        source_ref="PR #120（取代 ADR-001 双写方案）",
        timestamp=datetime(2025, 5, 9, 14, 0, 0),
        author="arch@example.com",
        file_path="src/api/orders.ts",
        line=63,
        constraints=["下线前确认监控无 V1 写流量"],
        confidence=0.75,
    ),
]


def find_decisions_for_location(file_path: str, line: int) -> list[Decision]:
    """返回绑定到指定文件行的全部决策。"""
    return [d for d in SAMPLE_DECISIONS if d.matches_location(file_path, line)]


def find_decisions_for_file(file_path: str) -> list[Decision]:
    """返回绑定到指定文件（或路径前缀）的全部决策。"""
    prefix = normalize_location_path(file_path)
    matched = [d for d in SAMPLE_DECISIONS if d.file_path == prefix or d.file_path.startswith(prefix)]
    return sorted(matched, key=lambda d: d.timestamp)
