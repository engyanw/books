# 《语文认知Ontology V1.0》

# 实际数据字典与文言文MVP数据资产

## 1. 数据资产总体规模

本版本以**高中语文文言文阅读**作为第一个完整验证域。

当前数据资产：

| 对象                     |     数量 | 状态        |
| ---------------------- | -----: | --------- |
| Core Literacy          |      4 | 基础稳定      |
| Task Capability        |      5 | 基础稳定      |
| Cognitive Process      |      7 | MVP       |
| Knowledge              |    100 | Seed V1.0 |
| Skill                  |     50 | Seed V1.0 |
| Misconception          |     30 | Seed V1.0 |
| Item Blueprint         |    100 | Seed V1.0 |
| Q-Matrix               | 100×50 | Seed V1.0 |
| Ontology Relation      |   约数百条 | Seed V1.0 |
| Knowledge Prerequisite |   初始关系 | 待专家审核     |

---

# 2. ID体系

统一采用：

```text
CLxxx     Core Literacy
TCxxx     Task Capability
CPxxx     Cognitive Process
Kxxx      Knowledge
SKxxx     Skill
Mxxx      Misconception
ITEMxxx   Item
PROBExxx  Diagnostic Probe
EVxxx     Evidence
RESxxx    Resource
INTxxx    Intervention
TRxxx     Transfer Task
RELxxxx   Ontology Relation
```

例如：

```text
K016
    ↓
虚词“之”

SK010
    ↓
辨析虚词“之”

M006
    ↓
虚词字面义替代

ITEM010
    ↓
用于测量SK010

EVxxxx
    ↓
学生实际作答证据
```

---

# 3. Core Literacy

```text
CL01 语言建构与运用
CL02 思维发展与提升
CL03 审美鉴赏与创造
CL04 文化传承与理解
```

注意：

> Core Literacy不是由某一个知识点直接“计算出来”的成绩。

正确关系是：

```text
Knowledge
    ↓
Skill
    ↓
Task Capability
    ↓
Evidence
    ↓
Core Literacy相关表现
```

因此当前版本的 `literacy_refs` 是**证据映射**，不是“素养得分计算公式”。

---

# 4. Task Capability

```text
TC01 文言文阅读
TC02 现代文阅读
TC03 古诗词鉴赏
TC04 写作
TC05 综合语言运用
```

本次MVP全部100个Knowledge和50个Skill聚焦：

```text
TC01 文言文阅读
```

这是刻意控制范围，而不是Ontology最终范围。

---

# 5. Cognitive Process

```text
CP01 识别
CP02 理解
CP03 分析
CP04 推理
CP05 评价
CP06 表达
CP07 迁移
```

其中：

```text
识别 → 理解 → 分析 → 推理 → 评价
                  ↓
                 表达
                  ↓
                 迁移
```

只是认知过程的参考结构，不代表所有任务必须严格按照该顺序执行。

---

# 6. Knowledge 100节点体系

100个知识节点分为八大知识簇。

## K001～K005：实词语义

```text
K001 文言实词语境义
K002 通假字
K003 古今异义
K004 一词多义
K005 偏义复词
```

---

## K006～K015：词类活用

```text
K006 词类活用总论
K007 名词作动词
K008 名词作状语
K009 名词意动用法
K010 名词使动用法
K011 动词使动用法
K012 形容词作名词
K013 形容词作动词
K014 形容词使动用法
K015 形容词意动用法
```

---

## K016～K030：高频虚词

```text
K016 虚词“之”
K017 虚词“其”
K018 虚词“而”
K019 虚词“以”
K020 虚词“于”
K021 虚词“为”
K022 虚词“者”
K023 虚词“所”
K024 虚词“乃”
K025 虚词“遂”
K026 虚词“则”
K027 虚词“若”
K028 虚词“盖”
K029 虚词“因”
K030 虚词“且”
```

---

## K031～K040：特殊句式

