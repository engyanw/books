"""Assessment Engine——测量与状态核心链路。

职责（docs/07）：设计测量 → 获取证据 → 更新状态 → 估计不确定性 → 生成评价结果。
不负责：生成讲义、学习路径、修改评价标准。

权限边界（V2.2 §20）：Update Student State 仅本引擎可写；Agent 无写权限。
LLM 不在此核心链路。
"""
from .engine import AssessmentEngine, StateUpdater, BetaBernoulliUpdater

__all__ = ["AssessmentEngine", "StateUpdater", "BetaBernoulliUpdater"]
