"""核心实验验证体系测试（任务 #28）。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.core import (
    auc, brier, f1, MetricBundle,
    experiment_diagnostic_validity, experiment_assessment_efficiency,
    experiment_learning_gain, experiment_external_validity,
    run_all_experiments,
)


def test_metrics():
    # 完美分离 → AUC=1
    assert abs(auc([0.9, 0.8, 0.1, 0.2], [1, 1, 0, 0]) - 1.0) < 1e-9
    # Brier: ((0.5-0)^2 + (0.5-1)^2)/2 = 0.25
    assert abs(brier([0.5, 0.5], [0, 1]) - 0.25) < 1e-9
    # F1
    assert f1([0.6, 0.4, 0.7], [1, 0, 1]) > 0
    print("PASS test_metrics")


def test_diagnostic_validity_external_required():
    r = experiment_diagnostic_validity()
    # 外部锚题必须独立计算，不能与训练题同源混用
    assert r.n_anchor > 0 and r.n_train > 0
    # 两个指标集都应产出
    assert 0.0 <= r.loo.auc <= 1.0
    assert 0.0 <= r.external_anchor.auc <= 1.0
    print("PASS test_diagnostic_validity",
          "LOO AUC=", r.loo.auc, "Anchor AUC=", r.external_anchor.auc)


def test_efficiency_system_beats_baseline():
    r = experiment_assessment_efficiency(target_auc=0.80)
    # 系统题量应 < IRT 基线题量（饱和更快）
    assert r.n_to_precision["E_system"] < r.n_to_precision["C_IRT"], \
        f"E 题量 {r.n_to_precision['E_system']} 应 < C {r.n_to_precision['C_IRT']}"
    assert r.reduction_pct > 0
    print("PASS test_efficiency", r.n_to_precision,
          "reduction=", r.reduction_pct, "%")


def test_learning_gain_attribution():
    r = experiment_learning_gain()
    # Treatment 增益 > Control → 可归因
    assert r.treatment_gain > r.control_gain
    assert r.attributable
    print("PASS test_learning_gain",
          "T=", r.treatment_gain, "C=", r.control_gain, "attr=", r.attributable)


def test_external_validity_needs_external():
    r = experiment_external_validity()
    # 同源率不应单独作为确认依据
    assert r.homologous_rate != r.external_rate  # 两者分离计算
    # confirmed 须由外部非同源率决定
    assert r.confirmed == (r.external_rate >= 0.6)
    print("PASS test_external_validity",
          "homo=", r.homologous_rate, "ext=", r.external_rate, "conf=", r.confirmed)


def test_full_report():
    rep = run_all_experiments()
    s = rep.summary()
    assert "[1]" in s and "[2]" in s and "[3]" in s and "[4]" in s
    print("\n" + s)


if __name__ == "__main__":
    test_metrics()
    test_diagnostic_validity_external_required()
    test_efficiency_system_beats_baseline()
    test_learning_gain_attribution()
    test_external_validity_needs_external()
    test_full_report()
    print("\nAll experiments tests passed.")
