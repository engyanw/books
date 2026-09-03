"""融合测试：DINA + IRT + 遗忘先验融合，含冲突→证据不足。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas.evidence import Evidence, EvidenceLevel, EvidenceSource
from schemas.item import Item, QMatrixEntry, ItemType, AuditStatus
from schemas.state import StateStatus
from repository import ItemRepository, EvidenceRepository, StateRepository
from assessment import AssessmentEngine
from irt.model import TwoPL
from fusion.updater import FusionUpdater


def _make_item(item_id, tags, a=1.2, b=0.0):
    it = Item(id=item_id, version="V3", source="t", text="t", question="q",
              answer="A", knowledge_tags=tags, q_matrix=[
                  QMatrixEntry(knowledge=k, cognitive="UNDERSTAND") for k in tags],
              irt_applicable=True, item_type=ItemType.OBJECTIVE,
              audit_status=AuditStatus.APPROVED)
    # 同时作为 IRT 题目参数（区分度/难度）
    return it, TwoPL(item_id, a=a, b=b)


def _ev(eid, item, score):
    return Evidence(id=eid, student_id="S1", item_id=item, item_version="V3",
                    score=score, source=EvidenceSource.DIRECT_ANSWER,
                    evidence_level=EvidenceLevel.C)


def test_fusion_combines_sources():
    item_repo = ItemRepository()
    irt_items = []
    for iid in ["I1", "I2", "I3", "I4"]:
        it, tp = _make_item(iid, ["K-WW-FUNC-001"])
        item_repo.put_item(it)
        irt_items.append(tp)

    ev_repo = EvidenceRepository()
    for e in [_ev("E1","I1",1.0), _ev("E2","I2",1.0),
              _ev("E3","I3",1.0), _ev("E4","I4",0.0)]:
        ev_repo.ingest(e)

    state_repo = StateRepository()
    engine = AssessmentEngine(state_repo, ev_repo,
                               updater=FusionUpdater(item_repo, irt_items))
    state = engine.update_state("S1","K-WW-FUNC-001","1.0","classical_reading",
                                ev_repo.by_student("S1"))
    assert "dina" in state.fusion.model_contributions
    assert "irt" in state.fusion.model_contributions
    assert "forgetting_prior" in state.fusion.model_contributions
    assert abs(sum(state.fusion.model_contributions.values()) - 1.0) < 1e-6
    assert state.fusion.effective_n > 0
    assert not state.fusion.is_multimodal
    print("PASS test_fusion_combines_sources",
          {k: round(v,2) for k,v in state.fusion.model_contributions.items()},
          "mastery", round(state.core.mastery,3))


def test_fusion_conflict_marks_insufficient():
    # DINA 证据全对（高 mastery），IRT 题目但作答全错 → 两者冲突
    item_repo = ItemRepository()
    irt_items = []
    for iid in ["I1", "I2", "I3"]:
        it, tp = _make_item(iid, ["K-WW-FUNC-001"], a=1.2, b=0.0)
        item_repo.put_item(it)
        irt_items.append(tp)

    ev_repo = EvidenceRepository()
    # DINA 视角：3 题全对 → 高 mastery
    # IRT 视角：同样的题全对 → θ 高 → p_irt 高 → 实际不冲突。
    # 要制造冲突：让 DINA 节点题全对，但另有一批 IRT 题全错。
    for iid in ["I1","I2","I3"]:
        ev_repo.ingest(_ev(f"E_{iid}", iid, 1.0))
    # IRT-only 题（不在该节点）全错 → θ 低
    for iid2, b in [("IX1",0.0),("IX2",0.0)]:
        it, tp = _make_item(iid2, ["K-OTHER"], a=1.2, b=b)
        item_repo.put_item(it)
        irt_items.append(tp)
        ev_repo.ingest(_ev(f"E_{iid2}", iid2, 0.0))

    state_repo = StateRepository()
    engine = AssessmentEngine(state_repo, ev_repo,
                               updater=FusionUpdater(item_repo, irt_items))
    state = engine.update_state("S1","K-WW-FUNC-001","1.0","classical_reading",
                                ev_repo.by_student("S1"))
    # DINA 高、IRT 低 → 冲突
    assert state.fusion.is_multimodal, state.fusion
    assert state.status == StateStatus.INSUFFICIENT_EVIDENCE
    print("PASS test_fusion_conflict_marks_insufficient",
          {k: round(v,2) for k,v in state.fusion.model_contributions.items()},
          "multimodal", state.fusion.is_multimodal)


if __name__ == "__main__":
    test_fusion_combines_sources()
    test_fusion_conflict_marks_insufficient()
    print("\nAll fusion tests passed.")
