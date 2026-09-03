"""端到端演示入口：一键运行闭环 + 实验 + 验收 + Baseline 对比。

运行：python3 run_demo.py
"""
from __future__ import annotations

from mvp.closed_loop import run_closed_loop
from experiments.core import run_all_experiments
from acceptance.metrics import run_acceptance
from baselines.compare import run_baseline_comparison, comparison_table


def main() -> None:
    print("=" * 60)
    print("高中语文学习评价与认知诊断系统 — 端到端演示")
    print("=" * 60)

    print("\n[1/4] MVP 最小闭环（合成学生）")
    print("-" * 60)
    rep = run_closed_loop()
    print(rep.summary())

    print("\n[2/4] 核心实验验证（四组）")
    print("-" * 60)
    print(run_all_experiments().summary())

    print("\n[3/4] Baseline A–E 对比")
    print("-" * 60)
    rows = run_baseline_comparison(n_students=15)
    print(comparison_table(rows))

    print("\n[4/4] 五项验收指标")
    print("-" * 60)
    acc = run_acceptance(n_students=10)
    print(acc.summary())

    print("\n" + "=" * 60)
    print("演示完成。")
    print("说明：以上为合成数据演示，验证链路正确性与指标可计算性；")
    print("真实阈值须大样本实证（V2.2 §5.1），需真实被试团队（任务 #14/#29真实版/#30真实版）。")
    print("=" * 60)


if __name__ == "__main__":
    main()
