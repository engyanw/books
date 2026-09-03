"""State 仓储——学生认知状态存储。"""
from __future__ import annotations
from schemas.state import StudentCognitiveState, StateStatus


class StateRepository:
    def __init__(self) -> None:
        # (student_id, node_id) -> state
        self._states: dict[tuple[str, str], StudentCognitiveState] = {}

    def get(self, student_id: str, node_id: str) -> StudentCognitiveState | None:
        return self._states.get((student_id, node_id))

    def put(self, state: StudentCognitiveState) -> None:
        """直接写入。仅 AssessmentEngine 应调用（V2.2 §20 权限边界）。"""
        self._states[(state.student_id, state.node_id)] = state

    def all_for_student(self, student_id: str) -> list[StudentCognitiveState]:
        return [s for (sid, _), s in self._states.items() if sid == student_id]

    def cold_start_state(
        self, student_id: str, node_id: str, node_version: str, domain: str
    ) -> StudentCognitiveState:
        """冷启动状态（V2.2 §9.6）：宽置信区间、status=cold_start。"""
        return StudentCognitiveState(
            student_id=student_id,
            node_id=node_id,
            node_version=node_version,
            domain=domain,
            status=StateStatus.COLD_START,
        )
