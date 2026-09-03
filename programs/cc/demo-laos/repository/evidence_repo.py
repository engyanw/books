"""Evidence 仓储——证据采集、查询、Provenance 反查。"""
from __future__ import annotations
from collections import defaultdict
from schemas.evidence import Evidence


class EvidenceRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, Evidence] = {}
        self._by_student: dict[str, list[str]] = defaultdict(list)
        self._by_item: dict[str, list[str]] = defaultdict(list)

    def ingest(self, ev: Evidence) -> None:
        """采集证据，附元数据（版本号已在 Evidence 对象中，保证可追溯）。"""
        if ev.id in self._by_id:
            raise ValueError(f"duplicate evidence id: {ev.id}")
        self._by_id[ev.id] = ev
        self._by_student[ev.student_id].append(ev.id)
        self._by_item[ev.item_id].append(ev.id)

    def get(self, evidence_id: str) -> Evidence | None:
        return self._by_id.get(evidence_id)

    def by_student(self, student_id: str) -> list[Evidence]:
        return [self._by_id[i] for i in self._by_student.get(student_id, [])]

    def by_student_node(
        self, student_id: str, knowledge_ids: set[str]
    ) -> list[Evidence]:
        """某学生、关联到指定知识节点的证据（用于状态 Provenance）。"""
        out: list[Evidence] = []
        for ev in self.by_student(student_id):
            # 通过 item 的 knowledge_tags 反查；标签查询需 ItemRepository，
            # 此处仅按 item 聚合，由调用方补充节点关联。
            out.append(ev)
        return out

    def provenance(self, evidence_ids: list[str]) -> list[Evidence]:
        """反查证据链（V2.2 §6.3）。"""
        return [self._by_id[i] for i in evidence_ids if i in self._by_id]
