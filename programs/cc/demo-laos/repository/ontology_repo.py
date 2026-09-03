"""Ontology 仓储——知识图谱节点、关系、标准映射。"""
from __future__ import annotations
from schemas.ontology import Knowledge, Relation, TaskCapability, CoreLiteracy, StandardMapping


class OntologyRepository:
    def __init__(self) -> None:
        self._knowledge: dict[str, Knowledge] = {}
        self._relations: dict[str, Relation] = {}
        self._tasks: dict[str, TaskCapability] = {}
        self._literacies: dict[str, CoreLiteracy] = {}
        self._mappings: dict[tuple, StandardMapping] = {}

    # ---- 知识节点 ----
    def put_knowledge(self, k: Knowledge) -> None:
        self._knowledge[k.id] = k

    def get_knowledge(self, node_id: str) -> Knowledge | None:
        return self._knowledge.get(node_id)

    # ---- 关系 ----
    def put_relation(self, r: Relation) -> None:
        self._relations[r.id] = r

    def relations_from(self, node_id: str) -> list[Relation]:
        return [r for r in self._relations.values() if r.src == node_id]

    # ---- 任务能力 / 素养 ----
    def put_task(self, t: TaskCapability) -> None:
        self._tasks[t.id] = t

    def put_literacy(self, lit: CoreLiteracy) -> None:
        self._literacies[lit.id] = lit

    # ---- 标准映射 ----
    def put_mapping(self, m: StandardMapping) -> None:
        self._mappings[(m.standard_id, m.knowledge_id, m.cognitive_process)] = m

    def mappings_for_knowledge(self, knowledge_id: str) -> list[StandardMapping]:
        return [m for m in self._mappings.values() if m.knowledge_id == knowledge_id]
