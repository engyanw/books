"""仓储层（Repository）——内存实现，接口与 Postgres 可替换。

对应 schemas/ 的数据模型。仓储是"哑存储"，不包含业务规则。
状态的写权限由 AssessmentEngine 独占（V2.2 §20），仓储本身不校验权限。
"""
from .ontology_repo import OntologyRepository
from .item_repo import ItemRepository
from .evidence_repo import EvidenceRepository
from .state_repo import StateRepository

__all__ = [
    "OntologyRepository",
    "ItemRepository",
    "EvidenceRepository",
    "StateRepository",
]
