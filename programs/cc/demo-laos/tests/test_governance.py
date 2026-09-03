"""治理层测试：Q矩阵 + 公平性 + 隐私。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governance.qmatrix import QMatrixValidator, inter_rater_kappa
from governance.fairness import DIFDetector, SubgroupCalibration
from governance.privacy import PrivacyGuard, AuditChain, deidentify, hash_pii


def test_kappa_high_on_agreement():
    # 完全一致 → κ=1
    k = inter_rater_kappa([1, 0, 1, 1, 0], [1, 0, 1, 1, 0], [0, 1])
    assert abs(k - 1.0) < 1e-9
    # 不一致 → κ<1
    k2 = inter_rater_kappa([1, 0, 1, 1, 0], [0, 1, 0, 1, 0], [0, 1])
    assert k2 < 0.6, f"低一致应<0.6，实际{k2}"
    print("PASS test_kappa", round(k, 2), round(k2, 2))


def test_qmatrix_suspect_detection():
    # 3 题都标注到 s1；I3 实际作答与 s1 组偏差大 → 疑似误标
    q = {"I1": {"s1": 1}, "I2": {"s1": 1}, "I3": {"s1": 1}}
    # I1/I2 普遍正确，I3 错的多
    resp = {
        "u1": {"I1": 1, "I2": 1, "I3": 0},
        "u2": {"I1": 1, "I2": 0, "I3": 0},
        "u3": {"I1": 0, "I2": 1, "I3": 1},
        "u4": {"I1": 1, "I2": 1, "I3": 0},
        "u5": {"I1": 1, "I2": 1, "I3": 0},
    }
    v = QMatrixValidator(q)
    flags = v.residual_flags(resp)
    assert flags["I3"] > flags["I1"], "I3 残差应更高"
    suspects = v.suspect_items(resp, threshold=0.15)
    assert "I3" in suspects, "I3 应被列为疑似误标"
    print("PASS test_qmatrix", {k: round(val, 3) for k, val in flags.items()})


def test_dif_detection():
    # 组A 题X 普遍高；组B 同能力层题X 低 → 题X 标 DIF
    recs = []
    # 总分分层 0~10
    import random
    random.seed(3)
    for i in range(200):
        score = random.randint(0, 10)
        grp = "A" if i % 2 == 0 else "B"
        # X 题对 B 不利
        p_x = 0.8 if grp == "A" else 0.3
        # Y 题公平
        p_y = score / 10.0
        recs.append({"student_id": f"u{i}", "group": grp, "item_id": "X",
                     "correct": 1 if random.random() < p_x else 0, "total_score": score})
        recs.append({"student_id": f"u{i}", "group": grp, "item_id": "Y",
                     "correct": 1 if random.random() < p_y else 0, "total_score": score})
    d = DIFDetector(n_strata=5)
    res = d.detect(recs)
    by = {r.item_id: r for r in res}
    assert by["X"].flag, "X 应被标 DIF"
    assert not by["Y"].flag, "Y 不应被标 DIF"
    print("PASS test_dif", {k: round(v.delta, 3) for k, v in by.items()})


def test_subgroup_calibration():
    recs = [
        {"group": "G1", "predicted": 0.8, "actual": 0.5},  # 高估 → 告警
        {"group": "G1", "predicted": 0.8, "actual": 0.5},
        {"group": "G2", "predicted": 0.5, "actual": 0.5},  # 准 → 不告警
    ]
    sc = SubgroupCalibration(threshold=0.1)
    out = {e.group: e for e in sc.evaluate(recs)}
    assert out["G1"].alarm and not out["G2"].alarm
    print("PASS test_subgroup_calibration",
          {k: round(v.bias, 3) for k, v in out.items()})


def test_privacy_chain_and_delete():
    chain = AuditChain()
    pg = PrivacyGuard(chain, salt="x")

    # 去标识化
    rec = {"name": "张三", "phone": "13800001111", "score": 0.9}
    deid = pg.deidentify(rec)
    assert deid["name"].startswith("h:") and deid["phone"].startswith("h:")
    assert deid["score"] == 0.9, "非 PII 不应改"
    assert "张三" not in str(deid)

    # 审计
    pg.log_access("teacher", "S1", "read_state")
    pg.log_access("engine", "S1", "write_state", "evidence=E1")

    # 可删除权
    deleted = {}
    def deleter(sid): deleted[sid] = True
    token = pg.delete_subject("admin", "S1", deleter)
    assert deleted.get("S1")
    assert pg.is_deleted("S1")
    assert token.startswith("del_")

    # 链完整性
    assert chain.verify(), "审计链应校验通过"

    # 篡改检测
    chain._entries[0].detail = "tampered"
    assert not chain.verify(), "篡改后应校验失败"
    print("PASS test_privacy", token)


if __name__ == "__main__":
    test_kappa_high_on_agreement()
    test_qmatrix_suspect_detection()
    test_dif_detection()
    test_subgroup_calibration()
    test_privacy_chain_and_delete()
    print("\nAll governance tests passed.")
