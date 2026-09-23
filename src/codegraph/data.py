"""内置示例决策与代码节点（假数据）。

MVP 阶段用于跑通 CLI 流程，后续由 tree-sitter + Dgraph 替换。
"""

from __future__ import annotations

from datetime import datetime

from codegraph.models import CodeNode, Decision, DecisionSource, DecisionStatus

# 全量示例决策：按 file:line 精确匹配
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

SAMPLE_NODES: list[CodeNode] = [
    CodeNode(
        uid="n-001",
        kind="function",
        name="createSession",
        file_path="src/auth/session.ts",
        line_start=40,
        line_end=58,
        language="typescript",
        commit_sha="a3f91c",
    ),
    CodeNode(
        uid="n-002",
        kind="function",
        name="hashPassword",
        file_path="src/auth/password.ts",
        line_start=12,
        line_end=30,
        language="typescript",
        commit_sha="c81e2b",
    ),
    CodeNode(
        uid="n-003",
        kind="variable",
        name="cacheKey",
        file_path="src/cache/keys.ts",
        line_start=1,
        line_end=20,
        language="typescript",
        commit_sha="9dd01a",
    ),
    CodeNode(
        uid="n-004",
        kind="function",
        name="listOrders",
        file_path="src/api/orders.ts",
        line_start=55,
        line_end=90,
        language="typescript",
        commit_sha="b4c12aa",
    ),
    CodeNode(
        uid="n-005",
        kind="class",
        name="User",
        file_path="src/models/user.ts",
        line_start=3,
        line_end=40,
        language="typescript",
        commit_sha="a3f91c",
    ),
]


def find_decisions_for_location(file_path: str, line: int) -> list[Decision]:
    """返回绑定到指定文件行的全部决策。"""
    return [d for d in SAMPLE_DECISIONS if d.matches_location(file_path, line)]


def normalize_location_path(raw: str) -> str:
    """把用户输入的路径规范为正斜杠形式，便于和样例数据比对。"""
    return raw.strip().replace("\\", "/").lstrip("./")
