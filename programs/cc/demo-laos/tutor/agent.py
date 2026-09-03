"""Tutor Agent——内容编排与解释层。

权限边界（V2.2 §20）：只读状态/知识；不得修改 Mastery/Threshold/Standard。
写状态必须经 AssessmentEngine（引擎层强制，非 Prompt 约束）。
"""
from __future__ import annotations

from schemas.state import StudentCognitiveState


class AgentPermissionError(PermissionError):
    """Agent 尝试越权写时抛出。"""


class TutorAgent:
    """AI Tutor。MVP：确定性编排 + 可接 LLM Gateway。"""

    # Agent 禁止的操作（docs/09 §6）
    FORBIDDEN = {"update_mastery", "update_threshold", "update_standard",
                 "set_final_score", "declare_mastered"}

    def __init__(self, assessment_engine=None) -> None:
        self.assessment_engine = assessment_engine  # 只读引用；写经它

    # ---- 只读 ----
    def read_state(self, student_id: str, node_id: str) -> StudentCognitiveState | None:
        if self.assessment_engine is None:
            return None
        return self.assessment_engine.get_state(student_id, node_id)

    def explain_gap(self, state: StudentCognitiveState) -> str:
        """LLM 负责解释（docs/09 §6），不修改状态。"""
        return (f"节点 {state.node_id}：mastery={state.core.mastery:.2f}，"
                f"应用={state.core.application:.2f}，迁移={state.core.transfer:.2f}，"
                f"置信={state.uncertainty.confidence:.2f}。"
                f"主要错误：{state.diagnostic.misconception or '未归因'}。")

    def generate_action(self, state: StudentCognitiveState) -> str:
        """LLM 生成学习内容/讲解动作（不写状态）。"""
        if state.core.mastery < 0.5:
            return f"建议：先讲 {state.node_id} 基础概念 + 典型语境例题"
        if state.core.transfer < 0.5:
            return f"建议：{state.node_id} 对比辨析 → 陌生文本迁移题"
        return f"建议：{state.node_id} 综合训练 + 间隔复习"

    # ---- 越权保护 ----
    def update_mastery(self, *args, **kwargs):
        raise AgentPermissionError("Agent 不得修改 Mastery（V2.2 §20）")

    def update_threshold(self, *args, **kwargs):
        raise AgentPermissionError("Agent 不得修改 Threshold")

    def declare_mastered(self, *args, **kwargs):
        raise AgentPermissionError("Agent 不得自行宣布已掌握")

    def submit_learning(self, student_id: str, action: str) -> str:
        """提交学习动作（不写状态；学习产生新证据后由 AssessmentEngine 更新）。"""
        return f"已编排学习动作：{action}（状态更新由后续证据触发，非 Agent 写入）"
