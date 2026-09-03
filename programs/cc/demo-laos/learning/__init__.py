"""学习决策引擎（Phase 6）。

对应 docs/09 §1-5 与任务 #21。
输入：Student State + Goal + Time + Item Pool + Content Resources → Next Learning Action。
效用：ExpectedGain × Priority × TransferValue / LearningCost，加 UCB 探索项（V2.2 §19）。
熔断：多因素触发降维，非机械"失败2次降级"（V2.2 §23）。
"""
from .decision import (
    LearningDecisionEngine, LearningAction, ActionType,
    CircuitBreaker, InterventionLevel,
)

__all__ = [
    "LearningDecisionEngine", "LearningAction", "ActionType",
    "CircuitBreaker", "InterventionLevel",
]
