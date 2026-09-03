"""
Student Cognitive State Schema 数据模型。
对应 docs/04-student-cognitive-state-schema.md（任务 #15）。
四层状态：核心认知 / 动态 / 诊断 / 不确定性 + 融合输出。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class StateStatus(str, Enum):
    """可识别性约束（V2.2 §9.6）：未达门槛只输出 insufficient_evidence，不强行给值。"""
    OK = "ok"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    COLD_START = "cold_start"


@dataclass
class CoreState:
    """A 核心认知状态。"""
    mastery: float = 0.0           # [0,1]
    application: float = 0.0
    transfer: float = 0.0


@dataclass
class DynamicState:
    """B 动态状态。"""
    stability: float = 0.0
    forgetting_risk: float = 0.0


@dataclass
class DiagnosticState:
    """C 诊断状态（错误归因，多级因果链）。"""
    error_distribution: dict[str, float] = field(default_factory=dict)
    # 键：context_discrim / knowledge_confusion / execution ...
    misconception: str | None = None


@dataclass
class UncertaintyState:
    """D 不确定性。"""
    posterior_variance: float = 1.0
    confidence: float = 0.0
    evidence_count: int = 0
    evidence_diversity: int = 0
    recency: float = 0.0
    effective_n: float = 0.0        # 融合有效样本量


@dataclass
class FusionOutput:
    """V2.2 §9.5 融合须输出：后验均值 + 方差 + 有效样本量 + 各模型贡献权重（可反解）。"""
    posterior_mean: float = 0.0
    posterior_var: float = 1.0
    effective_n: float = 0.0
    model_contributions: dict[str, float] = field(default_factory=dict)
    # dina / irt / kt / forgetting_prior / probe
    is_multimodal: bool = False     # 多峰 → 落入"证据不足"通道


@dataclass
class StudentCognitiveState:
    """统一学生认知状态。学生状态独立于知识图谱与题库存储。"""
    student_id: str
    node_id: str
    node_version: str
    domain: str

    core: CoreState = field(default_factory=CoreState)
    dynamic: DynamicState = field(default_factory=DynamicState)
    diagnostic: DiagnosticState = field(default_factory=DiagnosticState)
    uncertainty: UncertaintyState = field(default_factory=UncertaintyState)
    fusion: FusionOutput = field(default_factory=FusionOutput)

    status: StateStatus = StateStatus.COLD_START

    meta: dict[str, str] = field(default_factory=dict)
    # state_version / model_version / qmatrix_version / standard_version
    updated_at: datetime | None = None


# ---- 访问接口（权限边界，V2.2 §20）------------------------------------------
# getState(...)            只读，Agent/Tutor 可读
# updateState(...)         写，【仅 Assessment Engine 可调】
# getProvenance(state_id)  只读，反查证据链
#
# 实现（Service 层）属任务 #15 的服务层，数据模型层在此定义。
