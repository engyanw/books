"""IRT（项目反应理论）。

对应 docs/07 §4 与任务 #17。
2PL 模型：P(X=1|θ) = 1 / (1 + exp(-a(θ - b)))
- a 区分度，b 难度
- 多领域 θ（θ_language / θ_reading / θ_classical）

适用边界（V2.2 §13.2）：仅客观题；主观题用 MIRT/分层 rater，不在此。
"""
from .model import IRT, TwoPL

__all__ = ["IRT", "TwoPL"]
