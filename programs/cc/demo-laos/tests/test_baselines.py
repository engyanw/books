"""Baseline A–E 对比框架测试（任务 #2 实现层）。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from baselines.core import ALL_BASELINES, BaselineA, BaselineB, BaselineD, BaselineE
from baselines.compare import run_baseline_comparison, comparison_table


def test_each_baseline_produces_mastery():
    """每条基线输出 dict[node_id, mastery_prob]，值在 [0,1]。"""
    from mvp.closed_loop import build_item_bank, make_student, simulate_response
    from schemas.evidence import Evidence, EvidenceLevel, EvidenceSource
    import random
    rng = random.Random(5)
    item_repo, irt_items, all_items = build_item_bank(42)
    s = make_student(seed=9)
    evs = []
    for it in all_items[:20]:
        x = simulate_response(s, it, rng)
        evs.append(Evidence(id=f"T-{it.id}", student_id=s.student_id,
                            item_id=it.id, item_version=it.version,
                            score=float(x),
                            source=EvidenceSource.DIRECT_ANSWER,
                            evidence_level=EvidenceLevel.C))
    for bl in ALL_BASELINES:
        est = bl.estimate(evs, item_repo, irt_items)
        assert est, f"{bl.name} 应有输出"
        for v in est.values():
            assert 0.0 <= v <= 1.0, f"{bl.name} 输出越界 {v}"
    print("PASS test_each_baseline_produces_mastery")


def test_granularity_monotone():
    """B（知识粒度）应优于 A（无粒度），D/E 应不劣于 A（docs/02 §6 方向）。"""
    rows = run_baseline_comparison(n_students=15, seed=3)
    by = {r.name: r.metrics for r in rows}
    # B 的 AUC 优于 A（知识标签带来诊断力）
    assert by["B_tagged_accuracy"].auc > by["A_accuracy"].auc, \
        "B 应优于 A"
    # D/E 的 F1 不劣于 A
    assert by["D_dina"].f1 >= by["A_accuracy"].f1
    assert by["E_system"].f1 >= by["A_accuracy"].f1
    print("PASS test_granularity_monotone")
    print("  A AUC=", by["A_accuracy"].auc, "B AUC=", by["B_tagged_accuracy"].auc)
    print("  A F1=", by["A_accuracy"].f1, "D F1=", by["D_dina"].f1, "E F1=", by["E_system"].f1)


def test_table_renders():
    rows = run_baseline_comparison(n_students=10, seed=2)
    t = comparison_table(rows)
    for name in ("A_accuracy", "B_tagged_accuracy", "C_irt",
                 "D_dina", "E_system"):
        assert name in t
    print("PASS test_table_renders")


if __name__ == "__main__":
    test_each_baseline_produces_mastery()
    test_granularity_monotone()
    test_table_renders()
    print("\nAll baseline tests passed.")
