"""Pre/Post + 四层迁移验证（任务 #23）。

V2.2 §25：迁移材料须系统外、非同源（高考真题/教师自命题/其他来源文本），
不得用系统自有题库自证。与 §33 实验4 外部效度对齐。
四层：Recall → Application → Transfer → Comprehensive。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class TransferLevel(str, Enum):
    RECALL = "recall"               # Level 1 记住
    APPLICATION = "application"     # Level 2 熟悉情境用
    TRANSFER = "transfer"           # Level 3 近迁移（相似不同材料）
    COMPREHENSIVE = "comprehensive" # Level 4 远迁移/综合（新文本新任务）


@dataclass
class TransferTestItem:
    id: str
    level: TransferLevel
    source_homologous: bool        # True=系统同源；False=外部非同源
    score: float = 0.0             # 0/1 或 rubric 分


@dataclass
class TransferResult:
    level: TransferLevel
    rate: float
    n: int
    external_only: bool            # 是否仅由非同源材料支撑


class TransferValidator:
    """四层迁移验证。远迁移结论须有外部非同源材料（V2.2 §25）。"""

    def validate(self, items: list[TransferTestItem]) -> list[TransferResult]:
        by_level: dict[TransferLevel, list[TransferTestItem]] = {}
        for it in items:
            by_level.setdefault(it.level, []).append(it)

        results: list[TransferResult] = []
        for level in TransferLevel:
            pool = by_level.get(level, [])
            if not pool:
                continue
            # 远迁移/综合层：须由非同源材料支撑
            if level in (TransferLevel.TRANSFER, TransferLevel.COMPREHENSIVE):
                external = [p for p in pool if not p.source_homologous]
                if external:
                    rate = sum(p.score for p in external) / len(external)
                    n = len(external)
                    results.append(TransferResult(level, rate, n, external_only=True))
                else:
                    # 缺外部材料 → 不可下迁移结论
                    results.append(TransferResult(level, 0.0, 0, external_only=False))
            else:
                rate = sum(p.score for p in pool) / len(pool)
                results.append(TransferResult(level, rate, len(pool), external_only=False))
        return results

    def is_transfer_confirmed(self, results: list[TransferResult],
                              threshold: float = 0.6) -> bool:
        """迁移结论成立：远迁移层有外部非同源材料且达标。"""
        for r in results:
            if r.level == TransferLevel.COMPREHENSIVE:
                return r.external_only and r.n > 0 and r.rate >= threshold
        return False


@dataclass
class PrePostDesign:
    """Pre-Test → Diagnosis → Intervention → Post-Test（docs/11.1）。"""
    pre: list[TransferTestItem] = field(default_factory=list)
    post: list[TransferTestItem] = field(default_factory=list)

    def pre_rate(self) -> float:
        return sum(i.score for i in self.pre) / max(len(self.pre), 1)

    def post_rate(self) -> float:
        return sum(i.score for i in self.post) / max(len(self.post), 1)

    def absolute_gain(self) -> float:
        return self.post_rate() - self.pre_rate()
