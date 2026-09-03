"""Learning Assessment OS — 数据模型层（schemas）。

对应设计文档 docs/03..06。包含：
- ontology: LKG 四层认知模型（知识/认知过程/任务能力/核心素养）+ 关系
- state:    学生认知状态四层（核心/动态/诊断/不确定性）+ 融合输出
- evidence: 证据对象 + 四层分层 + 证据不足机制
- item:     题目 + Q 矩阵 + 质量模型 + 标注流水线
- ddl.sql:  PostgreSQL 持久化 DDL

约束（V2.2 评审采纳）：
- 写权限仅 Assessment Engine 持有（Agent 无写权限）
- 可识别性：未达门槛只输出 insufficient_evidence
- Q 矩阵治理优先级高于题目参数估计
"""
