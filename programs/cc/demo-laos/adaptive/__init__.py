"""自适应测评引擎（Phase 5）。

对应 docs/08 与任务 #19。
确定性 Adaptive Engine：当前状态 → 候选题 → 过滤约束 → 计算 EIG → 选下一题。
单次测评内用 t-1 冻结状态选题（V2.2 §12.2）。
"""
from .engine import AdaptiveEngine, AdaptiveConstraints
from .probe import ProbeEngine, ProbeLevel, Probe

__all__ = [
    "AdaptiveEngine", "AdaptiveConstraints",
    "ProbeEngine", "ProbeLevel", "Probe",
]
