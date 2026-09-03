# 《语文认知Ontology与Knowledge Graph设计 V1.0》

**文档状态：研发基线版**
**适用系统：高中语文学习评价与认知诊断系统**
**版本：V1.0**
**核心定位：Cognitive Ontology + Knowledge Graph + Evidence Graph 的统一语义基础设施**

---

# 1. 文档目标

## 1.1 建设目标

本系统需要解决的不是传统题库中的：

> “这道题属于哪个知识点？”

而是建立：

> **学生究竟需要掌握什么、通过什么任务表现出来、需要调用什么认知过程、什么证据可以证明其掌握、错误意味着什么，以及这些能力如何进一步映射到语文核心素养。**

因此，本Ontology必须支撑：

```text
课程标准
   ↓
评价标准
   ↓
核心素养
   ↓
任务能力
   ↓
认知过程
   ↓
知识
   ↓
题目 / 任务
   ↓
学生作答
   ↓
学习证据
   ↓
认知状态
   ↓
学习决策
```

最终成为整个 Learning Assessment OS 的语义底座。

---

# 2. 设计原则

## 2.1 标准与模型分离

必须遵循：

```text
Standards
    ↓
Ontology
    ↓
Measurement Model
    ↓
Decision Model
```

不能让：

```text
LLM
```

直接定义：

```text
什么是掌握
什么是优秀
什么是达标
```

---

## 2.2 知识与能力分离

例如：

> “之”是一个知识对象。

但：

> “能够在不同语境中正确判断‘之’的用法”

属于能力表现。

因此：

```text
Knowledge ≠ Capability
```

---

## 2.3 认知过程与任务能力分离

例如：

```text
文言文阅读
```

是任务能力。

而：

```text
理解
分析
推断
迁移
```

属于认知过程。

同一个认知过程可以存在于多个任务中。

---

## 2.4 核心素养不直接等价于单个知识点

例如：

```text
虚词“之”
```

不能直接推出：

```text
语言建构与运用 = 0.86
```

而应该通过：

```text
Knowledge
 → Cognitive Process
 → Task Capability
 → Evidence
 → Core Literacy
```

形成层级证据链。

---

## 2.5 知识图谱与资源库分离

不能把：

```text
教材
题目
讲义
视频
作文
```

全部直接当成Ontology节点。

应该：

```text
Ontology / Knowledge Graph
        ↕
Content / Resource Store
```

通过Typed Relation关联。

---

# 3. 总体Ontology架构

系统采用五层核心语义架构：

```text
┌──────────────────────────────────┐
│ L5 Goal / Standard               │
│ 学习目标 / 课程标准 / 学业质量    │
└────────────────┬─────────────────┘
                 ↓
┌──────────────────────────────────┐
│ L4 Core Literacy                 │
│ 语文核心素养                      │
└────────────────┬─────────────────┘
                 ↓
┌──────────────────────────────────┐
│ L3 Task Capability               │
│ 任务能力                          │
└────────────────┬─────────────────┘
                 ↓
┌──────────────────────────────────┐
│ L2 Cognitive Process             │
│ 认知过程                          │
└────────────────┬─────────────────┘
                 ↓
┌──────────────────────────────────┐
│ L1 Knowledge                     │
│ 语文知识                          │
└──────────────────────────────────┘
```

同时建立三个横向对象层：

```text
              ┌───────────────┐
              │ Assessment    │
              │ 评价对象       │
              └───────┬───────┘
                      │
┌─────────────┐       ↓       ┌─────────────┐
│ Content     │ ← Evidence → │ Learner     │
│ 内容资源     │              │ 学习者       │
└─────────────┘              └─────────────┘
```

---

# 4. Ontology顶层对象模型

定义以下核心Class：

```text
Standard
Goal
CoreLiteracy
TaskCapability
CognitiveProcess
Knowledge
Concept
Rule
Procedure
Misconception
Item
Assessment
Probe
Evidence
LearningResource
Intervention
TransferTask
Learner
LearnerState
Rubric
Skill
```

其中：

## 4.1 标准类

```text
Standard
Goal
AcademicQualityLevel
AssessmentRequirement
```

---

## 4.2 认知类

```text
CoreLiteracy
TaskCapability
CognitiveProcess
Knowledge
Concept
Rule
Procedure
Skill
```

---

## 4.3 评价类

```text
Item
Assessment
Probe
Rubric
Evidence
TransferTask
```

---

## 4.4 学习类

```text
LearningResource
Intervention
LearningAction
LearningStrategy
```

---

## 4.5 学习者类