```text
K031 判断句
K032 被动句
K033 宾语前置
K034 定语后置
K035 状语后置
K036 主谓倒装
K037 省略句
K038 固定句式
K039 否定句
K040 疑问句
```

---

## K041～K048：语气与副词

```text
K041 判断语气
K042 反问语气
K043 揣测语气
K044 时间副词
K045 程度副词
K046 范围副词
K047 推测副词
K048 否定副词
```

---

## K049～K060：文化与制度语境

```text
K049 人物称谓
K050 官职与迁谪
K051 古代礼制
K052 古代地理行政
K053 古代时间制度
K054 古代称谓与亲属
K055 古代刑法与司法
K056 古代科举与教育
K057 古代经济与赋税
K058 古代军事语汇
K059 古代交通与行旅
K060 古代文书语汇
```

---

## K061～K075：阅读策略

```text
K061 文言实词语境推断流程
K062 文言句意翻译流程
K063 虚词辨析流程
K064 特殊句式识别流程
K065 人物行为链重建
K066 事件因果链重建
K067 叙事时间线重建
K068 指代关系解析
K069 信息筛选流程
K070 内容概括流程
K071 人物形象概括
K072 作者态度判断
K073 主旨概括
K074 推断题解题流程
K075 选项证据核验
```

---

## K076～K092：篇章、文体与证据

```text
K076 叙事视角
K077 对比与衬托
K078 伏笔与照应
K079 详略安排
K080 因果与条件关系
K081 古代文化价值观
K082 士人精神
K083 史传文本特征
K084 论说文本特征
K085 书信表奏文本特征
K086 寓言文本特征
K087 语言表达准确性
K088 古今语序差异
K089 词义迁移与语境变化
K090 文言文语境整体性
K091 文本证据等级
K092 答案边界控制
```

---

## K093～K100：迁移与高级推理

```text
K093 陌生实词迁移推断
K094 陌生虚词迁移辨析
K095 陌生句式迁移识别
K096 跨文本人物比较
K097 跨文本主题迁移
K098 综合证据推断
K099 反事实检验
K100 证据驱动解释
```

---

# 7. Skill 50体系

50个Skill是整个Ontology的关键。

因为：

> Knowledge回答“知道什么”，Skill回答“能做什么”。

---

## SK001～SK009：字词与活用

```text
SK001 识别文言实词语境义
SK002 区分通假字
SK003 识别古今异义
SK004 处理一词多义
SK005 识别偏义复词
SK006 识别词类活用
SK007 判断名词作动词
SK008 判断名词作状语
SK009 判断使动与意动
```

---

## SK010～SK017：虚词

```text
SK010 辨析虚词“之”
SK011 辨析虚词“其”
SK012 辨析虚词“而”
SK013 辨析虚词“以”
SK014 辨析虚词“于”
SK015 辨析虚词“为”
SK016 辨析虚词“者所”
SK017 辨析常见高频虚词
```

---

## SK018～SK027：句式与语法

```text
SK018 识别判断句
SK019 识别被动句
SK020 识别宾语前置
SK021 识别定语后置
SK022 识别状语后置
SK023 识别省略句
SK024 识别固定句式
SK025 识别否定与疑问结构
SK026 理解文言语气
SK027 理解文言副词
```

---

## SK028～SK033：文化语境与翻译

```text
SK028 理解古代官职制度
SK029 理解古代礼制文化
SK030 理解古代制度与社会生活
SK031 理解古代亲属称谓
SK032 理解古代行旅与文书
SK033 执行文言句意翻译
```

---

## SK034～SK043：篇章理解

```text
SK034 重建人物行为链
SK035 重建事件因果链
SK036 重建叙事时间线
SK037 解析指代与省略
SK038 筛选有效信息
SK039 概括文本内容
SK040 概括人物形象
SK041 判断作者态度
SK042 完成推断题
SK043 核验选项证据
```

---

## SK044～SK050：高阶能力

