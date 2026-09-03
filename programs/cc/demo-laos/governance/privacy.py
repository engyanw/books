"""隐私合规 / 去标识化 / 审计链 / 可删除权（任务 #27，V2.2 §35 风险8）。

- 去标识化：对 PII 字段做哈希脱敏。
- 审计链：每次读取/写入认知状态落一条不可变审计记录。
- 可删除权：按学生 ID 物理删除所有关联数据并记录删除令牌。
"""
from __future__ import annotations
import hashlib
import time
from dataclasses import dataclass, field
from typing import Callable


PII_FIELDS = {"name", "phone", "email", "id_card", "student_id"}


def hash_pii(value: str, salt: str = "") -> str:
    """确定性哈希脱敏（带盐）。"""
    return "h:" + hashlib.sha256((salt + value).encode("utf-8")).hexdigest()[:16]


def deidentify(record: dict, salt: str = "") -> dict:
    """脱敏记录中的 PII 字段。"""
    out = dict(record)
    for k in list(out.keys()):
        if k in PII_FIELDS and out[k] is not None:
            out[k] = hash_pii(str(out[k]), salt)
    return out


@dataclass
class AuditEntry:
    ts: float
    actor: str
    action: str          # read_state / write_state / delete / export
    student_id: str
    detail: str = ""
    hash_chain: str = ""  # 前一条的哈希，构成链


class AuditChain:
    """不可变审计链：每条记录含前条哈希，防篡改。"""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def _prev_hash(self) -> str:
        if not self._entries:
            return "GENESIS"
        e = self._entries[-1]
        s = f"{e.ts}|{e.actor}|{e.action}|{e.student_id}|{e.detail}|{e.hash_chain}"
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

    def record(self, actor: str, action: str, student_id: str, detail: str = "") -> AuditEntry:
        e = AuditEntry(time.time(), actor, action, student_id, detail, self._prev_hash())
        self._entries.append(e)
        return e

    def verify(self) -> bool:
        """校验链完整性：每条记录的 hash_chain 须等于前一条的哈希。"""
        prev = "GENESIS"
        for e in self._entries:
            if e.hash_chain != prev:
                return False
            s = f"{e.ts}|{e.actor}|{e.action}|{e.student_id}|{e.detail}|{e.hash_chain}"
            prev = hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]
        return True

    def entries(self) -> list[AuditEntry]:
        return list(self._entries)


class PrivacyGuard:
    """隐私合规总管。"""

    def __init__(self, audit: AuditChain | None = None, salt: str = "laos") -> None:
        self.audit = audit or AuditChain()
        self.salt = salt
        self._deleted: set[str] = set()

    def deidentify(self, record: dict) -> dict:
        return deidentify(record, self.salt)

    def pseudonym(self, student_id: str) -> str:
        """稳定假名化：审计链中不存原始 student_id（V2.2 §35 风险8）。"""
        return "p:" + hashlib.sha256(
            (self.salt + student_id).encode("utf-8")
        ).hexdigest()[:16]

    def log_access(self, actor: str, student_id: str, action: str, detail: str = "") -> AuditEntry:
        if action not in ("read_state", "write_state", "delete", "export"):
            raise ValueError(f"未知动作: {action}")
        return self.audit.record(actor, action, student_id, detail)

    def delete_subject(self, actor: str, student_id: str,
                       deleter: Callable[[str], None]) -> str:
        """行使可删除权：物理删除该学生所有数据，并记录删除令牌。

        deleter: 实际执行删除的回调（由 repository 注入），传入 student_id。
        返回删除令牌。
        """
        token = "del_" + hashlib.sha256(
            f"{student_id}:{time.time()}".encode("utf-8")
        ).hexdigest()[:16]
        deleter(student_id)
        self._deleted.add(student_id)
        self.audit.record(actor, "delete", student_id, f"token={token}")
        return token

    def is_deleted(self, student_id: str) -> bool:
        return student_id in self._deleted
