"""
Evidence & Learning Event Schema 数据模型。
对应 docs/05-evidence-and-learning-event-schema.md（任务 #12）。
系统核心对象是 Evidence（非成绩）。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EvidenceLevel(str, Enum):
    """V2.2 §15 证据等级——不同层级效力不同。"""
    A = "A"   # 标准化外部测试 / 能力锚定
    B = "B"   # 独立新题 / 状态验证
    C = "C"   # 常规训练题 / 状态更新
    D = "D"   # 探针 / 原因诊断
    E = "E"   # 行为数据 / 辅助判断


class EvidenceSource(str, Enum):
    DIRECT_ANSWER = "direct_answer"
    SCORED = "scored"
    ESSAY_TEXT = "essay_text"
    BEHAVIOR = "behavior"
    PROBE = "probe"
    TRANSFER = "transfer"
    EXTERNAL_ANCHOR = "external_anchor"
    TEACHER = "teacher"


@dataclass
class Evidence:
    """核心对象：Evidence。含全部版本字段，保证可追溯（V2.2 §6.3）。"""
    id: str
    student_id: str
    item_id: str
    item_version: str
    assessment_id: str | None = None

    response: str | None = None
    score: float | None = None
    response_time: float | None = None
    hint_used: bool = False
    attempt: int = 1

    rubric_version: str | None = None
    model_version: str | None = None
    qmatrix_version: str | None = None
    standard_version: str = "STD_1.0"

    timestamp: datetime | None = None
    source: EvidenceSource = EvidenceSource.DIRECT_ANSWER
    evidence_level: EvidenceLevel = EvidenceLevel.C
    exposure_penalty: float = 0.0   # 同题重复证据降权（V2.2 §15）

    provenance: dict[str, object] = field(default_factory=dict)
    # linked_state, weight——反查链（V2.2 §6.3）


@dataclass
class InsufficientEvidenceResult:
    """证据不足机制（V2.2 §17）：不强行二选一，保留多假设 + 证据不足份额。"""
    primary_hypothesis: str
    primary_prob: float
    alternative_hypothesis: str | None
    alternative_prob: float
    insufficient_share: float
    suggestion: str                # 建议：增加 N 个独立情境证据
