# 高中语文学习评价与认知诊断系统 — 研发任务跟踪

> 本文件由 todo 系统导出，用于离线持续跟踪任务状态。随研发进展更新各任务勾选与备注列。
>
> - 任务源：规划依据《研发落地详细工作规划 V1.0》+ 系统设计《学习评价与认知诊断系统 V2.2》评审采纳项
> - 状态：`[ ]` 待办 · `[~]` 进行中 · `[x]` 已完成 · `[!]` 阻塞
> - 更新方式：勾选 checkbox；在"备注"列填入产出物链接/阻塞原因/负责人

---

## 一、任务总表

| ID  | 主线 | 任务 | 前置依赖 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| #1  | A 启动 | Phase0 MVP领域边界与实验设计 | — | [x] | docs/01-mvp-scope-and-experiment-design.md |
| #2  | A 启动 | Phase0 五个Baseline对比框架 | — | [x] | docs/02-baseline-comparison-framework.md |
| #3  | B 设计 | 设计文档01 认知Ontology与Knowledge Graph | — | [x] | docs/03-ontology-and-knowledge-graph.md |
| #4  | B 设计 | 设计文档02 Student Cognitive State Schema | — | [x] | docs/04-student-cognitive-state-schema.md |
| #5  | B 设计 | 设计文档03 Evidence与学习事件Schema | — | [x] | docs/05-evidence-and-learning-event-schema.md |
| #6  | B 设计 | 设计文档04 Item与Q-Matrix规格 | — | [x] | docs/06-item-and-qmatrix-spec.md |
| #7  | B 设计 | 设计文档05 认知诊断引擎技术设计 | #4,#5 | [x] | docs/07-cognitive-diagnosis-engine.md |
| #8  | B 设计 | 设计文档06 自适应测评引擎技术设计 | #6 | [x] | docs/08-adaptive-assessment-engine.md |
| #9  | B 设计 | 设计文档07 学习决策与AI Tutor技术设计 | #7,#8 | [x] | docs/09-learning-decision-and-ai-tutor.md |
| #10 | B 设计 | 设计文档08 MVP工程启动包 | #3-#9 | [x] | docs/10-mvp-engineering-starter-pack.md |
| #11 | C 实现 | Phase1 标准体系与四层认知模型实现 | #3,#10 | [x] | schemas/ontology.py+ddl；repository/ontology_repo.py |
| #12 | C 实现 | Phase2 Evidence模型与Provenance实现 | #5,#10 | [x] | schemas/evidence.py+ddl；repository/evidence_repo.py；assessment/engine.get_provenance |
| #13 | C 实现 | Phase3 题库Schema与Q-Matrix实现 | #6,#10 | [x] | schemas/item.py+ddl；repository/item_repo.py |
| #14 | C 实现 | Phase3 第一批题目标注入库 | #13 | [ ] | 需语文教研专家+学生（合成题库见 mvp/closed_loop.py） |
| #15 | C 实现 | Phase4 统一学生状态模型实现 | #4,#10 | [x] | schemas/state.py+ddl；repository/state_repo.py |
| #16 | C 实现 | Phase4 CDM(DINA/GDINA)诊断实现 | #7,#12,#13 | [x] | cdm/dina.py+updater.py；tests/test_cdm.py |
| #17 | C 实现 | Phase4 IRT与层级测量模型实现 | #7,#13 | [x] | irt/model.py；tests/test_irt.py |
| #18 | C 实现 | Phase4 概率更新与状态融合实现 | #16,#17 | [x] | fusion/updater.py；tests/test_fusion.py |
| #19 | D 实现 | Phase5 自适应诊断引擎实现 | #8,#16,#17 | [x] | adaptive/engine.py；tests/test_adaptive.py |
| #20 | D 实现 | Phase5 诊断探针机制实现 | #8 | [x] | adaptive/probe.py；tests/test_adaptive.py |
| #21 | D 实现 | Phase6 学习决策引擎实现 | #9,#15 | [x] | learning/decision.py；tests/test_learning_tutor.py |
| #22 | D 实现 | Phase6 AI Tutor与Agent权限隔离实现 | #9 | [x] | tutor/agent.py；tests/test_learning_tutor.py |
| #23 | D 实现 | Phase7 Pre/Post与迁移验证实现 | #21,#22 | [x] | evaluation/transfer.py；tests/test_evaluation.py |
| #24 | D 实现 | Phase7 保持模型与干预效果评价实现 | #21 | [x] | evaluation/retention.py；tests/test_evaluation.py |
| #25 | E 治理 | 治理 Q矩阵工程与误标检测 | #13,#14 | [x] | governance/qmatrix.py；tests/test_governance.py |
| #26 | E 治理 | 治理 公平性与偏差审计 | #16,#17 | [x] | governance/fairness.py；tests/test_governance.py |
| #27 | E 治理 | 治理 隐私合规与审计证据链 | #12 | [x] | governance/privacy.py；tests/test_governance.py |
| #28 | E 治理 | 治理 核心实验验证体系 | #16,#17,#19 | [x] | experiments/core.py；tests/test_experiments.py |
| #29 | F 验收 | MVP 最小闭环打通 | #16-#19,#21-#23 | [x] | mvp/closed_loop.py（合成数据演示）；真实学生待人工实验 |
| #30 | F 验收 | MVP 五项验收指标 | #28,#29 | [x] | acceptance/metrics.py（合成数据 ALL PASS）；真实对照实验待人工 |

---

## 二、阶段进度

### 主线 A — 工程启动准备（Phase 0） ✅ 完成
- [x] #1 Phase0 MVP领域边界与实验设计
- [x] #2 Phase0 五个Baseline对比框架

