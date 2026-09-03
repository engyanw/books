"""DINA / GDINA 实现。

DINA 模型（conjunctive）：
    η_j(α) = ∏_{k∈Q_j} α_k                       # 全部所需技能掌握=1
    P(X_j=1 | α) = g_j + (1 - s_j - g_j) · η_j(α)  # g_j=guess, s_j=slip
        η=1 → P(correct)=1-s_j
        η=0 → P(correct)=g_j

后验：P(α | x) ∝ ∏_j P(x_j | α) · P(α)
边际掌握：P(α_k=1 | x) = Σ_{α:α_k=1} P(α | x)

采用对数域枚举（K≤~15 可行；更大需 MCMC，MVP 节点规模够用）。
"""
from __future__ import annotations
import math
from itertools import product
from typing import Iterable


def _log_likelihood(alpha: tuple[int, ...], items: list[dict], responses: dict[str, int]) -> float:
    """对数似然 log P(x | α)。"""
    ll = 0.0
    for it in items:
        j = it["id"]
        if j not in responses:
            continue
        x = responses[j]
        required = it["required"]            # list[int] 技能下标
        eta = 1
        for k in required:
            if alpha[k] == 0:
                eta = 0
                break
        s, g = it["slip"], it["guess"]
        p_correct = g + (1 - s - g) * eta
        p = p_correct if x == 1 else (1 - p_correct)
        p = max(p, 1e-12)
        ll += math.log(p)
    return ll


class DINA:
    """DINA 模型。q_matrix/slip/guess 以 item 字典形式给出。"""

    def __init__(
        self,
        skills: list[str],
        items: list[dict],
        prior: float = 0.5,
    ) -> None:
        """
        skills: 技能 id 列表。
        items:  [{"id": item_id, "required": [skill_idx,...], "slip": s, "guess": g}]
        prior:  每技能先验掌握概率（经验贝叶斯群体先验，V2.2 §9.5/§9.6）。
        """
        self.skills = skills
        self.items = items
        self.prior = prior

    def posterior_mastery(self, responses: dict[str, int]) -> dict[str, float]:
        """返回每个技能的 P(α_k=1 | x)。responses: {item_id: 0/1}。"""
        K = len(self.skills)
        skill_idx = {k: i for i, k in enumerate(self.skills)}

        # 对数先验：log P(α)，独立伯努利(prior)
        def log_prior(alpha: tuple[int, ...]) -> float:
            p = self.prior
            return sum(math.log(p if a == 1 else (1 - p)) for a in alpha)

        log_post: list[tuple[tuple[int, ...], float]] = []
        for alpha in product([0, 1], repeat=K):
            lp = _log_likelihood(alpha, self.items, responses) + log_prior(alpha)
            log_post.append((alpha, lp))

        m = max(lp for _, lp in log_post)
        weights = [math.exp(lp - m) for _, lp in log_post]
        Z = sum(weights)
        probs = [w / Z for w in weights]

        marginal = [0.0] * K
        for (alpha, _), p in zip(log_post, probs):
            for k in range(K):
                if alpha[k] == 1:
                    marginal[k] += p
        return {self.skills[i]: marginal[i] for i in range(K)}


class GDINA:
    """GDINA——广义 DINA。

    每个"所需技能掌握模式" η 的子模式有独立概率（不再强制 conjunctive）。
    用于 DINA 颗粒度不足时的连续化扩展（V2.2 §13.1）。
    此处给出框架与默认 DINA 等价的简化实现；完整 GDINA 需对每个 item 的
    Q-模式学一组参数（需更多数据），数据不足时退回 DINA。
    """

    def __init__(self, skills: list[str], items: list[dict]) -> None:
        self.dina = DINA(skills, items)

    def posterior_mastery(self, responses: dict[str, int]) -> dict[str, float]:
        # 数据不足时退回 DINA（MVP 阶段）
        return self.dina.posterior_mastery(responses)