```text
Learner
LearnerState
MasteryState
ErrorState
TransferState
RetentionState
UncertaintyState
```

---

# 5. L5：标准与目标Ontology

## 5.1 Standard

```yaml
Standard:
  id:
  name:
  type:
  source:
  source_version:
  grade_scope:
  subject:
  description:
  requirement:
  evidence_requirement:
  effective_date:
  status:
```

Standard Type：

```text
CURRICULUM_STANDARD
ACADEMIC_QUALITY
ASSESSMENT_REQUIREMENT
GAOKAO_REQUIREMENT
SCHOOL_REQUIREMENT
SYSTEM_RULE
```

---

# 5.2 标准必须版本化

例如：

```text
STANDARD_CN_2026
```

不能直接覆盖旧版本。

采用：

```text
Standard V1
Standard V2
```

保证历史考试结果可重放。

---

# 5.3 Goal

Goal表示学生希望达到的学习目标。

例如：

```text
GOAL_GAO_KAO
GOAL_TERM_EXAM
GOAL_UNIT_MASTER
GOAL_TRANSFER
GOAL_LITERACY
```

---

# 6. L4：核心素养Ontology

系统保留四个核心素养维度：

```text
CL01 语言建构与运用
CL02 思维发展与提升
CL03 审美鉴赏与创造
CL04 文化传承与理解
```

定义：

```yaml
CoreLiteracy:
  id:
  name:
  definition:
  standard_refs:
  evidence_requirements:
  task_capabilities:
```

---

# 6.1 核心素养不是简单评分标签

例如：

```text
CL01 = 语言建构与运用
```

不是：

```text
0.86
```

这种数字本身没有意义。

系统必须维护：

```text
P(CL01 | Evidence)
```

或者更准确地说：

> 与该素养表现相关的证据支持程度。

如果未来建立成熟的层级测量模型，再将其估计为latent ability。

---

# 7. L3：任务能力Ontology

定义五类核心任务能力：

```text
TC01 文言文阅读
TC02 现代文阅读
TC03 古诗词鉴赏
TC04 写作
TC05 综合语言运用
```

---

# 7.1 TaskCapability Schema

```yaml
TaskCapability:
  id:
  name:
  definition:
  task_type:
  cognitive_processes:
  knowledge_requirements:
  literacy_refs:
  evidence_requirements:
```

---

# 7.2 任务能力不是知识点集合

例如：

```text
文言文阅读
```

需要：

```text
知识
+
理解
+
分析
+
推断
+
语境整合
+
迁移
```

因此：

```text
TaskCapability
  requires
    Knowledge
  requires
    CognitiveProcess
```

---

# 8. L2：认知过程Ontology

建议定义：

```text
CP01 识别
CP02 理解
CP03 分析
CP04 推理
CP05 评价
CP06 表达
CP07 迁移
```

---

# 8.1 认知过程层级

```text
识别
 ↓
理解
 ↓
分析
 ↓
推理
 ↓
评价
 ↓
迁移
```

但实际任务允许非线性组合。

例如：

```text
作文
```

可能：

```text
理解
+
分析
+
评价
+
表达
```

---

# 8.2 CognitiveProcess Schema

```yaml
CognitiveProcess:
  id:
  name:
  definition:
  prerequisite_processes:
  observable_behaviors:
  evidence_types:
  difficulty_factors:
```

---

# 9. L1：知识Ontology

这是整个系统最重要的Ontology之一。

不能只建立：

```text
知识点列表
```

而应该建立：

> **Knowledge Concept Model**

---

# 9.1 Knowledge类型

建议至少分成：

```text
KConcept
KRule
KProcedure
KText
KContext
KCulture
KExpression
KStrategy
```

---

# 9.2 KConcept

例如：

```text
虚词
之
其
而
以
```

---

# 9.3 KRule

例如：

```text
宾语前置规则
被动句规则
判断句规则
省略规则
```

---

# 9.4 KProcedure

例如：

```text
文言文句意翻译步骤
诗歌意象分析步骤
论证结构识别步骤
作文审题步骤
```

这类对象尤其重要，因为：

> 学生“知道知识”不代表“会执行解题过程”。

---

# 9.5 KText

例如：

```text
《劝学》
《师说》
《赤壁赋》
```

文本对象不应该和知识点混为一谈。

它是：

> Knowledge Resource / Textual Artifact

可以关联大量知识。

---

# 9.6 KContext

例如：

```text
历史背景
作者背景
时代语境
文学流派
```

---

# 9.7 KCulture

例如：

```text
儒家思想
士人文化
传统礼制
```

---

