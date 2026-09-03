"""Item 仓储——题目、Q 矩阵、标注记录。"""
from __future__ import annotations
from schemas.item import Item, QMatrixEntry, AnnotationRecord


class ItemRepository:
    def __init__(self) -> None:
        # (id, version) -> Item
        self._items: dict[tuple[str, str], Item] = {}
        # item_id -> 标注记录
        self._annotations: dict[str, AnnotationRecord] = {}

    def put_item(self, item: Item) -> None:
        self._items[(item.id, item.version)] = item

    def get_item(self, item_id: str, version: str) -> Item | None:
        return self._items.get((item_id, version))

    def latest_version(self, item_id: str) -> str | None:
        versions = [v for (i, v) in self._items if i == item_id]
        return max(versions) if versions else None

    def q_matrix(self, item_id: str, version: str) -> list[QMatrixEntry]:
        item = self.get_item(item_id, version)
        return list(item.q_matrix) if item else []

    def put_annotation(self, rec: AnnotationRecord) -> None:
        self._annotations[rec.item_id] = rec

    def annotation(self, item_id: str) -> AnnotationRecord | None:
        return self._annotations.get(item_id)

    def approved_items(self) -> list[Item]:
        """仅返回通过审核、可入诊断链路的题。"""
        return [it for it in self._items.values() if it.audit_status.value == "approved"]
