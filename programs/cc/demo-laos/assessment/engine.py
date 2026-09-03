"""Assessment Engine 实现。

编排：Evidence → 后验更新 → Student State → 不确定性。
状态的写权限独占于此（V2.2 §20）。

后验更新策略可插拔（StateUpdater）：
- 默认 BetaBernoulliUpdater（简单贝塔-伯努利，使闭环可跑通）
- #16/#17/#18 完成后替换为 DINA/IRT + 分层贝叶斯融合
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Protocol

from schemas.evidence import Evidence, EvidenceLevel
from schemas.state import (
    StudentCognitiveState, StateStatus, CoreState, UncertaintyState, FusionOutput,
)
from repository import StateRepository, EvidenceRepository
from governance.privacy import PrivacyGuard


class StateUpdater(Protocol):
    """后验更新策略接口。#16/#17/#18 提供具体实现。"""

    def update(
        self,
        state: StudentCognitiveState,
        evidence: list[Evidence],
    ) -> StudentCognitiveState:
        ...


class BetaBernoulliUpdater:
    """简单 Beta(α,β) 伯努利后验——默认占位实现，使闭环可端到端跑通。

    不做规则加减分（V2.2 §8.2）。每条正确/错误证据更新 Beta 参数。
    """

    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0) -> None:
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta

    def update(
        self, state: StudentCognitiveState, evidence: list[Evidence]
    ) -> StudentCognitiveState:
        alpha = self.prior_alpha
        beta = self.prior_beta
        n = 0
        for ev in evidence:
            if ev.score is None:
                continue
            # 同题重复证据降权（V2.2 §15）
            w = max(0.0, 1.0 - ev.exposure_penalty)
            if ev.score >= 0.5:
                alpha += w
            else:
                beta += w
            n += 1

        posterior_mean = alpha / (alpha + beta)
        posterior_var = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))

        state.core = CoreState(
            mastery=posterior_mean,
            application=posterior_mean,   # 占位；#16/#17 区分 mastery/application/transfer
            transfer=posterior_mean,
        )
        state.uncertainty = UncertaintyState(
            posterior_variance=posterior_var,
            confidence=1.0 - posterior_var,
            evidence_count=len(evidence),
            effective_n=float(n),
        )
        state.fusion = FusionOutput(
            posterior_mean=posterior_mean,
            posterior_var=posterior_var,
            effective_n=float(n),
            model_contributions={"beta_bernoulli": 1.0},
            is_multimodal=False,
        )
        state.status = (
            StateStatus.OK if n >= 3 else StateStatus.INSUFFICIENT_EVIDENCE
        )
        state.updated_at = datetime.now(timezone.utc)
        return state


class AssessmentEngine:
    """测量引擎——状态唯一写者。"""

    def __init__(
        self,
        state_repo: StateRepository,
        evidence_repo: EvidenceRepository,
        updater: StateUpdater | None = None,
        governance: PrivacyGuard | None = None,
    ) -> None:
        self.state_repo = state_repo
        self.evidence_repo = evidence_repo
        self.updater = updater or BetaBernoulliUpdater()
        # 治理横切（V2.2 §20/§35 风险8）：写/读/导出全落审计，假名化
        self.governance = governance

    def _audit(self, actor: str, action: str, student_id: str, detail: str = "") -> None:
        if self.governance is None:
            return
        sid = self.governance.pseudonym(student_id)
        self.governance.log_access(actor, sid, action, detail)

    # ---- 证据采集（写证据 + 触发状态更新）----
    def ingest_evidence(self, ev: Evidence) -> StudentCognitiveState | None:
        self.evidence_repo.ingest(ev)
        self._audit("engine", "write_state", ev.student_id,
                     detail=f"ingest evidence={ev.id}")
        if ev.item_id and ev.score is not None:
            return None
        return None

    # ---- 状态更新（唯一写路径）----
    def update_state(
        self,
        student_id: str,
        node_id: str,
        node_version: str,
        domain: str,
        evidence: list[Evidence],
    ) -> StudentCognitiveState:
        state = self.state_repo.get(student_id, node_id)
        if state is None:
            state = self.state_repo.cold_start_state(
                student_id, node_id, node_version, domain
            )
        state = self.updater.update(state, evidence)
        self.state_repo.put(state)   # 写权限独占
        self._audit("engine", "write_state", student_id,
                     detail=f"node={node_id} n_ev={len(evidence)}")
        return state

    # ---- 只读：反查证据链 ----
    def get_provenance(self, student_id: str, node_id: str) -> list[Evidence]:
        self._audit("engine", "read_state", student_id,
                     detail=f"provenance node={node_id}")
        return self.evidence_repo.by_student(student_id)

    # ---- 只读：状态查询（Agent 也可经只读接口读）----
    def get_state(self, student_id: str, node_id: str) -> StudentCognitiveState | None:
        self._audit("agent", "read_state", student_id, detail=f"node={node_id}")
        return self.state_repo.get(student_id, node_id)

    # ---- 导出给 LLM/外部：必须去标识化（V2.2 §35 风险8）----
    def export_for_llm(self, student_id: str, node_id: str) -> dict | None:
        state = self.state_repo.get(student_id, node_id)
        if state is None:
            return None
        ev = self.evidence_repo.by_student(student_id)
        snapshot = {
            "student": self.governance.pseudonym(student_id)
            if self.governance else student_id,
            "node_id": node_id,
            "mastery": state.core.mastery,
            "application": state.core.application,
            "transfer": state.core.transfer,
            "confidence": state.uncertainty.confidence,
            "status": state.status.value,
            "evidence_count": len(ev),
        }
        if self.governance is not None:
            snapshot = self.governance.deidentify(snapshot)
            self._audit("engine", "export", student_id, detail="llm snapshot")
        return snapshot

    def audit_entries(self) -> list:
        if self.governance is None:
            return []
        return self.governance.audit.entries()
