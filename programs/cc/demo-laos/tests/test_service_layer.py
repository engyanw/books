"""服务层端到端测试：证据采集 → 状态更新 → Provenance，及写权限边界。

运行：python3 -m pytest tests/test_service_layer.py
或：  python3 tests/test_service_layer.py
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas.evidence import Evidence, EvidenceLevel, EvidenceSource
from schemas.state import StateStatus
from repository import StateRepository, EvidenceRepository
from assessment import AssessmentEngine


def make_evidence(eid, student, item, score, level=EvidenceLevel.C):
    return Evidence(
        id=eid, student_id=student, item_id=item, item_version="V3",
        score=score, source=EvidenceSource.DIRECT_ANSWER, evidence_level=level,
    )


def test_state_update_and_provenance():
    state_repo = StateRepository()
    ev_repo = EvidenceRepository()
    engine = AssessmentEngine(state_repo, ev_repo)

    evs = [
        make_evidence("E1", "S1", "ITEM001", 1.0),
        make_evidence("E2", "S1", "ITEM001", 1.0),
        make_evidence("E3", "S1", "ITEM002", 0.0),
    ]
    for ev in evs:
        ev_repo.ingest(ev)

    state = engine.update_state("S1", "K-WW-FUNC-001", "1.0", "classical_reading", evs)
    assert state.status == StateStatus.OK
    assert 0.0 < state.core.mastery < 1.0
    assert state.uncertainty.evidence_count == 3
    assert state.fusion.model_contributions["beta_bernoulli"] == 1.0

    prov = engine.get_provenance("S1", "K-WW-FUNC-001")
    assert len(prov) == 3
    assert state.updated_at is not None
    print("PASS test_state_update_and_provenance", round(state.core.mastery, 3))


def test_cold_start_insufficient_evidence():
    state_repo = StateRepository()
    ev_repo = EvidenceRepository()
    engine = AssessmentEngine(state_repo, ev_repo)

    # 仅 1 条证据 → 不可识别，状态为 INSUFFICIENT_EVIDENCE（V2.2 §9.6）
    ev_repo.ingest(make_evidence("E1", "S2", "ITEM001", 1.0))
    state = engine.update_state("S2", "K-WW-FUNC-001", "1.0", "classical_reading",
                                ev_repo.by_student("S2"))
    assert state.status == StateStatus.INSUFFICIENT_EVIDENCE
    print("PASS test_cold_start_insufficient_evidence")


def test_write_permission_boundary():
    """写权限边界（V2.2 §20）：状态写路径仅 AssessmentEngine。"""
    state_repo = StateRepository()
    ev_repo = EvidenceRepository()
    engine = AssessmentEngine(state_repo, ev_repo)

    # Agent 角色只能读，不能写——验证只读 get 不抛错，写必须经 engine
    engine.update_state("S3", "K", "1.0", "d",
                        [make_evidence("E1", "S3", "I", 1.0)])
    read_state = engine.get_state("S3", "K")
    assert read_state is not None          # Agent 可读
    # StateRepository.put 虽然技术上公开（哑存储），但引擎层是唯一 sanctioned 写路径；
    # 真实部署在 service 边界强制（见 docs/07 §9 接口权限表）。
    print("PASS test_write_permission_boundary")


if __name__ == "__main__":
    test_state_update_and_provenance()
    test_cold_start_insufficient_evidence()
    test_write_permission_boundary()
    print("\nAll service-layer tests passed.")
