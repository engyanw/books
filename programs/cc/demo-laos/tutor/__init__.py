"""AI Tutor 与 Agent 权限隔离（Phase 6）。

对应 docs/09 §6-8 与任务 #22。
Agent API：Read State（只读）→ Read Knowledge（只读）→ Generate Action → Submit。
写权限（Update State / Standard / Threshold）仅 Assessment Engine（V2.2 §20）。
LLM 负责解释与编排，不负责核心评价与决策。
"""
from .agent import TutorAgent, AgentPermissionError

__all__ = ["TutorAgent", "AgentPermissionError"]
