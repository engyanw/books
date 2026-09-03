"""自适应选题引擎。

EIG 代理：对 IRT 题，信息量 I(θ)=a²P(1-P) 在当前能力处取值即为
"作答后预期不确定性减少"的良好代理（docs/08 §3）。
目标：max EIG / Cost，受多约束（docs/08 §4）。
终止规则：后验方差<τ / 信息增益边际<ε / 测量安全上限（docs/08 §5）。
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field

from schemas.item import Item
from schemas.state import StudentCognitiveState, StateStatus
from repository import ItemRepository
from irt.model import TwoPL, IRT


@dataclass
class AdaptiveConstraints:
    """docs/08 §4 多约束。"""
    content_coverage: set[str] = field(default_factory=set)   # 必须覆盖的 knowledge
    difficulty_range: tuple[float, float] = (-3.0, 3.0)
    item_types: set[str] = field(default_factory=lambda: {"objective"})
    exposure_cap: float = 0.5             # Sympson-Hetter 类曝光上限
    max_length: int = 20
    min_length: int = 8
    fatigue_budget: float = 1e9           # 累计成本上限
    target_variance: float = 0.05         # 后验方差阈值 τ
    eig_epsilon: float = 0.01             # 边际信息增益阈值


class AdaptiveEngine:
    """确定性自适应选题。"""

    def __init__(
        self,
        item_repo: ItemRepository,
        irt_items: list[TwoPL],
    ) -> None:
        self.item_repo = item_repo
        self.irt = IRT(irt_items)
        self.irt_by_id = {it.id: it for it in irt_items}

    def _passes_constraints(self, item: Item, seen: set[str], cost_used: float,
                            constraints: AdaptiveConstraints) -> bool:
        if item.id in seen:
            return False
        if item.item_type.value not in constraints.item_types:
            return False
        # 曝光：已用次数/容量（占位：用 seen 计数代理）
        if len(seen) >= 1 and item.id in seen:
            return False
        # 难度（用 IRT b 近似）
        tp = self.irt_by_id.get(item.id)
        if tp is not None:
            if not (constraints.difficulty_range[0] <= tp.b <= constraints.difficulty_range[1]):
                return False
        return True

    def eig(self, item: Item, theta: float, cost: float = 1.0) -> float:
        """预期信息增益代理（docs/08 §3）。"""
        tp = self.irt_by_id.get(item.id)
        if tp is None:
            return 0.0
        info = tp.info(theta)
        return info / max(cost, 1e-6)

    def select_next(
        self,
        state: StudentCognitiveState,
        candidates: list[Item],
        seen: set[str],
        cost_used: float,
        constraints: AdaptiveConstraints,
    ) -> Item | None:
        """选题：过滤约束 → max EIG/cost。用 t-1 冻结状态（V2.2 §12.2）。"""
        # 当前能力代理：mastery → θ
        p = max(min(state.core.mastery, 1 - 1e-6), 1e-6)
        theta = math.log(p / (1 - p))   # logit 作 θ 代理

        feasible = [it for it in candidates
                    if self._passes_constraints(it, seen, cost_used, constraints)]
        if not feasible:
            return None
        # 内容覆盖优先：未覆盖的必选知识优先
        uncovered = [it for it in feasible
                     if set(it.knowledge_tags) & constraints.content_coverage - seen_covered(seen, candidates)]
        pool = uncovered or feasible
        best = max(pool, key=lambda it: self.eig(it, theta))
        return best

    def should_stop(
        self,
        state: StudentCognitiveState,
        seen: list[str],
        candidates: list[Item],
        cost_used: float,
        constraints: AdaptiveConstraints,
    ) -> bool:
        """终止规则（docs/08 §5）。"""
        # 测量安全上限
        if len(seen) >= constraints.max_length:
            return True
        # 最小长度内不停
        if len(seen) < constraints.min_length:
            return False
        # 后验方差达标
        if state.uncertainty.posterior_variance < constraints.target_variance:
            return True
        # 边际信息增益不足
        p = max(min(state.core.mastery, 1 - 1e-6), 1e-6)
        theta = math.log(p / (1 - p))
        remaining = [it for it in candidates if it.id not in seen]
        max_eig = max((self.eig(it, theta) for it in remaining), default=0.0)
        if max_eig < constraints.eig_epsilon:
            return True
        return False


def seen_covered(seen: set[str], candidates: list[Item]) -> set[str]:
    """已见题覆盖的知识节点集合。"""
    covered: set[str] = set()
    cand_by_id = {it.id: it for it in candidates}
    for sid in seen:
        it = cand_by_id.get(sid)
        if it:
            covered.update(it.knowledge_tags)
    return covered