# 10. Knowledge Schema

统一定义：

```yaml
Knowledge:
  id:
  type:
  name:
  definition:
  aliases:
  grade_scope:
  prerequisite_ids:
  related_ids:
  parent_ids:
  standard_refs:
  capability_refs:
  cognitive_refs:
  literacy_refs:
  misconception_ids:
  evidence_requirements:
  resource_refs:
  status:
  version:
```

---

# 11. 知识关系模型

不能只使用：

```text
A → B
```

必须采用Typed Relation。

---

## 11.1 prerequisite_of

```text
K01 prerequisite_of K02
```

表示：

> K01是学习K02的重要前置知识。

---

## 11.2 part_of

```text
K01 part_of K02
```

表示：

> K01属于K02。

---

## 11.3 equivalent_to

表示同义/等价概念。

---

## 11.4 contrast_with

表示容易混淆的知识。

例如：

```text
之
vs
其
```

---

## 11.5 applies_to

表示规则适用于某知识或任务。

---

## 11.6 exemplified_by

表示概念由某文本/题目体现。

---

## 11.7 requires

表示任务需要某知识。

---

## 11.8 supports

表示知识支持某能力。

---

# 12. 概率关系

知识图谱不仅有：

```text
Semantic Relation
```

还需要：

```text
Probabilistic Relation
```

例如：

```text
K01 → CP02
P(CP02 | K01) = 0.82
```

但必须强调：

> 该概率是模型参数，而不是Ontology语义事实。

因此：

```text
Ontology Relation
```

与：

```text
Measurement Parameter
```

必须分离存储。

---

# 13. 认知图谱整体结构

最终形成：

```text
                Goal
                 │
              Standard
                 │
           Core Literacy
                 │
          Task Capability
                 │
          Cognitive Process
                 │
               Skill
                 │
             Knowledge
                 │
        ┌────────┼────────┐
        ↓        ↓        ↓
       Item    Resource  Probe
        │        │        │
        └────────┼────────┘
                 ↓
              Evidence
                 ↓
             Learner
                 ↓
           Learner State
```

---

# 14. Skill：连接知识与能力的关键对象

建议增加：

> Skill

因为：

```text
Knowledge
```

和：

```text
Task Capability
```

之间缺少一个重要中间层。

例如：

```text
Skill:
能够根据语境判断“之”的具体用法
```

它不是单纯知识，也不是完整任务能力。

因此：

```text
Knowledge
   ↓
Skill
   ↓
Task Capability
```

这是未来认知诊断最重要的对象之一。

---

# 15. Skill Schema

```yaml
Skill:
  id:
  name:
  definition:
  knowledge_requirements:
  cognitive_requirements:
  capability_refs:
  literacy_refs:
  observable_behaviors:
  assessment_methods:
  misconception_refs:
```

例如：

```yaml
id: SK_CN_CLASSICAL_ZHI_01

name: 根据语境判断“之”的用法

knowledge_requirements:
  - K_ZHI

cognitive_requirements:
  - CP02
  - CP03

capability_refs:
  - TC01
```

---

# 16. Misconception：错误认知模型

传统题库只记录：

```text
答错
```

本系统需要记录：

> 为什么错。

定义：

```yaml
Misconception:
  id:
  name:
  description:
  related_knowledge:
  triggering_conditions:
  observable_patterns:
  diagnostic_probes:
  remediation_strategies:
```

---

# 16.1 错误类型

建议建立：

```text
M01 知识缺失
M02 概念混淆
M03 规则误用
M04 语境误判
M05 认知过程错误
M06 审题错误
M07 信息提取错误
M08 推理错误
M09 表达错误
M10 迁移失败
M11 粗心 / 执行失误
M12 时间管理问题
```

注意：

> 错误分类是诊断假设，不应直接视为因果结论。

---

# 17. Item Ontology

题目是：

> Measurement Instrument

不是知识节点。

---

# 17.1 Item Schema

```yaml
Item:
  id:
  version:
  type:
  stem:
  options:
  answer:
  score_rule:

  knowledge_refs:
  skill_refs:
  cognitive_refs:
  capability_refs:
  literacy_refs:

  q_matrix:
  diagnostic_targets:
  misconception_targets:

  difficulty:
  discrimination:
  guessing:

  exposure_count:
  leakage_risk:

  source:
  license:
  status:
```

---

# 17.2 Q-Matrix

每道题建立：

```text
Item × Skill
```

矩阵。

例如：

```text
             SK01 SK02 SK03 SK04
ITEM001       1    0    0    0
ITEM002       1    1    0    0
ITEM003       0    1    1    0
ITEM004       0    1    1    1
```