```text
SK044 理解史传文本
SK045 理解论说文本
SK046 理解传统价值观
SK047 控制答案证据边界
SK048 迁移文言知识
SK049 跨文本比较与迁移
SK050 综合证据形成解释
```

---

# 8. Misconception 30体系

错误认知不是：

> “学生答错了。”

而是：

> **对导致错误的一种候选认知机制进行建模。**

因此30个M节点全部采用：

```text
Misconception Hypothesis
```

而不是事实性因果结论。

---

## M001～M010

```text
M001 现代义替代古义
M002 单一义项固化
M003 通假机械判断
M004 词类只看词形
M005 使动意动混淆
M006 虚词字面义推断
M007 虚词位置忽视
M008 虚词功能混淆
M009 句式靠表面标志
M010 宾语前置条件遗漏
```

---

## M011～M020

```text
M011 省略机械补主语
M012 固定句式逐字翻译
M013 语气判断只看标点
M014 时间副词混淆
M015 制度词现代化理解
M016 称谓关系错位
M017 礼制语境缺失
M018 逐句翻译不整合
M019 翻译漏得分点
M020 人物标签先入为主
```

---

## M021～M030

```text
M021 事件因果倒置
M022 时间线混乱
M023 指代就近原则滥用
M024 信息筛选无条件
M025 概括堆砌细节
M026 作者态度情绪化
M027 推断越界
M028 选项先验接受
M029 迁移表面化
M030 证据与结论脱节
```

---

# 9. Knowledge → Skill映射

例如：

```text
K016 虚词“之”
        ↓
SK010 辨析虚词“之”
```

进一步：

```text
SK010
 ├── CP02 理解
 └── CP03 分析
```

再进一步：

```text
SK010
 ↓
TC01 文言文阅读
 ↓
CL01 / CL02相关表现
```

因此：

```text
Knowledge
→ Skill
→ Cognitive Process
→ Task Capability
→ Core Literacy Evidence
```

是第一版的核心语义路径。

---

# 10. Knowledge → Skill不是一对一

例如：

```text
K033 宾语前置
```

可以支持：

```text
SK020 识别宾语前置
SK033 执行文言句意翻译
SK048 迁移文言知识
```

反过来：

```text
SK033 执行文言句意翻译
```

又需要：

```text
K016～K030
K031～K040
K062
K064
K087
```

这正是为什么需要Knowledge Graph，而不是简单Knowledge List。

---

# 11. Misconception诊断链

例如：

```text
学生答错
    ↓
Evidence
    ↓
候选Misconception
    ↓
Diagnostic Probe
    ↓
Posterior Probability
```

对于：

```text
SK010 辨析“之”
```

可能出现：

```text
M006 虚词字面义推断
M007 虚词位置忽视
M008 虚词功能混淆
```

不能因为一道题答错就直接判断：

```text
学生 = M008
```

而应该：

```text
P(M006 | Evidence)
P(M007 | Evidence)
P(M008 | Evidence)
```

再通过Probe降低不确定性。

---

# 12. Q-Matrix定义

第一版建立：

```text
Q ∈ {0,1}^{100×50}
```

即：

```text
100 Items
×
50 Skills
```

其中：

```text
Qij = 1
```

表示：

> Item i 对 Skill j 有实质性测量要求。

例如：

```text
          SK010 SK011 SK012
ITEM001     1     0     0
ITEM002     1     1     0
ITEM003     0     1     1
```

---

# 13. 第一版题目结构

100个Item Blueprint分为：

```text
ITEM001～ITEM070
    单技能诊断

ITEM071～ITEM090
    双技能综合

ITEM091～ITEM100
    迁移/综合
```

形成：

```text
70%
单技能识别
20%
组合技能
10%
迁移综合
```

这只是MVP测试设计，不是最终题库比例。

---

# 14. 为什么第一版要大量使用单技能题

因为系统第一阶段首先需要解决：

> **“到底是哪一个Skill没有掌握？”**

如果一道题同时需要：

```text
SK01
SK05
SK12
SK20
```

学生答错以后，很难判断究竟是哪一个Skill导致错误。

