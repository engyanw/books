"""公平性 / DIF 检测 / subgroup 校准（任务 #26，V2.2 §35 风险7）。

- DIFDetector：简化 Mantel-Haenszel DIF 检测——
  在匹配能力（总分分层）后，两组在某题的正确率差异；|Δ| 大 → 疑似 DIF。
- SubgroupCalibration：监控子组预测准确率，偏差大 → 校准告警。
"""
from __future__ import annotations
import math
from dataclasses import dataclass


@dataclass
class DIFResult:
    item_id: str
    delta: float        # MH 类的组间差异，|Δ| 越大越疑似 DIF
    flag: bool          # 是否标记 DIF


class DIFDetector:
    """简化 Mantel-Haenszel DIF 检测。

    records: list of dict {
        student_id, group ('A'/'B' 等), item_id, correct (0/1), total_score (匹配用)
    }
    按 total_score 分层（分箱），同层内比较两组正确率，汇总加权差异。
    """

    def __init__(self, n_strata: int = 5) -> None:
        self.n_strata = n_strata

    def _stratify(self, score: float, lo: float, hi: float) -> int:
        if hi <= lo:
            return 0
        b = int((score - lo) / (hi - lo) * self.n_strata)
        return max(0, min(self.n_strata - 1, b))

    def detect(self, records: list[dict], groups: tuple[str, str] = ("A", "B")) -> list[DIFResult]:
        g1, g2 = groups
        items = sorted({r["item_id"] for r in records})
        scores = [r["total_score"] for r in records]
        lo, hi = min(scores), max(scores)

        # 分层内每题每组的 (correct_sum, n)
        res: list[DIFResult] = []
        for iid in items:
            # stratum -> group -> [correct_sum, n]
            strata: dict[int, dict[str, list[float]]] = {}
            for r in records:
                if r["item_id"] != iid:
                    continue
                grp = r["group"]
                if grp not in groups:
                    continue
                s = self._stratify(r["total_score"], lo, hi)
                strata.setdefault(s, {g1: [0.0, 0.0], g2: [0.0, 0.0]})
                strata[s][grp][0] += r["correct"]
                strata[s][grp][1] += 1.0

            # 加权汇总两组正确率差
            num = 0.0
            den = 0.0
            for s, gd in strata.items():
                n1, n2 = gd[g1][1], gd[g2][1]
                if n1 == 0 or n2 == 0:
                    continue
                p1 = gd[g1][0] / n1
                p2 = gd[g2][0] / n2
                w = n1 * n2 / (n1 + n2)
                num += w * (p1 - p2)
                den += w
            delta = num / den if den > 0 else 0.0
            res.append(DIFResult(iid, delta, abs(delta) >= 0.1))
        return res

    def flagged(self, results: list[DIFResult]) -> list[str]:
        return [r.item_id for r in results if r.flag]


class SubgroupCalibration:
    """子组校准监控（V2.2 §35 风险7）。

    预测正确率 vs 实际正确率，子组偏差超过阈值 → 告警。
    """

    def __init__(self, threshold: float = 0.1) -> None:
        self.threshold = threshold

    @dataclass
    class CalibEntry:
        group: str
        predicted: float
        actual: float
        bias: float
        alarm: bool

    def evaluate(self, records: list[dict]) -> list["SubgroupCalibration.CalibEntry"]:
        """records: {group, predicted (0-1), actual (0/1)}"""
        agg: dict[str, list[float]] = {}
        for r in records:
            agg.setdefault(r["group"], [[], []])
            agg[r["group"]][0].append(r["predicted"])
            agg[r["group"]][1].append(float(r["actual"]))
        out: list[SubgroupCalibration.CalibEntry] = []
        for g, (preds, acts) in agg.items():
            p = sum(preds) / len(preds)
            a = sum(acts) / len(acts)
            bias = p - a
            out.append(self.CalibEntry(g, p, a, bias, abs(bias) >= self.threshold))
        return out