---

# 18. Item与Knowledge不是一对一

一个题目可以：

```text
ITEM001
 ├── K01
 ├── K03
 └── K08
```

因此：

```text
Item
 └─ assesses
       ├─ Knowledge
       ├─ Skill
       └─ CognitiveProcess
```

---

# 19. Assessment Ontology

定义：

```text
Assessment
```

作为一次正式测评。

包括：

```text
Entry Assessment
Unit Assessment
Stage Assessment
Anchor Assessment
Transfer Assessment
```

---

# 19.1 Assessment Schema

```yaml
Assessment:
  id:
  type:
  blueprint:
  standard_version:
  item_pool_version:
  scoring_version:
  duration:
  stopping_rule:
  adaptive:
  status:
```

---

# 20. Diagnostic Probe

Probe不是普通题。

定义：

> 用于减少特定认知状态不确定性的诊断性任务。

---

# 20.1 Probe类型

```text
P01 Recall Probe
P02 Discrimination Probe
P03 Explanation Probe
P04 Transfer Probe
```

---

# 20.2 Probe Schema

```yaml
Probe:
  id:
  target_skill:
  target_misconception:
  information_objective:
  response_type:
  scoring_rule:
  expected_information_gain:
```

---

# 21. Evidence Ontology

这是系统的核心。

定义：

> Evidence = 支持或反驳某一认知状态假设的可追溯观测。

---

# 21.1 Evidence类型

```text
DirectEvidence
BehaviorEvidence
DiagnosticEvidence
TransferEvidence
TeacherEvidence
AnchorEvidence
```

---

# 21.2 Evidence Schema

```yaml
Evidence:
  id:
  learner_id:
  source_type:
  source_id:

  observed_at:
  response:
  score:

  item_version:
  rubric_version:
  model_version:

  knowledge_refs:
  skill_refs:
  cognitive_refs:
  capability_refs:

  error_refs:
  confidence:

  provenance:
  validity:
```

---

# 22. Evidence Provenance

每条Evidence必须能够回答：

```text
谁？
何时？
通过什么任务？
使用哪个版本？
由谁评分？
依据什么规则？
产生什么观察？
```

例如：

```text
EV001
 ├── learner = S001
 ├── item = ITEM102
 ├── item_version = V3
 ├── scoring_version = R2
 ├── response = B
 ├── score = 1
 ├── timestamp = ...
 └── assessment = A2026_01
```

---

# 23. Learner Ontology

定义：

```yaml
Learner:
  id:
  grade:
  enrollment:
  goals:
  assessment_history:
  state_ref:
```

这里不存储不必要的敏感个人信息。

---

# 24. LearnerState

LearnerState不是永久属性，而是：

> 某一时间点、基于某一组Evidence估计出的认知状态。

---

# 24.1 State Schema

```yaml
LearnerState:
  learner_id:
  target_id:
  target_type:

  mastery:
  application:
  transfer:

  stability:
  forgetting_risk:

  error_distribution:

  uncertainty:
  evidence_count:

  estimated_at:
  model_version:
```

---

# 24.2 State必须可重建

例如：

```text
State @ T1
```

必须可以通过：

```text
Evidence E1...En
+
Model V1.2
```

重新计算出来。

---

# 25. 不确定性模型

不建议把：

```text
confidence = 0.88
```

简单理解成：

> “系统88%确定学生会。”

更准确地保存：

```text
Posterior Distribution
```

例如：

```text
Mastery ~ Beta(18,4)
```

或者：

```text
P(Mastery=1)=0.86
```

同时保存：

```text
credible_interval
evidence_count
model_version
```

---

# 26. 认知状态对象关系

```text
Learner
   │
   ↓
LearnerState
   │
   ├── target → Knowledge
   ├── target → Skill
   ├── target → Capability
   └── target → Literacy
```

但不同层级的State估计必须有明确的Measurement Model。

---

# 27. LearningResource

资源不属于核心Ontology知识节点，而是内容资产。

例如：

```text
教材
讲义
视频
例题
知识卡片
微课
文章
```

Schema：

```yaml
LearningResource:
  id:
  type:
  title:
  source:
  license:
  content_location:
  knowledge_refs:
  skill_refs:
  capability_refs:
  cognitive_refs:
  difficulty:
  quality_score:
  version:
```

---

# 28. Intervention

定义：

> 针对特定认知缺口设计的学习行为。

例如：

```text
解释
示例
对比
练习
提示
反例
迁移任务
复习
```

Schema：

