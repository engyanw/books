"""Baseline A–E 对比框架实现（任务 #2 实现层，docs/02 §4）。

每条基线封装为独立类，统一接口：
    estimate(evidence, item_repo, irt_items=None) -> dict[node_id, mastery_prob]

A 单纯正确率 | B 正确率+知识标签 | C IRT | D DINA/GDINA | E 本系统(融合)
所有基线在相同 Evidence/被试上运行，唯一变量是方法（docs/02 §3.1）。
"""
from __future__ import annotations
from typing import Protocol

from schemas.evidence import Evidence
from schemas.state import StudentCognitiveState
from repository import ItemRepository
from irt.model import TwoPL, IRT
from cdm.dina import DINA
from fusion.updater import FusionUpdater


class Baseline(Protocol):
    name: str
    def estimate(self, evidence: list[Evidence],
                 item_repo: ItemRepository,
                 irt_items: list[TwoPL] | None = None) -> dict[str, float]: ...


def _evidence_by_item(evidence: list[Evidence]) -> dict[str, int]:
    return {ev.item_id: (1 if (ev.score or 0) >= 0.5 else 0) for ev in evidence}


def _nodes_for(evidence: list[Evidence], item_repo: ItemRepository) -> list[str]:
    nodes: list[str] = []
    seen: set[str] = set()
    for ev in evidence:
        it = item_repo.get_item(ev.item_id, ev.item_version)
        if it is None:
            continue
        for n in it.knowledge_tags:
            if n not in seen:
                seen.add(n)
                nodes.append(n)
    return nodes


# ---------------------------------------------------------------------------
# Baseline A：单纯正确率（无知识粒度，所有节点同一正确率）
# ---------------------------------------------------------------------------

class BaselineA:
    name = "A_accuracy"

    def estimate(self, evidence, item_repo, irt_items=None) -> dict[str, float]:
        resp = _evidence_by_item(evidence)
        if not resp:
            return {}
        rate = sum(resp.values()) / len(resp)
        return {n: rate for n in _nodes_for(evidence, item_repo)}


# ---------------------------------------------------------------------------
# Baseline B：正确率 + 知识标签（分知识点正确率）
# ---------------------------------------------------------------------------

class BaselineB:
    name = "B_tagged_accuracy"

    def estimate(self, evidence, item_repo, irt_items=None) -> dict[str, float]:
        node_scores: dict[str, list[int]] = {}
        for ev in evidence:
            it = item_repo.get_item(ev.item_id, ev.item_version)
            if it is None:
                continue
            x = 1 if (ev.score or 0) >= 0.5 else 0
            for n in it.knowledge_tags:
                node_scores.setdefault(n, []).append(x)
        return {n: (sum(v) / len(v)) for n, v in node_scores.items()}


# ---------------------------------------------------------------------------
# Baseline C：IRT（单维 θ → sigmoid 映射为掌握度）
# ---------------------------------------------------------------------------

class BaselineC:
    name = "C_irt"

    def estimate(self, evidence, item_repo, irt_items=None) -> dict[str, float]:
        if irt_items is None:
            return {}
        irt = IRT(irt_items)
        theta, _se = irt.estimate_theta(_evidence_by_item(evidence))
        p = 1.0 / (1.0 + __import__("math").exp(-theta))
        return {n: p for n in _nodes_for(evidence, item_repo)}


# ---------------------------------------------------------------------------
# Baseline D：DINA/GDINA（每节点属性掌握概率）
# ---------------------------------------------------------------------------

class BaselineD:
    name = "D_dina"

    def estimate(self, evidence, item_repo, irt_items=None) -> dict[str, float]:
        skills: list[str] = []
        skill_idx: dict[str, int] = {}
        dina_items: list[dict] = []
        resp = {}
        for ev in evidence:
            it = item_repo.get_item(ev.item_id, ev.item_version)
            if it is None:
                continue
            req = []
            for k in it.knowledge_tags:
                if k not in skill_idx:
                    skill_idx[k] = len(skills)
                    skills.append(k)
                req.append(skill_idx[k])
            dina_items.append({"id": it.id, "required": req,
                                "slip": 0.10, "guess": 0.25})
            resp[it.id] = 1 if (ev.score or 0) >= 0.5 else 0
        if not resp:
            return {}
        dina = DINA(skills, dina_items, prior=0.5)
        return dina.posterior_mastery(resp)


# ---------------------------------------------------------------------------
# Baseline E：本系统（融合 DINA + IRT + 遗忘先验，复用 FusionUpdater）
# ---------------------------------------------------------------------------

class BaselineE:
    name = "E_system"

    def __init__(self, slip=0.10, guess=0.25, prior=0.5,
                 min_evidence=2, group_prior=0.5, group_strength=2.0) -> None:
        self.cfg = dict(slip=slip, guess=guess, prior=prior,
                        min_evidence=min_evidence,
                        group_prior=group_prior,
                        group_strength=group_strength)

    def estimate(self, evidence, item_repo, irt_items=None) -> dict[str, float]:
        fusion = FusionUpdater(item_repo, irt_items or [], **self.cfg)
        out: dict[str, float] = {}
        for n in _nodes_for(evidence, item_repo):
            state = StudentCognitiveState(
                student_id="_baseline", node_id=n,
                node_version="v1", domain="d",
            )
            fusion.update(state, evidence)
            out[n] = state.core.mastery
        return out


ALL_BASELINES: list = [BaselineA(), BaselineB(), BaselineC(),
                       BaselineD(), BaselineE()]
