"""CDM 后验更新策略——把 DINA 接入 AssessmentEngine。

实现 StateUpdater 协议（assessment.engine）。对目标知识节点，聚合相关题，
构建多技能 DINA，取目标节点的边际 P(Mastery | Evidence)。
"""
from __future__ import annotations
from datetime import datetime, timezone

from schemas.evidence import Evidence
from schemas.state import (
    StudentCognitiveState, StateStatus, CoreState, UncertaintyState, FusionOutput,
)
from repository import ItemRepository
from .dina import DINA


class CdmUpdater:
    """DINA 后验更新策略（V2.2 §13.1 连续化：P(Mastery|Evidence) 进状态层）。"""

    def __init__(
        self,
        item_repo: ItemRepository,
        slip: float = 0.10,
        guess: float = 0.25,
        prior: float = 0.5,
        min_evidence: int = 3,
    ) -> None:
        self.item_repo = item_repo
        self.slip = slip
        self.guess = guess
        self.prior = prior
        self.min_evidence = min_evidence

    def update(
        self, state: StudentCognitiveState, evidence: list[Evidence]
    ) -> StudentCognitiveState:
        target = state.node_id
        # 聚合相关题：知识标签含目标节点的题
        skills: list[str] = []
        skill_idx: dict[str, int] = {}
        dina_items: list[dict] = []
        responses: dict[str, int] = {}

        for ev in evidence:
            if ev.score is None:
                continue
            item = self.item_repo.get_item(ev.item_id, ev.item_version)
            if item is None:
                continue
            if target not in item.knowledge_tags:
                continue
            # 收集该题所涉技能（目标节点 + 共现技能）
            req: list[int] = []
            for k in item.knowledge_tags:
                if k not in skill_idx:
                    skill_idx[k] = len(skills)
                    skills.append(k)
                req.append(skill_idx[k])
            dina_items.append({
                "id": item.id, "required": req,
                "slip": self.slip, "guess": self.guess,
            })
            responses[item.id] = 1 if ev.score >= 0.5 else 0

        n = len(responses)
        if n == 0:
            state.status = StateStatus.INSUFFICIENT_EVIDENCE
            state.updated_at = datetime.now(timezone.utc)
            return state

        dina = DINA(skills, dina_items, prior=self.prior)
        mastery_probs = dina.posterior_mastery(responses)
        p = mastery_probs.get(target, 0.0)

        state.core = CoreState(
            mastery=p,
            application=p,    # 占位；application/transfer 由 #18 融合与迁移测试区分
            transfer=p,
        )
        var = p * (1 - p)
        state.uncertainty = UncertaintyState(
            posterior_variance=var,
            confidence=1.0 - var,
            evidence_count=len(evidence),
            effective_n=float(n),
        )
        state.fusion = FusionOutput(
            posterior_mean=p, posterior_var=var, effective_n=float(n),
            model_contributions={"dina": 1.0}, is_multimodal=False,
        )
        state.status = (
            StateStatus.OK if n >= self.min_evidence else StateStatus.INSUFFICIENT_EVIDENCE
        )
        state.updated_at = datetime.now(timezone.utc)
        return state