```yaml
Intervention:
  id:
  target_skill:
  target_misconception:
  intervention_type:
  prerequisite:
  expected_effect:
  evidence_requirement:
```

---

# 29. Intervention与LLM的关系

LLM可以：

```text
生成解释
选择例子
组织练习
生成对话
```

但不能直接：

```text
修改LearnerState
```

结构必须是：

```text
LLM
 ↓
Proposed Learning Action
 ↓
Decision Engine
 ↓
Intervention
 ↓
Learner
 ↓
Evidence
 ↓
Assessment Engine
 ↓
LearnerState Update
```

---

# 30. TransferTask

迁移任务是整个系统的重要对象。

定义：

> 在改变表面形式、材料、情境或任务组合后，要求学生调用相同或相关认知结构解决问题的任务。

---

# 30.1 Transfer类型

```text
T1 Same Skill / New Item
T2 Same Skill / New Context
T3 Cross-Context Transfer
T4 Integrated Transfer
```

---

# 31. Rubric Ontology

尤其用于作文和开放性任务。

```yaml
Rubric:
  id:
  version:
  dimensions:
  levels:
  scoring_rules:
  evidence_requirements:
  anchor_examples:
```

---

# 32. 作文Rubric

例如：

```text
立意
结构
论证
材料使用
语言
表达
文化理解
```

但这些维度必须与：

```text
Core Literacy
Task Capability
Cognitive Process
```

建立明确映射。

---

# 33. Ontology关系全集

建议第一版定义以下关系：

| Relation          | 含义     |
| ----------------- | ------ |
| part_of           | 属于     |
| parent_of         | 上位概念   |
| prerequisite_of   | 前置     |
| requires          | 需要     |
| supports          | 支持     |
| assesses          | 测量     |
| demonstrates      | 表现     |
| applies_to        | 适用     |
| exemplified_by    | 例示     |
| related_to        | 相关     |
| contrast_with     | 对比     |
| confusable_with   | 易混淆    |
| causes_hypothesis | 错误因果假设 |
| indicates         | 指示     |
| mitigates         | 干预缓解   |
| transfers_to      | 迁移到    |
| evidenced_by      | 证据支持   |
| derived_from      | 派生自    |
| aligned_to        | 对齐     |
| generated_from    | 生成自    |
| version_of        | 版本关系   |

其中：

> `causes_hypothesis` 必须明确是“假设”，不能作为已验证因果关系。

---

# 34. 关系必须带Metadata

不能只保存：

```text
A → B
```

建议：

```yaml
Relation:
  source:
  target:
  relation_type:
  confidence:
  source_type:
  evidence_refs:
  valid_from:
  valid_to:
  version:
  status:
```

例如：

```text
K01 prerequisite_of K02

confidence = 0.82
source = expert_annotation
version = ONTOLOGY_V1
```

---

# 35. 认知图谱与概率图谱分离

建议采用：

## Semantic Graph

存：

```text
概念
层级
语义关系
标准映射
```

## Probabilistic Graph

存：

```text
P(Skill | Knowledge)
P(Response | Skill)
P(Capability | Skill)
```

两者通过：

```text
Entity ID
```

关联。

不要把：

> Ontology事实

和：

> 统计参数

混在一起。

---

# 36. 图谱存储架构

MVP阶段不建议立即引入复杂Graph DB。

建议：

```text
PostgreSQL
 ├── ontology_entity
 ├── ontology_relation
 ├── standard
 ├── knowledge
 ├── skill
 ├── item
 ├── evidence
 └── learner_state
```

如果关系规模快速增长，再引入：

```text
Neo4j / NebulaGraph
```

或者专用Graph Store。

---

# 37. 推荐逻辑数据模型

```text
ontology_entity
----------------
entity_id
entity_type
name
definition
version
status

ontology_relation
-----------------
relation_id
source_id
target_id
relation_type
confidence
source
version

measurement_parameter
---------------------
parameter_id
model_type
source_id
target_id
parameter_name
parameter_value
model_version
```

形成：

```text
Semantic Layer
      ↓
Relation Layer
      ↓
Measurement Layer
```

---

# 38. Knowledge Graph API

第一版至少提供：

### 查询知识

```http
GET /knowledge/{id}
```

### 查询前置知识

```http
GET /knowledge/{id}/prerequisites
```

### 查询相关技能

```http
GET /knowledge/{id}/skills
```

### 查询题目

```http
GET /knowledge/{id}/items
```

### 查询诊断Probe

```http
GET /skill/{id}/probes
```

### 查询干预资源

```http
GET /skill/{id}/interventions
```

---