因此第一阶段：

```text
Single Skill Item
```

具有更好的诊断可识别性。

然后逐步增加：

```text
Multi-Skill Item
```

验证复杂认知结构。

---

# 15. Q-Matrix当前状态

当前Q-Matrix已经作为：

> **工程联调Seed Matrix**

写入Excel。

但是必须明确：

```text
当前Q-Matrix
        ↓
工程测试
        ↓
不是生产测量参数
```

正式版本必须经过：

```text
专家Q-Matrix
       ↓
认知访谈
       ↓
小规模Pilot
       ↓
CDM拟合
       ↓
残差分析
       ↓
Q-Matrix修正
       ↓
正式Q-Matrix
```

---

# 16. Data Dictionary

核心表：

```text
ontology_entity
ontology_relation
standard
core_literacy
task_capability
cognitive_process
knowledge
skill
misconception
item
probe
assessment
evidence
learner_state
resource
intervention
transfer_task
rubric
measurement_parameter
```

---

# 17. 最重要的数据表

## knowledge

```text
knowledge_id
type
name
definition
domain
parent_ids
prerequisite_ids
standard_refs
version
status
```

---

## skill

```text
skill_id
name
definition
knowledge_refs
cognitive_refs
capability_refs
literacy_refs
```

---

## misconception

```text
misconception_id
name
description
knowledge_refs
skill_refs
diagnostic_probes
interventions
```

---

## item

```text
item_id
version
type
stem
answer
skill_refs
cognitive_refs
q_matrix
difficulty
discrimination
exposure
status
```

---

## evidence

```text
evidence_id
learner_id
source_type
source_id
response
score
item_version
scoring_version
model_version
observed_at
validity
```

---

# 18. Ontology Relation

关系采用Typed Relation：

```text
prerequisite_of
part_of
requires
supports
assesses
demonstrates
applies_to
exemplified_by
contrast_with
confusable_with
indicates
mitigates
transfers_to
evidenced_by
aligned_to
```

---

# 19. 关系必须区分语义和概率

例如：

```text
K016 supports SK010
```

是Ontology事实。

而：

```text
P(SK010 | K016) = 0.82
```

是Measurement Model参数。

二者绝不能混在一起。

所以系统单独设置：

```text
measurement_parameter
```

用于：

```text
IRT
DINA
GDINA
Knowledge Tracing
Transfer Model
Retention Model
```

等参数。

---

# 20. Ontology → CDM接口

Ontology输出：

```text
Item
 ↓
Skill
 ↓
Q-Matrix
```

CDM输入：

```text
Q-Matrix
+
Response
+
Item Parameter
```

然后输出：

```text
P(Skill Mastery | Evidence)
```

所以：

```text
Ontology
```

负责：

> “测量什么？”

而：

```text
CDM
```

负责：

> “根据证据估计多少？”

---

# 21. Ontology → Adaptive Testing

Adaptive Engine从图谱获得：

```text
Target Skill
Prerequisite
Candidate Items
Difficulty
Exposure
Cognitive Process
```

然后计算：

```text
Expected Information Gain
```

最终：

```text
Graph
 ↓
Candidate Items
 ↓
Measurement Model
 ↓
Information Gain
 ↓
Constraint
 ↓
Next Item
```

---

# 22. Ontology → Learning Engine

例如：

```text
SK010 辨析“之”
Mastery = 0.58
Application = 0.42
Transfer = 0.31
Uncertainty = 0.20
```

通过Graph找到：

```text
Prerequisite
Misconception
Resource
Intervention
Transfer Task
```

形成：

```text
认知缺口
 ↓
错误假设
 ↓
学习资源
 ↓
学习干预
 ↓
应用训练
 ↓
迁移测试
```

---

# 23. 第一版真实研发闭环

Ontology数据投入研发以后，应该跑下面这条链：

