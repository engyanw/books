"""保持模型 + 干预效果评价（任务 #24）。

V2.2 §26：不套固定艾宾浩斯曲线，用群体先验 → 个体参数的个性化保持模型。
V2.2 §11.4：Absolute Gain / Normalized Gain / Effect Size / Retention Gain / Transfer Gain；
条件允许做 Treatment vs Control，否则不把前后测差异直接解释为系统造成的提升。
"""
from __future__ import annotations
import math
from dataclasses import dataclass


class RetentionModel:
    """个性化保持模型：群体先验 + 个体参数。

    保持率 R(t) = exp(-λ t)，λ 个体遗忘率。
    群体先验 λ0（如 0.05/天），个体证据收缩估计。
    """

    def __init__(self, group_lambda: float = 0.05, prior_strength: float = 5.0) -> None:
        self.group_lambda = group_lambda
        self.prior_strength = prior_strength  # 贝叶斯伪样本量

    def fit_individual(self, observations: list[tuple[float, float]]) -> float:
        """observations: [(days_since, retained_0or1)...] → 个体 λ。"""
        # 简化贝叶斯：λ = (prior_strength·λ0 + Σ fail) / (prior_strength + Σ t)
        # 其中 fail ≈ 1 - retained 在 t 处的期望
        num = self.prior_strength * self.group_lambda
        den = self.prior_strength
        for days, ret in observations:
            num += (1.0 - ret)
            den += days
        return num / max(den, 1e-6)

    def retention(self, lam: float, days: float) -> float:
        return math.exp(-lam * days)


@dataclass
class InterventionEffect:
    """干预效果评价（V2.2 §11.4）。"""

    pre_mean: float
    post_mean: float
    pre_sd: float = 1.0
    post_sd: float = 1.0
    n: int = 1
    retention_gain: float = 0.0   # 延迟保持后相对 post 的保持
    transfer_gain: float = 0.0   # 迁移题增益

    def absolute_gain(self) -> float:
        return self.post_mean - self.pre_mean

    def normalized_gain(self) -> float:
        """Hake g = (post - pre) / (100 - pre) 归一化。"""
        denom = (1.0 - self.pre_mean)
        return self.absolute_gain() / denom if denom > 1e-6 else 0.0

    def effect_size(self) -> float:
        """Cohen's d 类（合并 SD）。"""
        pooled = math.sqrt((self.pre_sd ** 2 + self.post_sd ** 2) / 2)
        return self.absolute_gain() / pooled if pooled > 1e-6 else 0.0

    def attributable(self, control_gain: float | None) -> bool:
        """有对照时，系统增益须显著高于对照，方可归因（V2.2 §11.4）。"""
        if control_gain is None:
            return False  # 无对照 → 不直接解释为系统造成
        return self.absolute_gain() > control_gain