# 39. Learner Graph API

### 获取学生状态

```http
GET /learner/{id}/state
```

### 获取认知缺口

```http
GET /learner/{id}/gaps
```

### 获取证据

```http
GET /learner/{id}/evidence
```

### 获取某知识诊断链

```http
GET /learner/{id}/knowledge/{knowledge_id}/diagnosis
```

返回：

```text
Knowledge
 ↓
Evidence
 ↓
Posterior
 ↓
Uncertainty
 ↓
Misconception
 ↓
Recommended Intervention
```

---

# 40. 示例：建立“之”的完整认知模型

例如：

```text
K_CN_ZHI
```

定义：

> 文言虚词“之”的常见用法及语境判断。

关系：

```text
K_CN_ZHI
 ├── prerequisite_of → K_CN_SYNTAX_BASIC
 ├── contrast_with → K_CN_QI
 ├── supports → SK_ZHI_CONTEXT_IDENTIFICATION
 └── part_of → K_CN_FUNCTION_WORD
```

Skill：

```text
SK_ZHI_CONTEXT_IDENTIFICATION
```

认知过程：

```text
CP02 理解
CP03 分析
CP07 迁移
```

任务：

```text
TC01 文言文阅读
```

核心素养：

```text
CL01 语言建构与运用
CL02 思维发展与提升
```

形成：

```text
             CL01
               ↑
             TC01
               ↑
      CP02 + CP03 + CP07
               ↑
 SK_ZHI_CONTEXT_IDENTIFICATION
               ↑
           K_CN_ZHI
```

---

# 41. 题目映射示例

```text
ITEM_ZHI_001
```

测量：

```text
K_CN_ZHI
SK_ZHI_CONTEXT_IDENTIFICATION
CP02
TC01
```

Q-Matrix：

```text
K_ZHI = 1
SK_ZHI_CONTEXT = 1
```

如果答错：

```text
Evidence
 ↓
Candidate Misconceptions
 ├─ M01 Knowledge Deficit
 ├─ M02 Function Confusion
 └─ M04 Context Misjudgment
```

系统不能直接选择其中一个。

需要：

```text
Diagnostic Probe
 ↓
Posterior Update
```

---

# 42. 完整认知诊断链

最终：

```text
Question
   ↓
Response
   ↓
Evidence
   ↓
Q-Matrix
   ↓
CDM / IRT
   ↓
Skill Posterior
   ↓
Knowledge State
   ↓
Task Capability Evidence
   ↓
Core Literacy Evidence
```

---

# 43. Knowledge Graph与CDM的接口

CDM不能直接读取所有图谱信息。

建立：

```text
Graph Adapter
```

负责：

```text
Ontology
 ↓
Assessment Blueprint
 ↓
Q-Matrix
 ↓
CDM
```

例如：

```python
item.skills()
item.knowledge_requirements()
item.cognitive_processes()
```

CDM只消费标准化后的：

```text
Q-Matrix
Evidence
```

---

# 44. Knowledge Graph与Adaptive Testing接口

Adaptive Engine需要：

```text
Candidate Items
Target Skills
Prerequisites
Difficulty
Information Gain
Exposure
```

因此：

```text
Graph
 ↓
Candidate Generation
 ↓
Measurement Model
 ↓
Information Gain
 ↓
Constraint Solver
```

---

# 45. Knowledge Graph与Learning Engine接口

Learning Engine需要：

```text
Current State
Prerequisite Graph
Misconception Graph
Resource Graph
Intervention Graph
```

例如：

```text
Skill A 掌握不足
       ↓
Prerequisite
       ↓
Skill B
       ↓
Resource
       ↓
Intervention
```

---

# 46. 图谱闭环

整个系统形成：

```text
         ┌──────────────┐
         │   Ontology   │
         └──────┬───────┘
                ↓
             Item
                ↓
           Assessment
                ↓
             Evidence
                ↓
          Cognitive State
                ↓
          Learning Decision
                ↓
           Intervention
                ↓
              Task
                ↓
             Evidence
                │
                └──────────────→ State Update
```

---

# 47. 版本治理

Ontology必须支持：

```text
Ontology Version
Knowledge Version
Item Version
Q-Matrix Version
Rubric Version
Model Version
Standard Version
```

一次诊断必须保存：

```text
standard_version
ontology_version
item_version
qmatrix_version
model_version
scoring_version
```

否则未来无法解释历史结果。

---

# 48. 数据质量规则

建立自动检查：

## Rule 01

每个Item必须至少关联一个Skill。

## Rule 02

每个Skill必须关联Knowledge或Cognitive Process。

