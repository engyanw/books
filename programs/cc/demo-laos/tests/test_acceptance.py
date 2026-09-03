"""MVP 五项验收指标测试（任务 #30）。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from acceptance.metrics import run_acceptance


def test_all_five_computed():
    rep = run_acceptance(n_students=10)
    s = rep.summary()
    for tag in ["[1]", "[2]", "[3]", "[4]", "[5]", "总验收"]:
        assert tag in s
    # 各项字段非空
    assert rep.measurement_validity.test_retest_correlation is not None
    assert rep.diagnostic_validity.auc is not None
    assert rep.adaptive_efficiency.adaptive_items > 0
    assert rep.learning_effect.gain is not None
    assert rep.decision_quality.ai_gain is not None
    print("PASS test_all_five_computed")


def test_decision_quality_ai_beats_random():
    rep = run_acceptance(n_students=10)
    # 核心断言：AI 个性化优于随机练题（规划 §19.5）
    assert rep.decision_quality.ai_gain > rep.decision_quality.random_gain, \
        f"AI {rep.decision_quality.ai_gain} 应 > 随机 {rep.decision_quality.random_gain}"
    assert rep.decision_quality.passed
    print("PASS test_decision_quality_ai_beats_random",
          "AI=", rep.decision_quality.ai_gain,
          "Rnd=", rep.decision_quality.random_gain)


def test_adaptive_efficiency_fewer_items():
    rep = run_acceptance(n_students=10)
    # 自适应题量应 ≤ 固定题量，且精度不显著劣化
    assert rep.adaptive_efficiency.adaptive_items <= rep.adaptive_efficiency.fixed_items
    assert rep.adaptive_efficiency.adaptive_auc >= rep.adaptive_efficiency.fixed_auc - 0.1
    print("PASS test_adaptive_efficiency_fewer_items",
          "ada=", rep.adaptive_efficiency.adaptive_items,
          "fixed=", rep.adaptive_efficiency.fixed_items)


if __name__ == "__main__":
    test_all_five_computed()
    test_decision_quality_ai_beats_random()
    test_adaptive_efficiency_fewer_items()
    print("\nAll acceptance tests passed.")
