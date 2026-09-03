"""认知诊断模型（CDM）——DINA / GDINA。

对应 docs/07 §3 与任务 #16。DINA 输出 P(Mastery | Evidence)，不做规则加减分。
连续化：以 P(α_k=1 | x) 作为连续掌握度进入状态层（V2.2 §13.1）。
"""
from .dina import DINA, GDINA

__all__ = ["DINA", "GDINA"]