## Rule 03

每个Skill必须至少存在一个可观测Evidence类型。

## Rule 04

每个Diagnostic Item必须具有Q-Matrix。

## Rule 05

每个Misconception必须存在至少一个诊断证据路径。

## Rule 06

每个Intervention必须有Target。

## Rule 07

每个TransferTask必须关联Transfer目标。

---

# 49. Ontology质量指标

不能只检查“节点数量”。

需要：

```text
Ontology Coverage
Relation Completeness
Annotation Agreement
Q-Matrix Quality
Prerequisite Consistency
Cycle Detection
Duplicate Rate
Orphan Node Rate
Version Integrity
```

---

# 50. 防止知识图谱膨胀

第一版不要追求：

```text
10万知识节点
```

建议：

> 先建设100～300个高价值认知节点。

例如：

```text
100 Knowledge
50 Skill
30 Cognitive Process / Strategy
20 Misconception
300～500 Items
```

先完成：

> **可测量、可诊断、可干预**

再扩大规模。

---

# 51. MVP Ontology规模

建议第一轮：

```text
Standard              30～50
Core Literacy         4
Task Capability       5
Cognitive Process     7～10
Knowledge              100～300
Skill                  50～100
Misconception          30～80
Item                   300～500
Probe                  50～100
Resource               200～500
Intervention           50～100
Transfer Task          30～50
```

---

# 52. 第一阶段重点领域

建议只建设：

> **文言文阅读**

Ontology覆盖：

```text
实词
虚词
词类活用
古今异义
通假字
特殊句式
句意理解
信息筛选
内容概括
分析推断
人物形象
文化语境
迁移
```

---

# 53. Ontology构建流程

采用：

```text
权威标准
   ↓
专家初建
   ↓
知识拆解
   ↓
技能拆解
   ↓
认知过程映射
   ↓
任务能力映射
   ↓
核心素养映射
   ↓
错误模型
   ↓
题目映射
   ↓
专家审核
   ↓
数据验证
   ↓
Ontology V1
```

---

# 54. 专家标注机制

建议至少：

```text
教研专家 × 2
一线教师 × 2
测量专家 × 1
```

对于：

```text
Knowledge
Skill
Cognitive Process
Q-Matrix
Misconception
```

进行双人独立标注。

分歧：

```text
→ 专家仲裁
```

---

# 55. LLM在Ontology构建中的位置

LLM可以：

```text
候选知识抽取
候选关系发现
题目初步标注
重复节点发现
术语归一化
文本聚类
```

但：

```text
LLM ≠ Ontology Authority
```

最终：

```text
LLM Proposal
 ↓
Rule Validation
 ↓
Human Review
 ↓
Ontology Commit
```

---

# 56. Ontology CI/CD

Ontology应该像代码一样管理。

```text
ontology/
├── standards/
├── literacy/
├── capabilities/
├── cognitive/
├── knowledge/
├── skills/
├── misconceptions/
├── relations/
├── mappings/
└── versions/
```

采用Git版本控制：

```text
ontology-v0.1
ontology-v0.2
ontology-v1.0
```

每次修改：

```text
Pull Request
 ↓
Schema Validation
 ↓
Consistency Check
 ↓
Expert Review
 ↓
Merge
```

---

# 57. Ontology自动测试

至少包括：

### 孤立节点检测

```text
Orphan Node
```

### 循环依赖检测

```text
A prerequisite B
B prerequisite A
```

### 关系类型错误

例如：

```text
CoreLiteracy prerequisite_of Item
```

属于非法关系。

### 映射完整性

例如：

```text
Skill
必须能找到
Knowledge / CognitiveProcess / Capability
```

---

# 58. 第一阶段研发任务拆解

## Sprint 1

```text
定义Ontology Class
定义Relation
定义ID规则
定义版本规则
建立Schema
```

---

## Sprint 2

```text
建立100个知识节点
建立50个Skill
建立认知过程
建立任务能力
建立核心素养映射
```

---

## Sprint 3

```text
建立Misconception
建立300道题
建立Q-Matrix
建立Probe
```

---

## Sprint 4

```text
建立Evidence Schema
建立Graph API
建立CDM Adapter
建立Adaptive Adapter
```

---

# 59. 最终Ontology MVP

第一阶段完成后，应能够查询：

### 查询1

> 学生“之”掌握不好，需要补什么？

```text
Learner
 ↓
K_ZHI
 ↓
Skill
 ↓
Prerequisite
 ↓
Misconception
 ↓
Intervention
```

---

### 查询2

