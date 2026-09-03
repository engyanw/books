"""
Ontology & Knowledge Graph 数据模型。
对应 docs/03-ontology-and-knowledge-graph.md（任务 #11）。
定义 L1 知识 / L2 认知过程 / L3 任务能力 / L4 核心素养 节点与关系。
学生状态不在此处，见 state.py。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class Domain(str, Enum):
    CLASSICAL_READING = "classical_reading"
    MODERN_READING = "modern_reading"      # MVP 不做
    POETRY = "poetry"                       # MVP 不做
    WRITING = "writing"                     # MVP 不做
    COMPREHENSIVE = "comprehensive"         # MVP 不做


class RelationType(str, Enum):
    """关系类型——不采用刚性前置，多类型关系 + 条件依赖 + 证据权重（V2.2 §7.1）。"""
    PREREQUISITE = "prerequisite"
    SUPPORT = "support"
    SIMILARITY = "similarity"
    CONTRAST = "contrast"
    COMPOSITION = "composition"
    TRANSFER = "transfer"


class CognitiveProcess(str, Enum):
    """L2 认知过程枚举（docs §2.2）。"""
    RECALL = "RECALL"
    UNDERSTAND = "UNDERSTAND"
    ANALYZE = "ANALYZE"
    INFER = "INFER"
    EVALUATE = "EVALUATE"
    TRANSFER = "TRANSFER"
    EXPRESS = "EXPRESS"


@dataclass
class CoreLiteracy:
    """L4 核心素养。"""
    id: str                       # L01..L04
    label: str
    version: str = "STD_1.0"


@dataclass
class TaskCapability:
    """L3 任务能力（可观察的任务表现维度，非心理能力本体）。"""
    id: str                       # CA01..CA05
    label: str
    domain: Domain
    literacy_weights: dict[str, float] = field(default_factory=dict)
    # 一任务可映射多素养（docs §4）；权重为待校准参数（V2.2 §5.1）


@dataclass
class Knowledge:
    """L1 知识节点。"""
    id: str                       # K-<DOMAIN>-<SUBTYPE>-<SEQ>
    label: str
    domain: Domain
    sub_type: str
    contexts: list[str] = field(default_factory=list)
    common_errors: list[str] = field(default_factory=list)
    typical_items: list[str] = field(default_factory=list)
    related_resources: list[str] = field(default_factory=list)
    version: str = "1.0"


@dataclass
class Relation:
    """知识/能力间关系。"""
    id: str                       # R-<SEQ>
    src: str                      # 节点 id
    dst: str                      # 节点 id
    type: RelationType
    weight: float = 1.0           # 条件依赖/证据权重，待校准
    version: str = "1.0"


@dataclass
class StandardMapping:
    """标准层映射：目标 → 核心素养 → 任务能力 → 认知表现 → 知识资源（docs §4.1）。
    标准层与知识层解耦，标准定义"达成"，图谱定义"结构与关系"。"""
    standard_id: str
    target: str
    literacy_id: str
    task_id: str
    cognitive_process: CognitiveProcess
    knowledge_id: str
    evidence_requirement: str
    standard_version: str = "STD_1.0"
