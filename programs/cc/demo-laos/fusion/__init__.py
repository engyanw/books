"""状态融合范式（V2.2 §9.5）。

分层贝叶斯融合：DINA（每节点掌握度）+ IRT（总体能力）+ 遗忘先验，在 logit 空间
按可靠性加权融合，输出后验均值/方差/有效样本量/各模型贡献权重（可反解）。
冲突证据不强行仲裁，落入"证据不足"通道。
"""
from .updater import FusionUpdater

__all__ = ["FusionUpdater"]
