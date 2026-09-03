# 10 MVP 工程启动包 V1.0

> 对应任务 #10（设计文档08）。把前 7 份设计转换成仓库脚手架与 Epic/Feature/Story/Task 拆解。第一阶段不做：全学科、复杂 Agent、大模型微调、漂亮前端；优先 RAG + Prompt + Tool Calling + Structured Output。

## 1. 仓库结构

```
laos/
├── docs/                # 设计文档（已产出 01-09）
├── ontology/            # LKG：知识/认知/任务/素养节点与关系
├── schemas/             # State / Evidence / Item 对象定义
├── item-bank/           # 题库 + Q 矩阵 + 标注工具
├── evidence/            # 证据采集管道 + Provenance
├── cdm/                 # DINA/GDINA + 概率更新
├── irt/                 # IRT + 层级测量模型
├── adaptive/            # 自适应选题 + 探针
├── learning/            # 学习决策 + 效用模型
├── tutor/               # AI Tutor + Agent 权限边界
├── evaluation/          # Baseline + 四类实验 + 验收指标
├── tests/               # 单元/集成/回归
└── deployment/          # 部署 + MLOps
```

## 2. 技术栈（MVP 建议）

| 层 | 选型 |
| --- | --- |
| 核心数据 | PostgreSQL |
| 认知关系 | PostgreSQL 邻接表（MVP），后续可迁 Graph DB |
| 实时状态 | Redis |
| 对象存储 | OSS/S3（试卷、作文、音视频） |
| 向量库 | 向量库（知识资源检索） |
| 算法服务 | Python（CDM/IRT/KT/Adaptive） |
| AI 层 | LLM Gateway + RAG + Tool Gateway |
| 前端 | 先最小（学生/教师端 MVP） |

## 3. 横向贯穿组件

```
Security / Privacy / Audit / Versioning / MLOps / Observability
```

## 4. Epic → Feature → Story → Task 拆解

### Epic 01：标准体系（Phase1，任务 #11）
- ST-001 标准 Ontology
- ST-002 核心素养模型
- ST-003 任务能力模型
- ST-004 认知过程模型
- ST-005 知识 Ontology
- ST-006 映射矩阵
- ST-007 评价规则
- ST-008 标准版本等值接口（V2.2 §4.3）

### Epic 02：题库（Phase3，任务 #13/#14/#25）
- ITEM-001 Item Schema
- ITEM-002 Q-Matrix
- ITEM-003 Item 标注工具
- ITEM-004 Item 版本管理
- ITEM-005 Item 质量模型（12 项）
- ITEM-006 曝光控制
- ITEM-007 泄露检测
- ITEM-008 Q 矩阵验证（GDI/stepwise，V2.2 §31.2）
- ITEM-009 标注流水线（LLM预标注→众教师→专家抽检，V2.2 §31.3）

### Epic 03：Evidence（Phase2，任务 #12/#27）
- EV-001 Response Event
- EV-002 Score Event
- EV-003 Probe Event
- EV-004 Transfer Event
- EV-005 Teacher Evidence
- EV-006 Anchor Evidence
- EV-007 Provenance
- EV-008 证据不足机制
- EV-009 隐私合规与脱敏（V2.2 §35 风险8）

### Epic 04：认知诊断（Phase4，任务 #15-#18）
- CDM-001 DINA
- CDM-002 GDINA（连续化）
- CDM-003 IRT（含适用边界）
- CDM-004 后验更新
- CDM-005 不确定性
- CDM-006 错误归因
- CDM-007 State API（写权限隔离）
- CDM-008 分层贝叶斯融合（V2.2 §9.5）
- CDM-009 可识别性/冷启动（V2.2 §9.6）

### Epic 05：Adaptive Testing（Phase5，任务 #19/#20）
- AT-001 候选选择
- AT-002 Information Gain
- AT-003 Q-Matrix 约束
- AT-004 难度约束
- AT-005 曝光控制（Sympson-Hetter）
- AT-006 终止规则
- AT-007 诊断探针
- AT-008 状态快照隔离（V2.2 §12.2）

### Epic 06：Learning Engine（Phase6-7，任务 #21-#24）
- LE-001 Gap Detection
- LE-002 Learning Utility（含 MAB 探索）
- LE-003 Learning Plan（动态路径）
- LE-004 Intervention
- LE-005 熔断机制
- LE-006 Retest
- LE-007 Transfer（外部非同源材料）
- LE-008 Retention（个性化保持模型）

### Epic 07：AI Tutor（Phase6，任务 #22）
- AI-001 LLM Gateway
- AI-002 RAG
- AI-003 来源引用
- AI-004 Claim Verification（NLI/事实核验）
- AI-005 Tutor Agent
- AI-006 练习生成器
- AI-007 解释生成器
- AI-008 Agent 权限边界
- AI-009 LLM 离线质量门（V2.2 §21）

### Epic 08：Evaluation（任务 #2/#28/#30）
- EVL-001 Baseline A-E
- EVL-002 实验1 诊断有效性
- EVL-003 实验2 测评效率
- EVL-004 实验3 学习增益
- EVL-005 实验4 外部效度
- EVL-006 五项验收

### Epic 09：治理（任务 #25/#26/#27）
- GOV-001 Q 矩阵治理
- GOV-002 公平性/偏差审计（DIF、subgroup 校准）
- GOV-003 隐私合规
- GOV-004 审计证据链

## 5. MVP 最小闭环（任务 #29）

```
学生 → 10~20 道诊断题 → Evidence → CDM → Student State
→ Top 3 认知缺口 → 7 天学习任务 → 训练 → 迁移测试
→ 更新 State → 成长报告
```

> 此链不能稳定运行则不扩展。

## 6. 第一条要打通的技术链

> 100 个真实知识节点 + 300~500 道高质量题目 + 50~100 名学生
> → Evidence → CDM/IRT → Student State → Adaptive Diagnosis → 学习干预 → 迁移测试

先用小规模真实实验证明**测量有效性与学习闭环**，再扩展到完整高中语文。

## 7. MVP 验收（任务 #30，见 TODO §四）

- Measurement Validity
- Diagnostic Validity
- Adaptive Efficiency
- Learning Effect
- Decision Quality（AI 个性化 vs 随机练题）

## 8. 启动顺序

1. Phase 0（#1/#2）✅ 已完成
2. 8 份设计文档（#3-#10）✅ 已完成
3. 进入实现：#11/#12/#13 并行 → #14/#15 → #16/#17 → #18 → #19-#24 → #29 → #30

> 设计文档已就绪，下一步进入代码实现（需工程团队承接）。