```text
100 Knowledge
      ↓
50 Skill
      ↓
100 Item Blueprint
      ↓
Q-Matrix
      ↓
学生作答
      ↓
Evidence
      ↓
DINA/GDINA
      +
IRT
      ↓
Skill Posterior
      ↓
Misconception Candidate
      ↓
Diagnostic Probe
      ↓
Learning Decision
      ↓
Intervention
      ↓
Transfer Item
      ↓
New Evidence
      ↓
Posterior Update
```

这条链跑通，才真正证明Ontology不是“静态知识图谱”。

---

# 24. 第一轮专家标注任务

下一阶段必须组织：

```text
语文教研专家 × 2
一线高中语文教师 × 2
教育测量专家 × 1
算法工程师 × 1
```

重点审核：

```text
① Knowledge边界
② Skill边界
③ Knowledge → Skill
④ Skill → Cognitive Process
⑤ Skill → Task Capability
⑥ Misconception
⑦ Item → Skill
⑧ Q-Matrix
```

---

# 25. 第一轮不允许自动确认的数据

以下数据禁止直接由LLM自动Commit：

```text
Knowledge prerequisite
Skill prerequisite
Misconception diagnosis
Item Q-Matrix
Core Literacy evidence mapping
```

LLM可以：

```text
提出候选
```

最终必须：

```text
LLM Proposal
 ↓
Expert Review
 ↓
Evidence Check
 ↓
Ontology Commit
```

---

# 26. Q-Matrix正式验证

正式Q-Matrix必须经过三个阶段。

## Stage 1：专家认知分析

逐题回答：

> 学生要答对这道题，必须具备哪些Skill？

---

## Stage 2：认知访谈

让学生边做题边解释：

> “你是怎么想到这个答案的？”

检查实际解题过程是否符合预设Skill。

---

## Stage 3：统计验证

真实作答数据进入：

```text
DINA
GDINA
```

检查：

```text
Model Fit
Item Fit
Classification Accuracy
Residual
Attribute Correlation
Q-Matrix Identifiability
```

必要时进行Q-Matrix修正。

---

# 27. MVP数据规模建议

当前100/50/30是：

> **Ontology研发种子规模。**

真实实验建议逐步扩大：

```text
Knowledge
100 → 300 → 1000+

Skill
50 → 150 → 300+

Misconception
30 → 80 → 200+

Items
100 → 500 → 3000+

Students
50 → 300 → 3000+
```

但必须遵循：

> **先增加Evidence质量，再增加节点数量。**

---

# 28. 下一阶段最关键的工作

现在已经完成：

```text
Ontology
Knowledge
Skill
Misconception
Q-Matrix Seed
Data Dictionary
```

下一步不应该继续扩展Knowledge数量。

而应该进入：

# 《Item & Q-Matrix Specification V1.0》

具体要完成：

```text
100道真实文言文题目
        ↓
每道题真实题干
        ↓
标准答案
        ↓
评分规则
        ↓
Knowledge标注
        ↓
Skill标注
        ↓
Cognitive Process标注
        ↓
Misconception候选
        ↓
Q-Matrix专家版
        ↓
Diagnostic Probe
```

然后用**50～100名真实学生的实际作答数据**跑第一版：

```text
DINA
GDINA
IRT
```

这样才能从现在的：

> **“Ontology Seed”**

真正进入：

> **“Cognitive Measurement System V0.1”。**

---

# 29. 当前版本的研发定位

因此，本版本可以明确命名为：

> **Ontology V1.0 / Data Seed V1.0**

而不是宣称：

> “已经完成生产级认知模型”。

真正的版本演进建议为：

```text
Ontology V1.0
      ↓
Expert Validated V1.1
      ↓
Pilot Calibrated V1.2
      ↓
Measurement Validated V1.5
      ↓
Production Ontology V2.0
```

最终目标不是拥有：

> 10000个知识点。

而是拥有一个能够稳定回答：

> **“学生当前到底会什么、不会什么、为什么不会、证据是什么、下一步学什么，以及学完以后是否真的会了。”**

的认知基础设施。