> 如何证明学生真正掌握“之”？

```text
Knowledge
 ↓
Skill
 ↓
Recall Evidence
 ↓
Application Evidence
 ↓
Transfer Evidence
```

---

### 查询3

> 哪道题最适合诊断“之”的问题？

```text
Target Skill
 ↓
Candidate Items
 ↓
Expected Information Gain
 ↓
Difficulty
 ↓
Exposure
 ↓
Select
```

---

### 查询4

> 学生为什么错？

```text
Wrong Response
 ↓
Evidence
 ↓
Candidate Misconception
 ↓
Diagnostic Probe
 ↓
Posterior
```

---

# 60. Definition of Done

Ontology V1.0只有同时满足以下条件，才能认为完成。

## 语义完整性

```text
Standard
Core Literacy
Task
Cognitive
Knowledge
Skill
```

全部建立。

## 可测量

每个Skill至少存在：

```text
1个正式测量任务
1个Evidence
```

---

## 可诊断

高价值Skill至少存在：

```text
2～3个诊断Probe
```

---

## 可干预

每个主要Skill至少关联：

```text
2种Intervention
```

---

## 可迁移

关键Skill至少存在：

```text
1个TransferTask
```

---

## 可计算

能够生成：

```text
Q-Matrix
```

并供：

```text
CDM
IRT
Adaptive Testing
```

使用。

---

# 61. V1.0最终交付物

项目第一阶段最终不只是一个Graph数据库，而应该交付：

```text
01 Ontology Specification
02 Entity Schema
03 Relation Schema
04 Knowledge Dictionary
05 Skill Dictionary
06 Cognitive Process Dictionary
07 Misconception Dictionary
08 Q-Matrix
09 Evidence Schema
10 Mapping Matrix
11 Ontology Validation Rules
12 Graph API
13 Ontology Version Repository
14 Expert Annotation Guidelines
15 Data Quality Report
```

---

# 62. 与后续系统的依赖关系

Ontology V1.0完成后：

```text
                 Ontology
                    │
        ┌───────────┼───────────┐
        ↓           ↓           ↓
      Q-Matrix   Evidence    Resource
        ↓           ↓           ↓
       CDM         IRT        RAG
        │           │           │
        └──────┬────┴───────────┘
               ↓
          Learner State
               ↓
       Adaptive Assessment
               ↓
        Learning Decision
               ↓
           AI Tutor
```

因此：

> **Ontology不是一个独立模块，而是整个系统的“语义操作系统”。**

---

# 63. 最终架构原则

整个项目最终形成：

```text
                 ┌───────────────────┐
                 │ Standards         │
                 │ 标准与目标         │
                 └─────────┬─────────┘
                           ↓
                 ┌───────────────────┐
                 │ Cognitive         │
                 │ Ontology          │
                 │ 认知本体           │
                 └─────────┬─────────┘
                           ↓
                 ┌───────────────────┐
                 │ Knowledge Graph   │
                 │ 语义关系网络       │
                 └─────────┬─────────┘
                           ↓
                 ┌───────────────────┐
                 │ Measurement       │
                 │ CDM / IRT         │
                 └─────────┬─────────┘
                           ↓
                 ┌───────────────────┐
                 │ Evidence Graph    │
                 │ 学习证据网络       │
                 └─────────┬─────────┘
                           ↓
                 ┌───────────────────┐
                 │ Learner State     │
                 │ 学生认知状态       │
                 └─────────┬─────────┘
                           ↓
                 ┌───────────────────┐
                 │ Decision Engine   │
                 │ 学习决策           │
                 └─────────┬─────────┘
                           ↓
                 ┌───────────────────┐
                 │ Intervention      │
                 │ 学习干预           │
                 └─────────┬─────────┘
                           ↓
                 ┌───────────────────┐
                 │ Transfer / Retest │
                 │ 迁移与再测         │
                 └─────────┬─────────┘
                           │
                           └────────→ Evidence
```

最终系统的核心不是：

> **“知识图谱 + 大模型”**

而是：

> **“认知本体 + 测量模型 + 学习证据 + 决策闭环”。**

其中：

```text
Ontology
回答：学生需要学什么？

Knowledge Graph
回答：这些知识、技能、认知过程之间是什么关系？

Evidence Graph
回答：我们有什么证据认为学生会/不会？

Measurement Model
回答：如何从证据推断认知状态？

Decision Engine
回答：下一步最应该做什么？

Intervention
回答：如何帮助学生改变？

Transfer Assessment
回答：这种改变是否真正迁移？
```

这六个问题共同构成整个系统的技术壁垒。
