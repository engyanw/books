"""
Item & Q-Matrix Schema 数据模型。
对应 docs/06-item-and-qmatrix-spec.md（任务 #13）。
Q 矩阵是认知诊断链路的命门，治理优先级高于题目参数估计。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class ItemType(str, Enum):
    OBJECTIVE = "objective"
    SUBJECTIVE = "subjective"


class AuditStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    PILOT = "pilot"            # 预测试池（V2.2 §9.6）
    CALIBRATING = "calibrating"
    APPROVED = "approved"
    RETIRED = "retired"


@dataclass
class QMatrixEntry:
    """题目→知识/认知 的 Q 矩阵项。"""
    knowledge: str
    cognitive: str
    weight: float = 1.0
    is_primary: bool = True
    confidence: float = 1.0     # 主观题标注附置信度（V2.2 §31.2）


@dataclass
class ItemQuality:
    """题目质量模型 12 项（docs §3）。"""
    content_correctness: float = 0.0
    knowledge_coverage: float = 0.0
    cognitive_level: float = 0.0
    difficulty: float = 0.0
    discrimination: float = 0.0
    guessing: float = 0.0
    distractor_quality: float = 0.0
    diagnostic_info: float = 0.0
    ambiguity: float = 0.0
    curriculum_alignment: float = 0.0
    gaokao_relevance: float = 0.0
    exposure_risk: float = 0.0


@dataclass
class Item:
    """题目对象（docs §1）。"""
    id: str
    version: str
    source: str
    text: str
    question: str
    options: list[str] = field(default_factory=list)
    answer: str | None = None
    score_rule: dict[str, object] = field(default_factory=dict)

    knowledge_tags: list[str] = field(default_factory=list)        # L1
    cognitive_tags: list[str] = field(default_factory=list)        # L2
    capability_tags: list[str] = field(default_factory=list)       # L3
    literacy_tags: list[str] = field(default_factory=list)         # L4

    diagnostic_targets: list[str] = field(default_factory=list)
    misconception_targets: list[str] = field(default_factory=list)
    transfer_target: str | None = None

    exposure_count: int = 0
    leakage_risk: str = "low"

    q_matrix: list[QMatrixEntry] = field(default_factory=list)

    # V2.2 §13.2 IRT 适用边界：主观题不套单维 IRT
    irt_applicable: bool = True
    item_type: ItemType = ItemType.OBJECTIVE
    audit_status: AuditStatus = AuditStatus.DRAFT

    quality: ItemQuality = field(default_factory=ItemQuality)


@dataclass
class AnnotationRecord:
    """标注流水线（V2.2 §31.2/§31.3）：双人标注 + 专家仲裁 + 一致性门槛。"""
    item_id: str
    annotators: list[str]
    labels: dict[str, object]
    kappa: float = 0.0           # < 0.6 退回重标
    krippendorff_alpha: float = 0.0
    expert_arbitration: bool = False
    passed: bool = False         # κ/α 达标 + 专家抽检通过才可入库
