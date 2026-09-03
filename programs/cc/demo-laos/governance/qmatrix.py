"""Q 矩阵治理与误标检测（V2.2 §31.2）。

- inter_rater_kappa：Cohen's κ，<0.6 退回重标。
- QMatrixValidator：基于残差的 Q 矩阵验证（GDI 思路）——
  衡量"某题若归到某技能，能解释多少作答变异"。残差高的题→疑似误标。
"""
from __future__ import annotations
import math


def inter_rater_kappa(r1: list[int], r2: list[int], categories: list[int]) -> float:
    """Cohen's κ。r1/r2 同长度，值为 category id。"""
    n = len(r1)
    if n == 0:
        return 0.0
    obs_agree = sum(1 for a, b in zip(r1, r2) if a == b) / n
    # 期望一致率
    p1 = {c: r1.count(c) / n for c in categories}
    p2 = {c: r2.count(c) / n for c in categories}
    exp_agree = sum(p1[c] * p2[c] for c in categories)
    if exp_agree >= 1.0:
        return 1.0
    return (obs_agree - exp_agree) / (1.0 - exp_agree)


class QMatrixValidator:
    """基于残差的 Q 矩阵验证（GDI/stepwise 思路）。

    q_matrix: {item_id: {skill_id: weight}}
    responses: {student_id: {item_id: 0/1}}
    对每题，计算其所属技能组对作答的预测力（边际），残差高 → 疑似误标。
    """

    def __init__(self, q_matrix: dict[str, dict[str, float]]) -> None:
        self.q = q_matrix

    def _item_skill_pvals(self, item_id: str, responses: dict) -> tuple[float, int]:
        """该题作答正确率 + 样本量。"""
        vals = [r.get(item_id) for r in responses.values() if item_id in r]
        if not vals:
            return 0.5, 0
        return sum(vals) / len(vals), len(vals)

    def residual_flags(self, responses: dict) -> dict[str, float]:
        """返回每题残差偏离度（越高越疑似误标）。

        简化 GDI：题的正确率与"同技能其他题平均正确率"的偏差。
        偏差大说明该题与其 Q 标注的技能不一致。
        """
        # 每技能平均正确率
        skill_rates: dict[str, list[float]] = {}
        item_rate: dict[str, float] = {}
        for iid in self.q:
            r, n = self._item_skill_pvals(iid, responses)
            item_rate[iid] = r
            for sk in self.q[iid]:
                skill_rates.setdefault(sk, []).append(r)

        skill_avg = {sk: (sum(v) / len(v)) if v else 0.5 for sk, v in skill_rates.items()}
        flags: dict[str, float] = {}
        for iid, skills in self.q.items():
            expected = sum(skill_avg[sk] for sk in skills) / max(len(skills), 1)
            flags[iid] = abs(item_rate.get(iid, 0.5) - expected)
        return flags

    def suspect_items(self, responses: dict, threshold: float = 0.25) -> list[str]:
        flags = self.residual_flags(responses)
        return [iid for iid, f in flags.items() if f >= threshold]
