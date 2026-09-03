"""诊断探针机制（Phase 5）。

对应 docs/08 §6 与任务 #20。
三级探针：Recall → Discrimination → Explanation。
区分：不知道 / 知道但不会用 / 会用但不稳定 / 理解但迁移失败。
探针属诊断证据（EvidenceLevel.D），不混入正式考试分数。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum

from schemas.evidence import Evidence, EvidenceLevel, EvidenceSource


class ProbeLevel(str, Enum):
    RECALL = "recall"                # 是否知道
    DISCRIMINATION = "discrimination"  # 相似情境能否区分
    EXPLANATION = "explanation"      # 是否理解规则/原因


@dataclass
class Probe:
    id: str
    node_id: str
    level: ProbeLevel
    prompt: str
    expected: str                  # 期望回答/判定依据
    cost: float = 1.0


# 探针结果 → 错误归类（docs/08 §6）
_ERROR_LADDER = {
    "unknown": "不知道",
    "know_cant_apply": "知道但不会用",
    "unstable": "会用但不稳定",
    "transfer_fail": "理解但迁移失败",
    "stable": "常规情境会用",
}


class ProbeEngine:
    """探针触发与结果解释。"""

    def __init__(self) -> None:
        self._probes: dict[str, Probe] = {}

    def put(self, probe: Probe) -> None:
        self._probes[probe.id] = probe

    def probes_for_node(self, node_id: str) -> list[Probe]:
        return [p for p in self._probes.values() if p.node_id == node_id]

    def interpret(
        self, results: dict[ProbeLevel, bool | None]
    ) -> tuple[str, str]:
        """根据三级探针结果判定错误层级。

        返回 (ladder_key, label)。
        results: {ProbeLevel: 正确?}，None=未施测。
        """
        recall = results.get(ProbeLevel.RECALL)
        discrim = results.get(ProbeLevel.DISCRIMINATION)
        expl = results.get(ProbeLevel.EXPLANATION)

        if recall is False:
            return "unknown", _ERROR_LADDER["unknown"]
        if recall is True and (discrim is False):
            return "know_cant_apply", _ERROR_LADDER["know_cant_apply"]
        if discrim is True and expl is False:
            return "unstable", _ERROR_LADDER["unstable"]
        if expl is True:
            return "stable", _ERROR_LADDER["stable"]
        return "unknown", _ERROR_LADDER["unknown"]

    def to_evidence(self, probe: Probe, student_id: str, correct: bool) -> Evidence:
        """探针结果 → 诊断证据（level D，不进正式分数）。"""
        return Evidence(
            id=f"{probe.id}-{student_id}",
            student_id=student_id,
            item_id=probe.id,
            item_version="P1",
            score=1.0 if correct else 0.0,
            source=EvidenceSource.PROBE,
            evidence_level=EvidenceLevel.D,
            response=probe.prompt,
        )
