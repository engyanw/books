"""IRT 实现：2PL 能力估计（MLE）与题目参数校准（联合 MLE，小题集）。

2PL：P(X=1|θ) = σ(a(θ-b)) = 1/(1+exp(-a(θ-b)))

能力估计：给定题目参数 (a,b) 与作答，Newton-Raphson 求 MLE θ。
信息量：I(θ) = a² P(1-P)。
"""
from __future__ import annotations
import math


def _p_correct(theta: float, a: float, b: float) -> float:
    z = a * (theta - b)
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


class TwoPL:
    """单个 2PL 题目。"""

    def __init__(self, item_id: str, a: float, b: float) -> None:
        self.id = item_id
        self.a = a   # 区分度
        self.b = b   # 难度

    def p_correct(self, theta: float) -> float:
        return _p_correct(theta, self.a, self.b)

    def info(self, theta: float) -> float:
        p = self.p_correct(theta)
        return self.a * self.a * p * (1 - p)


class IRT:
    """IRT 能力估计与校准。MVP：单维 θ（领域能力由多组 IRT 分别估计）。"""

    def __init__(self, items: list[TwoPL]) -> None:
        self.items = {it.id: it for it in items}

    def estimate_theta(
        self, responses: dict[str, int], theta0: float = 0.0,
        max_iter: int = 50, tol: float = 1e-4,
    ) -> tuple[float, float]:
        """MLE 估计 θ，返回 (theta, se)。se=1/sqrt(Fisher 信息)。"""
        theta = theta0
        for _ in range(max_iter):
            # 一阶导 d logL/dθ 与 信息量
            score_deriv = 0.0
            info = 0.0
            for j, x in responses.items():
                if j not in self.items:
                    continue
                it = self.items[j]
                p = it.p_correct(theta)
                p = min(max(p, 1e-6), 1 - 1e-6)
                # d/dθ logP = a*(x - p)
                score_deriv += it.a * (x - p)
                info += it.info(theta)
            if info <= 0:
                break
            delta = score_deriv / info
            # 阻尼，防发散
            delta = max(-1.0, min(1.0, delta))
            theta += delta
            theta = max(-4.0, min(4.0, theta))
            if abs(delta) < tol:
                break
        se = 1.0 / math.sqrt(max(info, 1e-6)) if info > 0 else 99.0
        return theta, se

    def total_info(self, theta: float, item_ids: list[str] | None = None) -> float:
        ids = item_ids or list(self.items)
        return sum(self.items[j].info(theta) for j in ids if j in self.items)
