"""治理接入写路径测试（V2.2 §20/§35 风险8 集成）。

引擎每次写/读/导出都落审计链，导出给 LLM 前去标识化、假名化。
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas.evidence import Evidence, EvidenceLevel, EvidenceSource
from repository import StateRepository, EvidenceRepository
from assessment import AssessmentEngine
from governance.privacy import PrivacyGuard, AuditChain


def _ev(eid, sid, score=1.0):
    return Evidence(id=eid, student_id=sid, item_id="I1", item_version="v1",
                    score=score, source=EvidenceSource.DIRECT_ANSWER,
                    evidence_level=EvidenceLevel.C)


def test_audited_writes_and_reads():
    pg = PrivacyGuard(AuditChain(), salt="z")
    engine = AssessmentEngine(StateRepository(), EvidenceRepository(),
                              governance=pg)
    engine.ingest_evidence(_ev("E1", "张三真名", 1.0))
    engine.update_state("张三真名", "K1", "v1", "d", [_ev("E2", "张三真名", 1.0),
                                                      _ev("E3", "张三真名", 1.0)])
    engine.get_state("张三真名", "K1")
    engine.get_provenance("张三真名", "K1")
    entries = engine.audit_entries()
    actions = [e.action for e in entries]
    assert "write_state" in actions and "read_state" in actions
    # 审计链不含原始可识别 student_id（假名化）
    assert all("张三真名" not in (e.student_id or "") for e in entries)
    assert all(e.student_id.startswith("p:") for e in entries)
    # 链完整
    assert pg.audit.verify()
    print("PASS test_audited_writes_and_reads", f"n={len(entries)}")


def test_export_deidentified():
    pg = PrivacyGuard(AuditChain(), salt="z")
    engine = AssessmentEngine(StateRepository(), EvidenceRepository(),
                              governance=pg)
    engine.update_state("李四", "K1", "v1", "d",
                         [_ev("E1", "李四", 1.0), _ev("E2", "李四", 1.0),
                          _ev("E3", "李四", 0.0)])
    snap = engine.export_for_llm("李四", "K1")
    assert snap is not None
    # 导出快照假名化 + 去标识化，不含原始姓名
    assert str(snap["student"]).startswith("h:") or str(snap["student"]).startswith("p:")
    assert "李四" not in str(snap)
    # 导出动作已审计
    assert any(e.action == "export" for e in engine.audit_entries())
    print("PASS test_export_deidentified", snap["student"][:8])


def test_no_governance_backward_compatible():
    """未接入治理时行为不变（向后兼容）。"""
    engine = AssessmentEngine(StateRepository(), EvidenceRepository())
    engine.update_state("S1", "K1", "v1", "d",
                        [_ev("E1", "S1", 1.0), _ev("E2", "S1", 1.0),
                         _ev("E3", "S1", 0.0)])
    assert engine.audit_entries() == []
    print("PASS test_no_governance_backward_compatible")


if __name__ == "__main__":
    test_audited_writes_and_reads()
    test_export_deidentified()
    test_no_governance_backward_compatible()
    print("\nAll governed-engine tests passed.")
