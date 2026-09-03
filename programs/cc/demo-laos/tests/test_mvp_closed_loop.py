"""MVP 最小闭环测试（任务 #29）。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mvp.closed_loop import ClosedLoop, run_closed_loop
from tutor.agent import AgentPermissionError


def test_closed_loop_runs_end_to_end():
    rep = run_closed_loop(seed=7)
    # 诊断阶段产生了证据
    assert rep.n_diagnostic_items > 0
    # 识别出 Top3 缺口
    assert len(rep.gap_nodes) == 3
    # 干预后至少一个缺口节点掌握度上升
    gains = [rep.post_mastery.get(n, 0) - rep.pre_mastery.get(n, 0)
             for n in rep.gap_nodes]
    assert max(gains) > 0, "干预应带来增益"
    print("PASS test_closed_loop_runs_end_to_end")
    print("  gaps:", rep.gap_nodes)
    print("  max gain:", round(max(gains), 2))


def test_write_isolation_in_loop():
    """闭环中 Agent 不得写状态（V2.2 §20）。"""
    cl = ClosedLoop(seed=42)
    student = cl.run.__self__  # noqa
    # 直接测 TutorAgent 越权保护
    agent = cl.tutor
    for forbidden in ("update_mastery", "declare_mastered", "update_threshold"):
        fn = getattr(agent, forbidden)
        try:
            fn("S7", "虚词辨析", 0.9)
        except AgentPermissionError:
            continue
        raise AssertionError(f"{forbidden} 应被禁止")
    print("PASS test_write_isolation_in_loop")


def test_transfer_uses_external_only():
    rep = run_closed_loop(seed=3)
    # 迁移结论由外部非同源材料决定
    assert rep.transfer_external_rate >= 0
    # confirmed 与外部迁移率一致（阈值 0.6）
    assert rep.transfer_confirmed == (rep.transfer_external_rate >= 0.6)
    print("PASS test_transfer_uses_external_only",
          "ext_rate=", round(rep.transfer_external_rate, 2))


if __name__ == "__main__":
    test_closed_loop_runs_end_to_end()
    test_write_isolation_in_loop()
    test_transfer_uses_external_only()
    print("\nAll MVP closed-loop tests passed.")
