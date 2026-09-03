"""迁移验证 + 保持/干预效果测试。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.transfer import (
    PrePostDesign, TransferTestItem, TransferValidator, TransferLevel,
)
from evaluation.retention import RetentionModel, InterventionEffect


def test_transfer_requires_external_material():
    v = TransferValidator()
    # 远迁移仅有同源题 → 不确认迁移
    items = [TransferTestItem("T1", TransferLevel.COMPREHENSIVE, True, 1.0)]
    res = v.validate(items)
    comp = [r for r in res if r.level == TransferLevel.COMPREHENSIVE][0]
    assert not v.is_transfer_confirmed(res), "同源题不应确认迁移"

    # 加入外部非同源远迁移题且达标 → 确认
    items.append(TransferTestItem("TX", TransferLevel.COMPREHENSIVE, False, 1.0))
    items.append(TransferTestItem("TY", TransferLevel.COMPREHENSIVE, False, 1.0))
    res2 = v.validate(items)
    assert v.is_transfer_confirmed(res2), "外部非同源达标应确认迁移"
    print("PASS test_transfer_requires_external_material")


def test_pre_post_gain():
    pp = PrePostDesign(
        pre=[TransferTestItem("P1", TransferLevel.RECALL, True, 0.0),
             TransferTestItem("P2", TransferLevel.RECALL, True, 1.0)],
        post=[TransferTestItem("Q1", TransferLevel.RECALL, False, 1.0),
              TransferTestItem("Q2", TransferLevel.RECALL, False, 1.0)],
    )
    assert pp.absolute_gain() == 0.5  # 0.5 → 1.0
    print("PASS test_pre_post_gain", round(pp.absolute_gain(), 2))


def test_retention_individualized():
    m = RetentionModel(group_lambda=0.05)
    # 一个学生遗忘快：多次观察 retained 低
    obs = [(1, 0.5), (7, 0.2), (30, 0.1)]
    lam = m.fit_individual(obs)
    assert lam > m.group_lambda, "个体 λ 应高于群体先验（遗忘更快）"
    assert m.retention(lam, 7) < m.retention(m.group_lambda, 7)
    print("PASS test_retention_individualized", round(lam, 4))


def test_intervention_effect_attribution():
    ie = InterventionEffect(pre_mean=0.4, post_mean=0.7, pre_sd=0.2, post_sd=0.2)
    assert abs(ie.absolute_gain() - 0.3) < 1e-6
    assert ie.effect_size() > 0
    # 无对照 → 不归因
    assert not ie.attributable(None)
    # 对照增益 0.1 < 0.3 → 可归因
    assert ie.attributable(0.1)
    # 对照增益 0.4 > 0.3 → 不可归因
    assert not ie.attributable(0.4)
    print("PASS test_intervention_effect_attribution",
          round(ie.effect_size(), 2))


if __name__ == "__main__":
    test_transfer_requires_external_material()
    test_pre_post_gain()
    test_retention_individualized()
    test_intervention_effect_attribution()
    print("\nAll evaluation tests passed.")