### 主线 B — 8 份研发设计文档 ✅ 完成
- [x] #3 设计文档01 认知Ontology与Knowledge Graph
- [x] #4 设计文档02 Student Cognitive State Schema
- [x] #5 设计文档03 Evidence与学习事件Schema
- [x] #6 设计文档04 Item与Q-Matrix规格
- [x] #7 设计文档05 认知诊断引擎技术设计
- [x] #8 设计文档06 自适应测评引擎技术设计
- [x] #9 设计文档07 学习决策与AI Tutor技术设计
- [x] #10 设计文档08 MVP工程启动包

### 主线 C — 测量系统实现（Phase 1-4） ✅ 完成（#14 真实标注除外）
- [x] #11 Phase1 标准体系与四层认知模型实现 — schemas/ontology.py+ddl+repository
- [x] #12 Phase2 Evidence模型与Provenance实现 — schemas/evidence.py+ddl+repository+get_provenance
- [x] #13 Phase3 题库Schema与Q-Matrix实现 — schemas/item.py+ddl+repository
- [ ] #14 Phase3 第一批题目标注入库（需专家+学生；合成题库见 mvp/closed_loop.py）
- [x] #15 Phase4 统一学生状态模型实现 — schemas/state.py+ddl+repository
- [x] #16 Phase4 CDM(DINA/GDINA)诊断实现 — cdm/dina.py+updater.py
- [x] #17 Phase4 IRT与层级测量模型实现 — irt/model.py
- [x] #18 Phase4 概率更新与状态融合实现 — fusion/updater.py

### 主线 D — 闭环实现（Phase 5-7） ✅ 完成
- [x] #19 Phase5 自适应诊断引擎实现 — adaptive/engine.py
- [x] #20 Phase5 诊断探针机制实现 — adaptive/probe.py
- [x] #21 Phase6 学习决策引擎实现 — learning/decision.py
- [x] #22 Phase6 AI Tutor与Agent权限隔离实现 — tutor/agent.py
- [x] #23 Phase7 Pre/Post与迁移验证实现 — evaluation/transfer.py
- [x] #24 Phase7 保持模型与干预效果评价实现 — evaluation/retention.py

### 主线 E — 治理与验证（横切） ✅ 完成
- [x] #25 治理 Q矩阵工程与误标检测 — governance/qmatrix.py
- [x] #26 治理 公平性与偏差审计 — governance/fairness.py
- [x] #27 治理 隐私合规与审计证据链 — governance/privacy.py
- [x] #28 治理 核心实验验证体系 — experiments/core.py

### 主线 F — MVP 验收 ✅ 完成（合成数据；真实被试待人工实验）
- [x] #29 MVP 最小闭环打通 — mvp/closed_loop.py（合成数据演示）
- [x] #30 MVP 五项验收指标 — acceptance/metrics.py（合成数据 ALL PASS）

---

## 三、关键执行要点

1. **设计阶段已完成**：8 份设计文档（#3-#10）就绪，是工程实现的直接依据。
2. **下一步进入代码实现**：#11/#12/#13/#15 已解锁（前置均完成），可并行开工。
3. **测量壁垒关键路径**：#16/#17（CDM/IRT）需 #12/#13 就绪；#18 融合需 #16/#17。
4. **需真实人力的任务**：#14（专家标注）、#29（真实学生闭环）、#30（对照实验）无法在无团队/无被试环境完成。
5. **治理横切并行**：#25-#28 在各自前置就绪后并行。

---

## 四、MVP 验收口径（来自规划 §19）

合成数据演示结果（acceptance/metrics.py，n=12 学生）：

- [x] **Measurement Validity**：Test-Retest=0.745 / 分类一致=0.792 / Brier=0.109 — PASS
- [x] **Diagnostic Validity**：P=0.829 / R=0.829 / F1=0.829 / AUC=0.911 / Brier=0.125 — PASS（AUC 非唯一）
- [x] **Adaptive Efficiency**：固定20题AUC=0.925 vs 自适应18题AUC=0.988，减少10% — PASS
- [x] **Learning Effect**：Pre=0.489 / Post=0.778 / 保持=0.548 / 迁移=0.833 — PASS
- [x] **Decision Quality**：AI增益=0.308 vs 随机=0.007，Δ=+0.287 — PASS（最重要）

> 合成数据仅证明链路正确性与指标可计算性；真实阈值须大样本实证（V2.2 §5.1）。

---

## 五、变更记录

| 日期 | 变更 | 操作人 |
| --- | --- | --- |
| 2026-09-02 | 初始版本，导入 30 任务与依赖链 | Claude |
| 2026-09-02 | 完成 #1-#10：Phase 0 + 8 份设计文档，产出 docs/01-10 | Claude |
| 2026-09-02 | 交付 #11/#12/#13/#15 数据模型层：schemas/*.py + ddl.sql，已验证可导入；服务逻辑层待工程承接 | Claude |
| 2026-09-02 | 完成 #16-#24：CDM/IRT/融合/自适应/探针/学习决策/Tutor/迁移/保持 全部实现并测试通过 | Claude |
| 2026-09-02 | 完成 #25-#28：治理层（Q矩阵+公平性+隐私）+ 核心实验验证体系，测试通过 | Claude |
| 2026-09-02 | 完成 #29-#30：MVP 最小闭环（mvp/closed_loop.py）+ 五项验收（acceptance/metrics.py 合成数据 ALL PASS）；#14 真实标注待人工 | Claude |
| 2026-09-02 | 治理集成硬化：治理层接入 AssessmentEngine 写/读/导出全落审计链、假名化、LLM 导出去标识化（tests/test_governed_engine.py）；新增 Baseline A–E 可运行对比器（baselines/，docs/02 §4 实现）+ 端到端 run_demo.py；13 个测试套件全部通过 | Claude |
