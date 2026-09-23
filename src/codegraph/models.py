"""CodeGraph 核心数据模型。

用 pydantic 描述代码节点与设计决策，后续可直接映射到 Dgraph schema。
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
    commit_sha: str = Field(description="引入该节点的提交")


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
