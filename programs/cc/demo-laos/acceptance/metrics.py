"""MVP 五项验收指标（任务 #30）。

规划 V1.0 §十九 五项：
  19.1 Measurement Validity    —— Test-Retest / Classification Consistency / Calibration
  19.2 Diagnostic Validity     —— Precision/Recall/F1/AUC/Calibration vs 专家判断
  19.3 Adaptive Efficiency     —— 固定20题 vs 自适应10~15题，相近精度更少题量
  19.4 Learning Effect         —— Pre / Post / Retention / Transfer
  19.5 Decision Quality        —— AI 个性化 vs 随机练题

在合成数据上计算并给出达标判定（真实被试见人工实验）。
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field

from experiments.core import auc, brier, f1
from mvp.closed_loop import ClosedLoop, make_student, NODES


# ---------------------------------------------------------------------------
# 19.1 Measurement Validity
# ---------------------------------------------------------------------------

@dataclass
class MeasurementValidity:
    test_retest_correlation: float   # 两次评估掌握度排序相关
    classification_consistency: float  # 掌握/未掌握二分一致率
    calibration_brier: float          # 预测概率 vs 实际
    passed: bool


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx > 0 and dy > 0 else 0.0


def measure_measurement_validity(n_students: int = 30, seed: int = 101) -> MeasurementValidity:
    """同一批学生跑两遍闭环（不同题目随机序列），看掌握度估计稳定性。"""
    rng = random.Random(seed)
    pre_mastery: dict[str, list[float]] = {}
    post_mastery: dict[str, list[float]] = {}
    actual_labels: list[int] = []
    pred_probs: list[float] = []
    for i in range(n_students):
        s = make_student(seed=rng.randint(0, 10**6))
        # 两次评估
        cl1 = ClosedLoop(seed=rng.randint(1, 10**6))
        cl1.assess_phase(s)
        m1 = {st.node_id: st.core.mastery
              for st in cl1.state_repo.all_for_student(s.student_id)}
        # 第二次（不同题序）
        cl2 = ClosedLoop(seed=rng.randint(1, 10**6))
        cl2.assess_phase(s)
        m2 = {st.node_id: st.core.mastery
              for st in cl2.state_repo.all_for_student(s.student_id)}
        common = sorted(set(m1) & set(m2))
        for nd in common:
            pre_mastery.setdefault(nd, []).append(m1[nd])
            post_mastery.setdefault(nd, []).append(m2[nd])
            # 校准：实际掌握（真值>=0.5）vs 预测
            actual_labels.append(1 if s.mastery[nd] >= 0.5 else 0)
            pred_probs.append(m1[nd])
    # 聚合相关：取每节点序列
    cors = []
    cons_rates = []
    for nd in pre_mastery:
        a = pre_mastery[nd]
        b = post_mastery[nd]
        if len(a) > 2:
            cors.append(_pearson(a, b))
            # 二分一致
            agree = sum(1 for x, y in zip(a, b)
                        if (x >= 0.5) == (y >= 0.5)) / len(a)
            cons_rates.append(agree)
    trr = sum(cors) / len(cors) if cors else 0.0
    cc = sum(cons_rates) / len(cons_rates) if cons_rates else 0.0
    cal = brier(pred_probs, actual_labels)
    passed = trr >= 0.6 and cc >= 0.7 and cal <= 0.3
    return MeasurementValidity(
        test_retest_correlation=round(trr, 3),
        classification_consistency=round(cc, 3),
        calibration_brier=round(cal, 3),
        passed=passed,
    )


# ---------------------------------------------------------------------------
# 19.2 Diagnostic Validity
# ---------------------------------------------------------------------------

@dataclass
class DiagnosticValidity:
    precision: float
    recall: float
    f1: float
    auc: float
    calibration: float
    passed: bool


def measure_diagnostic_validity(n_students: int = 30, seed: int = 202) -> DiagnosticValidity:
    """系统掌握判定 vs 潜在真值（代理"专家判断"）。"""
    rng = random.Random(seed)
    pred_probs: list[float] = []
    labels: list[int] = []
    for i in range(n_students):
        s = make_student(seed=rng.randint(0, 10**6))
        cl = ClosedLoop(seed=rng.randint(1, 10**6))
        cl.assess_phase(s)
        for st in cl.state_repo.all_for_student(s.student_id):
            nd = st.node_id
            if nd not in s.mastery:
                continue
            pred_probs.append(st.core.mastery)
            labels.append(1 if s.mastery[nd] >= 0.5 else 0)
    a = auc(pred_probs, labels)
    f1v = f1(pred_probs, labels, thresh=0.5)
    # precision / recall
    tp = fp = fn = 0
    for p, y in zip(pred_probs, labels):
        pred = 1 if p >= 0.5 else 0
        if pred == 1 and y == 1:
            tp += 1
        elif pred == 1 and y == 0:
            fp += 1
        elif pred == 0 and y == 1:
            fn += 1
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    cal = brier(pred_probs, labels)
    passed = a >= 0.75 and f1v >= 0.6 and cal <= 0.3
    return DiagnosticValidity(
        precision=round(prec, 3), recall=round(rec, 3),
        f1=round(f1v, 3), auc=round(a, 3),
        calibration=round(cal, 3), passed=passed,
    )


# ---------------------------------------------------------------------------
# 19.3 Adaptive Efficiency
# ---------------------------------------------------------------------------

@dataclass
class AdaptiveEfficiency:
    fixed_items: int                 # 固定题量
    adaptive_items: int              # 自适应平均题量
    fixed_auc: float
    adaptive_auc: float
    reduction_pct: float
    passed: bool                      # 相近精度下题量减少


def _fixed_assess_auc(n_items: int, n_students: int, rng: random.Random) -> float:
    from mvp.closed_loop import simulate_response
    preds, labels = [], []
    for i in range(n_students):
        s = make_student(seed=rng.randint(0, 10**6))
        cl = ClosedLoop(seed=rng.randint(1, 10**6))
        items = rng.sample(cl.all_items, min(n_items, len(cl.all_items)))
        for nd in NODES:
            nd_items = [it for it in items if nd in it.knowledge_tags]
            if not nd_items:
                continue
            scs = [simulate_response(s, it, rng) for it in nd_items]
            preds.append(sum(scs) / len(scs))
            labels.append(1 if s.mastery[nd] >= 0.5 else 0)
    return auc(preds, labels)


def measure_adaptive_efficiency(n_students: int = 25, seed: int = 303) -> AdaptiveEfficiency:
    rng = random.Random(seed)
    fixed_n = 20
    fixed_a = _fixed_assess_auc(fixed_n, n_students, rng)
    # 自适应平均题量：从闭环报告取
    ada_items = []
    ada_preds, ada_labels = [], []
    from mvp.closed_loop import simulate_response
    for i in range(n_students):
        s = make_student(seed=rng.randint(0, 10**6))
        cl = ClosedLoop(seed=rng.randint(1, 10**6))
        ev = cl.assess_phase(s)
        ada_items.append(len(ev))
        for st in cl.state_repo.all_for_student(s.student_id):
            nd = st.node_id
            if nd in s.mastery:
                ada_preds.append(st.core.mastery)
                ada_labels.append(1 if s.mastery[nd] >= 0.5 else 0)
    ada_n = int(sum(ada_items) / len(ada_items)) if ada_items else fixed_n
    ada_a = auc(ada_preds, ada_labels)
    reduction = (1 - ada_n / fixed_n) * 100 if fixed_n > 0 else 0.0
    # 相近精度（自适应AUC不低于固定0.05以内）且题量减少
    passed = (ada_a >= fixed_a - 0.05) and (ada_n < fixed_n)
    return AdaptiveEfficiency(
        fixed_items=fixed_n, adaptive_items=ada_n,
        fixed_auc=round(fixed_a, 3), adaptive_auc=round(ada_a, 3),
        reduction_pct=round(reduction, 1), passed=passed,
    )


# ---------------------------------------------------------------------------
# 19.4 Learning Effect
# ---------------------------------------------------------------------------

@dataclass
class LearningEffect:
    pre: float
    post: float
    retention: float
    transfer: float
    gain: float
    passed: bool


def measure_learning_effect(n_students: int = 20, seed: int = 404) -> LearningEffect:
    """闭环 Pre/Post + 仿真 Retention/Transfer。"""
    rng = random.Random(seed)
    pres, posts, rets, trans = [], [], [], []
    for i in range(n_students):
        s = make_student(seed=rng.randint(0, 10**6))
        cl = ClosedLoop(seed=rng.randint(1, 10**6))
        cl.assess_phase(s)
        pre = {st.node_id: st.core.mastery
               for st in cl.state_repo.all_for_student(s.student_id)}
        gaps = cl.top_gaps(s.student_id, 3)
        cl.intervention_phase(s, gaps)
        post = {st.node_id: st.core.mastery
                for st in cl.state_repo.all_for_student(s.student_id)}
        common = sorted(set(pre) & set(post))
        if not common:
            continue
        pres.append(sum(pre.values()) / len(pre))
        posts.append(sum(post.values()) / len(post))
        # 保留：7天后衰减（仿真，λ=0.05）
        lam = 0.05
        rets.append(sum(post.values()) / len(post) * math.exp(-lam * 7))
        # 迁移：外部迁移率
        _, ext = cl.transfer_phase(s)
        trans.append(ext)
    pre = sum(pres) / len(pres)
    post = sum(posts) / len(posts)
    ret = sum(rets) / len(rets)
    tra = sum(trans) / len(trans)
    passed = (post > pre) and (ret >= pre * 0.8) and (tra >= 0.5)
    return LearningEffect(
        pre=round(pre, 3), post=round(post, 3),
        retention=round(ret, 3), transfer=round(tra, 3),
        gain=round(post - pre, 3), passed=passed,
    )


# ---------------------------------------------------------------------------
# 19.5 Decision Quality
# ---------------------------------------------------------------------------

@dataclass
class DecisionQuality:
    ai_gain: float          # AI 个性化干预增益
    random_gain: float      # 随机练题增益
    delta: float
    passed: bool            # AI > 随机


def _random_practice_gain(s, rng: random.Random) -> float:
    """随机练题：随机选节点训练，增益较小。"""
    from mvp.closed_loop import simulate_response
    cl = ClosedLoop(seed=rng.randint(1, 10**6))
    cl.assess_phase(s)
    pre = sum(st.core.mastery
              for st in cl.state_repo.all_for_student(s.student_id)) / max(
        len(cl.state_repo.all_for_student(s.student_id)), 1)
    # 随机练 3 个节点各 1 题（非针对性）
    train_nodes = rng.sample(NODES, 3)
    for nd in train_nodes:
        items = [it for it in cl.all_items if nd in it.knowledge_tags][:1]
        for it in items:
            score = simulate_response(s, it, rng)
            ev = cl._evidence(s.student_id, it, score, tag="rnd")
            cl.engine.evidence_repo.ingest(ev)
        node_ev = [e for e in cl.evidence_repo.by_student(s.student_id)
                   if nd in cl.item_repo.get_item(e.item_id, e.item_version).knowledge_tags]
        cl.engine.update_state(s.student_id, nd, "v1", "文言文阅读", node_ev)
    post = sum(st.core.mastery
               for st in cl.state_repo.all_for_student(s.student_id)) / max(
        len(cl.state_repo.all_for_student(s.student_id)), 1)
    return post - pre


def _ai_personalized_gain(s, rng: random.Random) -> float:
    """AI 个性化：闭环决策+针对性训练。"""
    cl = ClosedLoop(seed=rng.randint(1, 10**6))
    cl.assess_phase(s)
    pre = sum(st.core.mastery
              for st in cl.state_repo.all_for_student(s.student_id)) / max(
        len(cl.state_repo.all_for_student(s.student_id)), 1)
    gaps = cl.top_gaps(s.student_id, 3)
    cl.intervention_phase(s, gaps)
    post = sum(st.core.mastery
               for st in cl.state_repo.all_for_student(s.student_id)) / max(
        len(cl.state_repo.all_for_student(s.student_id)), 1)
    return post - pre


def measure_decision_quality(n_students: int = 20, seed: int = 505) -> DecisionQuality:
    rng = random.Random(seed)
    ai_gains, rnd_gains = [], []
    for i in range(n_students):
        s = make_student(seed=rng.randint(0, 10**6))
        ai_gains.append(_ai_personalized_gain(s, rng))
        rnd_gains.append(_random_practice_gain(s, rng))
    ai_g = sum(ai_gains) / len(ai_gains)
    rnd_g = sum(rnd_gains) / len(rnd_gains)
    return DecisionQuality(
        ai_gain=round(ai_g, 3), random_gain=round(rnd_g, 3),
        delta=round(ai_g - rnd_g, 3), passed=ai_g > rnd_g,
    )


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------

@dataclass
class AcceptanceReport:
    measurement_validity: MeasurementValidity
    diagnostic_validity: DiagnosticValidity
    adaptive_efficiency: AdaptiveEfficiency
    learning_effect: LearningEffect
    decision_quality: DecisionQuality

    def all_passed(self) -> bool:
        return all([
            self.measurement_validity.passed,
            self.diagnostic_validity.passed,
            self.adaptive_efficiency.passed,
            self.learning_effect.passed,
            self.decision_quality.passed,
        ])

    def summary(self) -> str:
        m = self.measurement_validity
        d = self.diagnostic_validity
        e = self.adaptive_efficiency
        le = self.learning_effect
        q = self.decision_quality
        lines = ["=== MVP 五项验收指标（合成数据演示）==="]
        lines.append(
            f"[1] Measurement Validity   TRT相关={m.test_retest_correlation} "
            f"分类一致={m.classification_consistency} Brier={m.calibration_brier} "
            f"{'PASS' if m.passed else 'FAIL'}"
        )
        lines.append(
            f"[2] Diagnostic Validity    P={d.precision} R={d.recall} "
            f"F1={d.f1} AUC={d.auc} Brier={d.calibration} "
            f"{'PASS' if d.passed else 'FAIL'}"
        )
        lines.append(
            f"[3] Adaptive Efficiency    固定{e.fixed_items}题AUC={e.fixed_auc} vs "
            f"自适应{e.adaptive_items}题AUC={e.adaptive_auc} 减少{e.reduction_pct}% "
            f"{'PASS' if e.passed else 'FAIL'}"
        )
        lines.append(
            f"[4] Learning Effect        Pre={le.pre} Post={le.post} "
            f"保持={le.retention} 迁移={le.transfer} 增益={le.gain} "
            f"{'PASS' if le.passed else 'FAIL'}"
        )
        lines.append(
            f"[5] Decision Quality       AI增益={q.ai_gain} vs 随机={q.random_gain} "
            f"Δ={q.delta} {'PASS' if q.passed else 'FAIL'}"
        )
        lines.append(f"总验收: {'ALL PASS' if self.all_passed() else 'PARTIAL'}")
        return "\n".join(lines)


def run_acceptance(n_students: int = 15) -> AcceptanceReport:
    return AcceptanceReport(
        measurement_validity=measure_measurement_validity(n_students),
        diagnostic_validity=measure_diagnostic_validity(n_students),
        adaptive_efficiency=measure_adaptive_efficiency(n_students),
        learning_effect=measure_learning_effect(n_students),
        decision_quality=measure_decision_quality(n_students),
    )


if __name__ == "__main__":
    rep = run_acceptance(n_students=12)
    print(rep.summary())
