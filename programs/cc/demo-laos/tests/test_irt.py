"""IRT 测试。

运行：python3 tests/test_irt.py
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from irt import IRT, TwoPL


def test_irt_recovers_theta():
    # 30 题，难度分散在 [-2,2]，区分度 1；真实 θ=1.0
    import random
    random.seed(7)
    bs = [-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0]
    items = [TwoPL(f"I{i:02d}", a=1.2, b=bs[i % len(bs)]) for i in range(30)]
    irt = IRT(items)
    theta_true = 1.0
    responses = {}
    for it in items:
        p = it.p_correct(theta_true)
        responses[it.id] = 1 if random.random() < p else 0
    theta_hat, se = irt.estimate_theta(responses)
    # 分散难度下 MLE 更稳；估计应方向正确且在容差内
    assert abs(theta_hat - theta_true) < 0.9, (theta_hat, se)
    assert se > 0
    print("PASS test_irt_recovers_theta", round(theta_hat, 3), "se", round(se, 3))


def test_irt_info_peaks_at_difficulty():
    it = TwoPL("X", a=1.5, b=0.5)
    # 信息量在 θ=b 处最大
    info_at_b = it.info(0.5)
    assert it.info(-1.0) < info_at_b
    assert it.info(2.0) < info_at_b
    print("PASS test_irt_info_peaks_at_difficulty", round(info_at_b, 3))


if __name__ == "__main__":
    test_irt_recovers_theta()
    test_irt_info_peaks_at_difficulty()
    print("\nAll IRT tests passed.")
