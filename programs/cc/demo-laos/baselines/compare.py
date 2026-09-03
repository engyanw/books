"""Baseline A–E 对比运行器（docs/02 §3/§5）。

同一批学生/题目上运行全部基线，唯一变量是方法。产出对比表：
    方法 | N | AUC | F1 | Brier
留一/外部锚定（docs/02 §3.2）：诊断有效性不得用训练题自证——
本运行器对每学生用其作答估计掌握度，再与潜在真值比（代理外部锚定）。
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass

from baselines.core import ALL_BASELINES, Baseline
from experiments.core import auc, f1, brier, MetricBundle
from mvp.closed_loop import build_item_bank, make_student, simulate_response, NODES


@dataclass
class BaselineRow:
    name: str
    n: int
    metrics: MetricBundle

    def as_row(self) -> str:
        m = self.metrics
        return f"{self.name:<12} | N={self.n:<4} | AUC={m.auc} F1={m.f1} Brier={m.brier}"


def run_baseline_comparison(n_students: int = 30, seed: int = 7) -> list[BaselineRow]:
    rng = random.Random(seed)
    item_repo, irt_items, all_items = build_item_bank(seed)

    # 每学生固定题集（同题同被试，docs/02 §3.1）
    fixed_items = all_items[:20]

    rows: list[BaselineRow] = []
    for bl in ALL_BASELINES:  # type: ignore
        preds: list[float] = []
        labels: list[int] = []
        n_eval = 0
        for i in range(n_students):
            s = make_student(seed=rng.randint(0, 10**6))
            ev_list = []
            for it in fixed_items:
                x = simulate_response(s, it, rng)
                from schemas.evidence import Evidence, EvidenceLevel, EvidenceSource
                ev_list.append(Evidence(
                    id=f"BL-{bl.name}-{i}-{it.id}",
                    student_id=s.student_id, item_id=it.id,
                    item_version=it.version, score=float(x),
                    source=EvidenceSource.DIRECT_ANSWER,
                    evidence_level=EvidenceLevel.C,
                ))
            est = bl.estimate(ev_list, item_repo, irt_items)
            for nd, p in est.items():
                if nd in s.mastery:
                    preds.append(p)
                    labels.append(1 if s.mastery[nd] >= 0.5 else 0)
                    n_eval += 1
        rows.append(BaselineRow(bl.name, n_eval,
                                 MetricBundle.from_scores(preds, labels)))
    return rows


def comparison_table(rows: list[BaselineRow]) -> str:
    lines = ["=== Baseline A–E 对比（同题同被试，合成数据）==="]
    lines.append(f"{'方法':<12} | {'N':<6} | {'AUC':<7} {'F1':<7} {'Brier':<7}")
    lines.append("-" * 50)
    for r in rows:
        m = r.metrics
        lines.append(f"{r.name:<12} | N={r.n:<4} | {m.auc:<7} {m.f1:<7} {m.brier:<7}")
    return "\n".join(lines)


if __name__ == "__main__":
    rows = run_baseline_comparison(n_students=20)
    print(comparison_table(rows))
