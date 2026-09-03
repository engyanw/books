"""学习决策引擎实现。

效用模型（V2.2 §19）：
    U(a|s) = ExpectedGain × Priority × TransferValue / LearningCost
        + ExplorationValue           # UCB 探索项，防局部最优

ExpectedGain：由历史干预效果预测（MVP 用代理：(1 - mastery) × 节点相关度）。
探索项：UCB1 = c · sqrt(ln(t) / (1 + n_a))，使低置信动作被探索。
熔断（V2.2 §23）：状态低置信 + 多独立失败 + 错误模式一致 + 连续增益不足 → 降维。
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import Enum


class ActionType(str, Enum):
    EXPLAIN = "explain"             # 知识讲解
    EXAMPLE = "example"            # 例题学习
    BASIC_DRILL = "basic_drill"
    APPLY_DRILL = "apply_drill"
    TRANSFER_DRILL = "transfer_drill"
    ERROR_REDO = "error_redo"
    SPACED_REVIEW = "spaced_review"
    COMPREHENSIVE = "comprehensive"


class InterventionLevel(str, Enum):
    """三级干预（V2.2 §23）。"""
    NORMAL = "normal"
    ONE = "one"          # 降低任务复杂度
    TWO = "two"          # 更换教学策略
    THREE = "three"      # 教师人工介入


@dataclass
class LearningAction:
    action_type: ActionType
    node_id: str
    utility: float
    expected_gain: float
    exploration_value: float
    cost: float
    reasoning: str = ""


@dataclass
class ActionStats:
    """历史动作统计（用于 ExpectedGain 估计与 UCB）。"""
    n: int = 0
    total_gain: float = 0.0
    last_gain: float = 0.0

    def avg_gain(self) -> float:
        return self.total_gain / self.n if self.n > 0 else 0.0


class CircuitBreaker:
    """熔断判定（V2.2 §23）：多因素触发降维。"""

    def __init__(
        self,
        confidence_threshold: float = 0.4,
        min_independent_failures: int = 2,
        error_consistency: float = 0.6,
        gain_threshold: float = 0.1,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.min_failures = min_independent_failures
        self.error_consistency = error_consistency
        self.gain_threshold = gain_threshold

    def evaluate(
        self,
        confidence: float,
        independent_failures: int,
        error_consistency: float,
        recent_gain: float,
    ) -> InterventionLevel:
        score = 0
        if confidence < self.confidence_threshold:
            score += 1
        if independent_failures >= self.min_failures:
            score += 1
        if error_consistency >= self.error_consistency:
            score += 1
        if recent_gain < self.gain_threshold:
            score += 1
        if score >= 4:
            return InterventionLevel.THREE
        if score >= 3:
            return InterventionLevel.TWO
        if score >= 2:
            return InterventionLevel.ONE
        return InterventionLevel.NORMAL


class LearningDecisionEngine:
    """学习决策引擎。"""

    def __init__(
        self,
        explore_c: float = 1.0,
        stats: dict[tuple, ActionStats] | None = None,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self.explore_c = explore_c
        self.stats = stats or {}
        self.breaker = breaker or CircuitBreaker()
        self.t = 0   # 全局决策次数

    def decide(
        self,
        state,                          # StudentCognitiveState
        candidate_actions: list[ActionType],
        priority: dict[str, float],      # node_id -> priority
        transfer_value: dict[ActionType, float] = None,
        cost: dict[ActionType, float] = None,
    ) -> LearningAction:
        """选择 Next Learning Action（效用 + UCB 探索）。"""
        self.t += 1
        tv = transfer_value or {}
        co = cost or {}
        node_id = state.node_id

        best: LearningAction | None = None
        for a in candidate_actions:
            # ExpectedGain 代理：(1 - mastery) × 节点优先级
            gap = max(0.0, 1.0 - state.core.mastery)
            pri = priority.get(node_id, 0.5)
            eg = gap * pri
            tv_a = tv.get(a, 0.5)
            cost_a = co.get(a, 1.0)
            base = (eg * pri * tv_a) / max(cost_a, 1e-6)

            # UCB1 探索项
            key = (node_id, a)
            stats = self.stats.get(key, ActionStats())
            n_a = stats.n
            exploration = self.explore_c * math.sqrt(
                math.log(max(self.t, 2)) / max(1, n_a + 1)
            )
            utility = base + exploration
            act = LearningAction(
                action_type=a, node_id=node_id, utility=utility,
                expected_gain=eg, exploration_value=exploration, cost=cost_a,
                reasoning=f"gap={gap:.2f} pri={pri:.2f} tv={tv_a:.2f} "
                          f"base={base:.2f} explore={exploration:.2f}",
            )
            if best is None or utility > best.utility:
                best = act
        return best  # type: ignore

    def record_outcome(self, node_id: str, action: ActionType, gain: float) -> None:
        """记录干预效果，校准 ExpectedGain（V2.2 §19）。"""
        key = (node_id, action)
        s = self.stats.setdefault(key, ActionStats())
        s.n += 1
        s.total_gain += gain
        s.last_gain = gain
