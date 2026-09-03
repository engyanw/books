"""学习决策 + AI Tutor 权限边界测试。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas.state import StudentCognitiveState, StateStatus, CoreState, UncertaintyState, DiagnosticState
from learning.decision import (
    LearningDecisionEngine, ActionType, CircuitBreaker, InterventionLevel,
)
from tutor.agent import TutorAgent, AgentPermissionError


def _state(mastery, transfer=0.3, confidence=0.5):
    return StudentCognitiveState(
        student_id="S1", node_id="K-WW-FUNC-001", node_version="1.0",
        domain="classical_reading", status=StateStatus.OK,
        core=CoreState(mastery=mastery, application=mastery, transfer=transfer),
        uncertainty=UncertaintyState(confidence=confidence, posterior_variance=0.2),
        diagnostic=DiagnosticState(misconception="语境辨析不足"),
    )


def test_decision_prefers_low_mastery_node():
    eng = LearningDecisionEngine(explore_c=0.0)  # 关探索看贪心
    state = _state(mastery=0.3)  # 低 mastery → 大 gap
    act = eng.decide(state, [ActionType.EXPLAIN, ActionType.TRANSFER_DRILL],
                     priority={"K-WW-FUNC-001": 0.8})
    assert act.node_id == "K-WW-FUNC-001"
    assert act.expected_gain > 0
    print("PASS test_decision_prefers_low_mastery_node", act.action_type.value,
          round(act.utility, 3))


def test_exploration_pulls_untried_action():
    eng = LearningDecisionEngine(explore_c=2.0)
    state = _state(mastery=0.9)  # 高 mastery → base 小，探索主导
    # 已多次试 EXPLAIN，从未试 TRANSFER_DRILL → 后者探索项大
    for _ in range(10):
        eng.record_outcome(state.node_id, ActionType.EXPLAIN, 0.05)
    act = eng.decide(state, [ActionType.EXPLAIN, ActionType.TRANSFER_DRILL],
                     priority={"K-WW-FUNC-001": 0.5})
    assert act.action_type == ActionType.TRANSFER_DRILL, act.action_type
    print("PASS test_exploration_pulls_untried_action", act.action_type.value)


def test_circuit_breaker_levels():
    cb = CircuitBreaker()
    # 正常
    assert cb.evaluate(confidence=0.8, independent_failures=0,
                       error_consistency=0.2, recent_gain=0.5) == InterventionLevel.NORMAL
    # 全部触发 → 三级（教师介入）
    assert cb.evaluate(confidence=0.2, independent_failures=3,
                       error_consistency=0.8, recent_gain=0.01) == InterventionLevel.THREE
    print("PASS test_circuit_breaker_levels")


def test_agent_permission_boundary():
    agent = TutorAgent()
    # 越权写应抛 AgentPermissionError
    for fn in ("update_mastery", "declare_mastered", "update_threshold"):
        raised = False
        try:
            getattr(agent, fn)()
        except AgentPermissionError:
            raised = True
        assert raised, fn
    # 但只读与生成动作可用
    s = _state(0.3)
    assert "mastery=0.30" in agent.explain_gap(s)
    assert "基础概念" in agent.generate_action(s)
    print("PASS test_agent_permission_boundary")


if __name__ == "__main__":
    test_decision_prefers_low_mastery_node()
    test_exploration_pulls_untried_action()
    test_circuit_breaker_levels()
    test_agent_permission_boundary()
    print("\nAll learning+tutor tests passed.")
