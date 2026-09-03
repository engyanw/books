"""自适应 + 探针测试。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas.item import Item, ItemType, AuditStatus
from schemas.state import StudentCognitiveState, StateStatus, CoreState, UncertaintyState
from adaptive.engine import AdaptiveEngine, AdaptiveConstraints
from adaptive.probe import ProbeEngine, ProbeLevel, Probe


def _make_item(iid, tags, b=0.0):
    return Item(id=iid, version="V3", source="t", text="t", question="q",
                answer="A", knowledge_tags=tags,
                irt_applicable=True, item_type=ItemType.OBJECTIVE,
                audit_status=AuditStatus.APPROVED), b


def test_adaptive_selects_high_info_item():
    from repository import ItemRepository
    from irt.model import TwoPL
    item_repo = ItemRepository()
    irt_items = []
    # 两题：高区分度高信息 vs 低信息
    it_hi, b_hi = _make_item("I_HI", ["K1"], b=0.0)
    it_lo, b_lo = _make_item("I_LO", ["K1"], b=2.0)
    item_repo.put_item(it_hi); item_repo.put_item(it_lo)
    irt_items = [TwoPL("I_HI", a=1.5, b=0.0), TwoPL("I_LO", a=0.5, b=2.0)]

    eng = AdaptiveEngine(item_repo, irt_items)
    state = StudentCognitiveState(
        student_id="S1", node_id="K1", node_version="1.0", domain="d",
        status=StateStatus.OK,
        core=CoreState(mastery=0.5, application=0.5, transfer=0.5),
        uncertainty=UncertaintyState(posterior_variance=0.2),
    )
    chosen = eng.select_next(state, [it_hi, it_lo], set(), 0.0,
                              AdaptiveConstraints())
    assert chosen.id == "I_HI", chosen.id
    print("PASS test_adaptive_selects_high_info_item", chosen.id)


def test_stopping_when_variance_low():
    from repository import ItemRepository
    from irt.model import TwoPL
    item_repo = ItemRepository()
    eng = AdaptiveEngine(item_repo, [TwoPL("I1", 1.0, 0.0)])
    it, _ = _make_item("I1", ["K1"])
    state = StudentCognitiveState(
        student_id="S1", node_id="K1", node_version="1.0", domain="d",
        status=StateStatus.OK,
        core=CoreState(mastery=0.5),
        uncertainty=UncertaintyState(posterior_variance=0.01),  # 低于 τ=0.05
    )
    seen = [f"I{i}" for i in range(10)]  # 已超 min_length
    assert eng.should_stop(state, seen, [it], 0.0, AdaptiveConstraints())
    print("PASS test_stopping_when_variance_low")


def test_probe_ladder():
    pe = ProbeEngine()
    pe.put(Probe("P_R", "K1", ProbeLevel.RECALL, "r?", "e"))
    pe.put(Probe("P_D", "K1", ProbeLevel.DISCRIMINATION, "d?", "e"))
    pe.put(Probe("P_E", "K1", ProbeLevel.EXPLANATION, "e?", "e"))

    # 不知道
    key, label = pe.interpret({ProbeLevel.RECALL: False,
                               ProbeLevel.DISCRIMINATION: None,
                               ProbeLevel.EXPLANATION: None})
    assert key == "unknown", label
    # 知道但不会用
    key, _ = pe.interpret({ProbeLevel.RECALL: True,
                           ProbeLevel.DISCRIMINATION: False,
                           ProbeLevel.EXPLANATION: None})
    assert key == "know_cant_apply"
    # 会用但不稳定
    key, _ = pe.interpret({ProbeLevel.RECALL: True,
                           ProbeLevel.DISCRIMINATION: True,
                           ProbeLevel.EXPLANATION: False})
    assert key == "unstable"
    # 稳定掌握
    key, _ = pe.interpret({ProbeLevel.RECALL: True,
                           ProbeLevel.DISCRIMINATION: True,
                           ProbeLevel.EXPLANATION: True})
    assert key == "stable"

    # 探针 → 证据为 level D
    ev = pe.to_evidence(pe._probes["P_R"], "S1", True)
    assert ev.evidence_level.value == "D"
    assert ev.source.value == "probe"
    print("PASS test_probe_ladder")


if __name__ == "__main__":
    test_adaptive_selects_high_info_item()
    test_stopping_when_variance_low()
    test_probe_ladder()
    print("\nAll adaptive tests passed.")
