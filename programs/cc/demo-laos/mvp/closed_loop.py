"""MVP 最小闭环打通（任务 #29）。

docs/01 §6 闭环定义：
    学生 → 自适应诊断题 → Evidence → CDM/IRT 融合 → Student State
        → Top3 认知缺口 → 学习决策 → Tutor 编排（只读）
        → 训练产生新证据 → 再测 → 迁移测试（外部非同源）→ 成长报告

合成数据演示（真实被试见任务 #14/#29 的人工部分）。本模块把前序所有引擎
串成一条可运行链路，验证写权限隔离、证据→状态→决策→干预→再测的完整性。
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field

from schemas.item import Item, QMatrixEntry, ItemType, AuditStatus
from schemas.evidence import Evidence, EvidenceLevel, EvidenceSource
from schemas.state import StudentCognitiveState, StateStatus
from repository import ItemRepository, EvidenceRepository, StateRepository
from assessment.engine import AssessmentEngine
from fusion.updater import FusionUpdater
from irt.model import TwoPL
from adaptive.engine import AdaptiveEngine, AdaptiveConstraints
from learning.decision import LearningDecisionEngine, ActionType
from tutor.agent import TutorAgent
from evaluation.transfer import (
    TransferValidator, TransferTestItem, TransferLevel,
)


# ---------------------------------------------------------------------------
# 合成题库
# ---------------------------------------------------------------------------

NODES = ["实词义项", "虚词辨析", "句式判断", "特殊用法", "信息筛选", "推断迁移"]
DOMAIN = "文言文阅读"


def build_item_bank(seed: int = 42) -> tuple[ItemRepository, list[TwoPL], list[Item]]:
    """构造合成题库：每节点 ~4 题，附 Q 矩阵与 IRT 参数。"""
    rng = random.Random(seed)
    repo = ItemRepository()
    irt_items: list[TwoPL] = []
    items: list[Item] = []
    iid = 0
    for ni, node in enumerate(NODES):
        for k in range(4):
            iid += 1
            # 1~2 个知识节点；难度按节点序递增
            req = [node] if k < 2 else [node, NODES[(ni + 1) % len(NODES)]]
            b = -1.5 + 0.6 * ni + 0.3 * k    # 难度
            a = rng.uniform(0.8, 1.6)        # 区分度
            tp = TwoPL(f"I{iid}", a, b)
            irt_items.append(tp)
            qm = [QMatrixEntry(knowledge=n, cognitive="understand",
                               weight=1.0, is_primary=(n == node))
                  for n in req]
            it = Item(
                id=f"I{iid}", version="v1", source="synthetic",
                text=f"文言文题 {iid}", question=f"下列哪项...({node})",
                options=["A", "B", "C", "D"], answer="A",
                knowledge_tags=list(req),
                q_matrix=qm,
                irt_applicable=True,
                item_type=ItemType.OBJECTIVE,
                audit_status=AuditStatus.APPROVED,
            )
            repo.put_item(it)
            items.append(it)
    return repo, irt_items, items


# ---------------------------------------------------------------------------
# 合成学生
# ---------------------------------------------------------------------------

@dataclass
class SyntheticStudent:
    student_id: str
    mastery: dict[str, float]          # 潜在真值
    slip: float = 0.12
    guess: float = 0.22


def make_student(seed: int = 7) -> SyntheticStudent:
    rng = random.Random(seed)
    m = {n: rng.uniform(0.1, 0.9) for n in NODES}
    return SyntheticStudent(f"S{seed}", m)


def simulate_response(student: SyntheticStudent, item: Item,
                      rng: random.Random) -> int:
    """DINA 类生成：所需节点全掌握→高正确率，否则靠猜。"""
    mastered = all(student.mastery[n] >= 0.5 for n in item.knowledge_tags)
    p = (1 - student.slip) if mastered else student.guess
    return 1 if rng.random() < p else 0


# ---------------------------------------------------------------------------
# 闭环
# ---------------------------------------------------------------------------

@dataclass
class ClosedLoopReport:
    student_id: str
    n_diagnostic_items: int
    gap_nodes: list[str]               # Top3 缺口
    action: str
    pre_mastery: dict[str, float]
    post_mastery: dict[str, float]
    transfer_confirmed: bool
    transfer_external_rate: float
    status_per_node: dict[str, str]

    def summary(self) -> str:
        lines = [f"=== MVP 闭环报告（学生 {self.student_id}）==="]
        lines.append(f"诊断题量: {self.n_diagnostic_items}")
        lines.append(f"Top3 认知缺口: {self.gap_nodes}")
        lines.append(f"学习动作: {self.action}")
        lines.append("干预前掌握度: " + ", ".join(
            f"{k}={v:.2f}" for k, v in self.pre_mastery.items()))
        lines.append("干预后掌握度: " + ", ".join(
            f"{k}={v:.2f}" for k, v in self.post_mastery.items()))
        gains = {k: self.post_mastery[k] - self.pre_mastery[k]
                 for k in self.pre_mastery}
        lines.append("增益: " + ", ".join(
            f"{k}={v:+.2f}" for k, v in gains.items()))
        lines.append(f"迁移确认(外部非同源): {self.transfer_confirmed} "
                     f"(外部迁移率={self.transfer_external_rate:.2f})")
        return "\n".join(lines)


class ClosedLoop:
    """端到端最小闭环。"""

    def __init__(self, seed: int = 42) -> None:
        self._ev_seq = 0
        self.item_repo, self.irt_items, self.all_items = build_item_bank(seed)
        self.state_repo = StateRepository()
        self.evidence_repo = EvidenceRepository()
        self.fusion = FusionUpdater(
            self.item_repo, self.irt_items,
            slip=0.12, guess=0.22, prior=0.5,
            min_evidence=2, group_prior=0.5, group_strength=2.0,
        )
        self.engine = AssessmentEngine(
            self.state_repo, self.evidence_repo, updater=self.fusion,
        )
        self.adaptive = AdaptiveEngine(self.item_repo, self.irt_items)
        self.decision = LearningDecisionEngine(explore_c=0.5)
        self.tutor = TutorAgent(assessment_engine=self.engine)
        self.validator = TransferValidator()

    def _evidence(self, student_id: str, item: Item, score: int,
                  level=EvidenceLevel.C, source=EvidenceSource.DIRECT_ANSWER,
                  tag: str = "d") -> Evidence:
        self._ev_seq += 1
        return Evidence(
            id=f"E-{student_id}-{self._ev_seq}-{tag}",
            student_id=student_id, item_id=item.id, item_version=item.version,
            response="A" if score else "B",
            score=float(score),
            source=source, evidence_level=level,
        )

    def assess_phase(self, student: SyntheticStudent) -> list[Evidence]:
        """自适应诊断阶段。"""
        rng = random.Random(hash(student.student_id) % 100000)
        seen: set[str] = set()
        evidence: list[Evidence] = []
        constraints = AdaptiveConstraints(
            content_coverage=set(NODES),
            min_length=6, max_length=18,
            target_variance=0.06, eig_epsilon=0.02,
        )
        # 用一个聚合状态驱动选题（以最弱节点代理）
        for _ in range(constraints.max_length):
            # 当前聚合状态：取所有已更新节点的均值；无则冷启动
            states = self.state_repo.all_for_student(student.student_id)
            if states:
                p = sum(s.core.mastery for s in states) / len(states)
            else:
                p = 0.5
            proxy = StudentCognitiveState(
                student_id=student.student_id, node_id="_proxy",
                node_version="v1", domain=DOMAIN,
            )
            proxy.core.mastery = p
            proxy.uncertainty.posterior_variance = constraints.target_variance
            if self.adaptive.should_stop(proxy, list(seen), self.all_items,
                                         0.0, constraints):
                break
            nxt = self.adaptive.select_next(
                proxy, self.all_items, seen, 0.0, constraints)
            if nxt is None:
                break
            seen.add(nxt.id)
            score = simulate_response(student, nxt, rng)
            ev = self._evidence(student.student_id, nxt, score)
            self.engine.evidence_repo.ingest(ev)
            evidence.append(ev)
            # 逐题更新每个相关节点状态
            for node in nxt.knowledge_tags:
                node_ev = [e for e in evidence
                           if node in self.item_repo.get_item(e.item_id, e.item_version).knowledge_tags]
                self.engine.update_state(
                    student.student_id, node, "v1", DOMAIN, node_ev)
        return evidence

    def top_gaps(self, student_id: str, k: int = 3) -> list[str]:
        states = self.state_repo.all_for_student(student_id)
        ranked = sorted(states, key=lambda s: s.core.mastery)
        return [s.node_id for s in ranked[:k]]

    def intervention_phase(self, student: SyntheticStudent,
                           gaps: list[str]) -> tuple[str, list[Evidence]]:
        """学习决策 + Tutor 编排 + 模拟训练产生新证据。"""
        # 用最弱缺口节点驱动决策
        node = gaps[0]
        state = self.engine.get_state(student.student_id, node)
        if state is None:
            state = self.state_repo.cold_start_state(
                student.student_id, node, "v1", DOMAIN)
        action = self.decision.decide(
            state,
            [ActionType.EXPLAIN, ActionType.BASIC_DRILL,
             ActionType.APPLY_DRILL, ActionType.SPACED_REVIEW],
            priority={n: 1.0 - (i + 1) / (len(gaps) + 1) for i, n in enumerate(gaps)},
        )
        # Tutor 只读编排（不写状态）
        tutor_msg = self.tutor.generate_action(state)
        # 模拟训练：对每个缺口节点做 2 道针对性题，掌握度提升后正确率上升
        rng = random.Random(99)
        train_ev: list[Evidence] = []
        for g in gaps:
            # 训练后该节点掌握度上升（仿真）
            improved = StudentCognitiveState(
                student_id=student.student_id, node_id=g,
                node_version="v1", domain=DOMAIN,
            )
            improved.core.mastery = min(1.0, student.mastery[g] + 0.3)
            train_items = [it for it in self.all_items if g in it.knowledge_tags][:2]
            for it in train_items:
                mastered = improved.core.mastery >= 0.5
                p = (1 - student.slip) if mastered else student.guess
                p = min(p + 0.2, 1.0)   # 训练后正确率提升
                score = 1 if rng.random() < p else 0
                ev = self._evidence(student.student_id, it, score,
                                    level=EvidenceLevel.C)
                self.engine.evidence_repo.ingest(ev)
                train_ev.append(ev)
        # 重新更新缺口节点状态
        for g in gaps:
            node_ev = [e for e in (self.evidence_repo.by_student(student.student_id))
                       if g in self.item_repo.get_item(e.item_id, e.item_version).knowledge_tags]
            self.engine.update_state(student.student_id, g, "v1", DOMAIN, node_ev)
        return f"{action.action_type.value} | {tutor_msg}", train_ev

    def transfer_phase(self, student: SyntheticStudent) -> tuple[bool, float]:
        """迁移测试：外部非同源材料（V2.2 §25）。"""
        rng = random.Random(123)
        # 外部非同源远迁移题
        ext_items = []
        for i in range(6):
            score = 1 if rng.random() < 0.65 else 0
            ext_items.append(TransferTestItem(
                f"EXT{i}", TransferLevel.COMPREHENSIVE,
                source_homologous=False, score=float(score)))
        # 同源题（不可单独采信）
        homo_items = [TransferTestItem("H1", TransferLevel.COMPREHENSIVE,
                                       True, 0.8)]
        res = self.validator.validate(homo_items + ext_items)
        confirmed = self.validator.is_transfer_confirmed(res, threshold=0.6)
        ext_rate = 0.0
        for r in res:
            if r.level == TransferLevel.COMPREHENSIVE and r.external_only:
                ext_rate = r.rate
        return confirmed, ext_rate

    def run(self, seed: int = 7) -> ClosedLoopReport:
        student = make_student(seed)
        # Pre
        self.assess_phase(student)
        pre = {s.node_id: s.core.mastery
               for s in self.state_repo.all_for_student(student.student_id)}
        gaps = self.top_gaps(student.student_id, 3)
        action, _ = self.intervention_phase(student, gaps)
        # Post
        post = {s.node_id: s.core.mastery
                for s in self.state_repo.all_for_student(student.student_id)}
        confirmed, ext_rate = self.transfer_phase(student)
        status = {s.node_id: s.status.value
                  for s in self.state_repo.all_for_student(student.student_id)}
        n_diag = len(self.evidence_repo.by_student(student.student_id))
        return ClosedLoopReport(
            student_id=student.student_id,
            n_diagnostic_items=n_diag,
            gap_nodes=gaps,
            action=action,
            pre_mastery=pre,
            post_mastery=post,
            transfer_confirmed=confirmed,
            transfer_external_rate=ext_rate,
            status_per_node=status,
        )


def run_closed_loop(seed: int = 7) -> ClosedLoopReport:
    return ClosedLoop(seed=42).run(seed=seed)


if __name__ == "__main__":
    rep = run_closed_loop()
    print(rep.summary())
