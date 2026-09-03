"""融合后验更新策略。

融合多个证据源（V2.2 §9.5）：
- DINA：每节点 P(Mastery|Evidence)（per-node，证据来自相关题）
- IRT：总体 θ → 经 link 映射为该节点掌握度的独立证据
- 遗忘先验：群体先验 p0，强度 κ0（冷启动借力，V2.2 §9.6）

融合方法：logit 空间逆方差加权（近似分层贝叶斯，可反解）。
    logit(p) = ln(p/(1-p))
    fused_logit = Σ w_i logit_i / Σ w_i
    w_i ∝ 可靠性（有效样本量 / 1+se²）
贡献权重 model_contributions = w_i / Σw。
冲突检测：DINA 与 IRT 在 logit 空间分歧大且均可靠 → is_multimodal，落证据不足。
"""
from __future__ import annotations
import math
from datetime import datetime, timezone

from schemas.evidence import Evidence
from schemas.state import (
    StudentCognitiveState, StateStatus, CoreState, UncertaintyState, FusionOutput,
)
from repository import ItemRepository
from cdm.dina import DINA
from irt.model import IRT, TwoPL


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


class FusionUpdater:
    """分层贝叶斯融合更新策略（DINA + IRT + 遗忘先验）。"""

    def __init__(
        self,
        item_repo: ItemRepository,
        irt_items: list[TwoPL] | None = None,
        slip: float = 0.10,
        guess: float = 0.25,
        prior: float = 0.5,
        min_evidence: int = 3,
        group_prior: float = 0.5,
        group_strength: float = 2.0,       # 遗忘先验伪样本量 κ0
        theta_to_mastery_scale: float = 1.0,
        conflict_logit_threshold: float = 1.5,
    ) -> None:
        self.item_repo = item_repo
        self.irt = IRT(irt_items or [])
        self.slip = slip
        self.guess = guess
        self.prior = prior
        self.min_evidence = min_evidence
        self.group_prior = group_prior
        self.group_strength = group_strength
        self.scale = theta_to_mastery_scale
        self.conflict_thr = conflict_logit_threshold

    def _dina_for_node(
        self, node_id: str, evidence: list[Evidence]
    ) -> tuple[float, float]:
        """返回 (P(Mastery), effective_n) 由 DINA。"""
        skills: list[str] = []
        skill_idx: dict[str, int] = {}
        dina_items: list[dict] = []
        responses: dict[str, int] = {}
        for ev in evidence:
            if ev.score is None:
                continue
            item = self.item_repo.get_item(ev.item_id, ev.item_version)
            if item is None or node_id not in item.knowledge_tags:
                continue
            req = []
            for k in item.knowledge_tags:
                if k not in skill_idx:
                    skill_idx[k] = len(skills)
                    skills.append(k)
                req.append(skill_idx[k])
            dina_items.append({"id": item.id, "required": req,
                                "slip": self.slip, "guess": self.guess})
            responses[item.id] = 1 if ev.score >= 0.5 else 0
        if not responses:
            return 0.5, 0.0
        dina = DINA(skills, dina_items, prior=self.prior)
        probs = dina.posterior_mastery(responses)
        return probs.get(node_id, 0.5), float(len(responses))

    def _irt_evidence(
        self, evidence: list[Evidence]
    ) -> tuple[float, float]:
        """返回 (P(Mastery 由 IRT), weight)。"""
        responses = {}
        for ev in evidence:
            if ev.score is None:
                continue
            if ev.item_id in self.irt.items:
                responses[ev.item_id] = 1 if ev.score >= 0.5 else 0
        if not responses:
            return 0.5, 0.0
        theta, se = self.irt.estimate_theta(responses)
        p = _sigmoid(self.scale * theta)
        weight = 1.0 / max(se * se, 1e-6)
        return p, weight

    def update(
        self, state: StudentCognitiveState, evidence: list[Evidence]
    ) -> StudentCognitiveState:
        node_id = state.node_id
        p_dina, n_dina = self._dina_for_node(node_id, evidence)
        p_irt, w_irt = self._irt_evidence(evidence)

        # 各源 logit + 权重
        w_dina = n_dina                                 # 有效样本量
        w_prior = self.group_strength                   # 遗忘先验强度 κ0
        sources = []
        if w_dina > 0:
            sources.append(("dina", _logit(p_dina), w_dina))
        if w_irt > 0:
            sources.append(("irt", _logit(p_irt), w_irt))
        sources.append(("forgetting_prior", _logit(self.group_prior), w_prior))

        total_w = sum(w for _, _, w in sources)
        fused_logit = sum(w * l for _, l, w in sources) / total_w
        p_fused = _sigmoid(fused_logit)
        var = p_fused * (1 - p_fused) / max(total_w, 1e-6)   # 近似后验方差
        contributions = {name: w / total_w for name, _, w in sources}

        # 冲突检测
        is_multimodal = False
        if w_dina > 0 and w_irt > 0:
            if abs(_logit(p_dina) - _logit(p_irt)) > self.conflict_thr:
                is_multimodal = True

        state.core = CoreState(
            mastery=p_fused,
            application=p_fused,
            transfer=p_fused,
        )
        state.uncertainty = UncertaintyState(
            posterior_variance=var,
            confidence=1.0 - var,
            evidence_count=len(evidence),
            effective_n=total_w,
        )
        state.fusion = FusionOutput(
            posterior_mean=p_fused, posterior_var=var, effective_n=total_w,
            model_contributions=contributions, is_multimodal=is_multimodal,
        )
        if is_multimodal or n_dina < self.min_evidence:
            state.status = StateStatus.INSUFFICIENT_EVIDENCE
        else:
            state.status = StateStatus.OK
        state.updated_at = datetime.now(timezone.utc)
        return state
