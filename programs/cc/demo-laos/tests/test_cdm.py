"""CDM（DINA/GDINA）测试。

运行：python3 tests/test_cdm.py
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas.evidence import Evidence, EvidenceLevel, EvidenceSource
from schemas.item import Item, QMatrixEntry, ItemType, AuditStatus
from repository import ItemRepository, EvidenceRepository, StateRepository
from assessment import AssessmentEngine
from cdm.updater import CdmUpdater
from cdm import DINA


def test_dina_posterior_recovers_mastery():
    # 2 技能，3 题；学生掌握了 K1，未掌握 K2
    skills = ["K1", "K2"]
    items = [
        {"id": "I1", "required": [0], "slip": 0.1, "guess": 0.2},   # 仅 K1
        {"id": "I2", "required": [0], "slip": 0.1, "guess": 0.2},
        {"id": "I3", "required": [1], "slip": 0.1, "guess": 0.2},   # 仅 K2
    ]
    dina = DINA(skills, items, prior=0.5)
    # K1 掌握 → I1/I2 多数对；K2 未掌握 → I3 错
    resp = {"I1": 1, "I2": 1, "I3": 0}
    p = dina.posterior_mastery(resp)
    assert p["K1"] > 0.7, p
    assert p["K2"] < 0.3, p
    print("PASS test_dina_posterior_recovers_mastery", round(p["K1"], 3), round(p["K2"], 3))


def _make_item(item_id, knowledge_tags):
    return Item(
        id=item_id, version="V3", source="t", text="t", question="q",
        answer="A", knowledge_tags=knowledge_tags, q_matrix=[
            QMatrixEntry(knowledge=k, cognitive="UNDERSTAND") for k in knowledge_tags
        ], irt_applicable=True, item_type=ItemType.OBJECTIVE,
        audit_status=AuditStatus.APPROVED,
    )


def test_cdm_updater_via_engine():
    item_repo = ItemRepository()
    for iid, tags in [("I1", ["K-WW-FUNC-001"]),
                      ("I2", ["K-WW-FUNC-001"]),
                      ("I3", ["K-WW-FUNC-001"])]:
        item_repo.put_item(_make_item(iid, tags))

    ev_repo = EvidenceRepository()
    state_repo = StateRepository()
    engine = AssessmentEngine(state_repo, ev_repo, updater=CdmUpdater(item_repo))

    def ev(eid, item, score):
        return Evidence(id=eid, student_id="S1", item_id=item, item_version="V3",
                        score=score, source=EvidenceSource.DIRECT_ANSWER,
                        evidence_level=EvidenceLevel.C)
    for e in [ev("E1","I1",1.0), ev("E2","I2",1.0), ev("E3","I3",0.0)]:
        ev_repo.ingest(e)

    state = engine.update_state("S1","K-WW-FUNC-001","1.0","classical_reading",
                                ev_repo.by_student("S1"))
    assert state.fusion.model_contributions == {"dina": 1.0}
    assert 0.0 <= state.core.mastery <= 1.0
    assert state.uncertainty.effective_n == 3
    print("PASS test_cdm_updater_via_engine", round(state.core.mastery, 3))


if __name__ == "__main__":
    test_dina_posterior_recovers_mastery()
    test_cdm_updater_via_engine()
    print("\nAll CDM tests passed.")
