# 03 语文认知 Ontology 与 Knowledge Graph 设计 V1.0

> 对应任务 #3（设计文档01）。定义四层认知模型、节点/关系对象、ID 规约与知识图谱存储模型。本文档是后续 State/Evidence/Item/CDM 文档的共同术语基础。

## 1. 设计原则

- 知识图谱描述"知识、认知过程、任务能力、核心素养及其关系"，**不描述学生水平**（学生状态独立存储，见 `04-student-cognitive-state-schema.md`）。
- 不采用刚性前置（A→B→C），而采用多类型关系 + 条件依赖 + 证据权重。
- 标准层与知识层解耦：标准定义"什么是达成"，图谱定义"知识结构与关系"。

## 2. 四层认知模型

```
L4 Core Literacy（核心素养）
       ↑
L3 Task Capability（任务能力）
       ↑
L2 Cognitive Process（认知过程）
       ↑
L1 Knowledge（知识）
```

### 2.1 L1 Knowledge

知识节点示例（文言文 MVP）：

| ID | 类型 | 名称 |
| --- | --- | --- |
| K-WW-WORD-001 | 文言实词 | "负" |
| K-WW-FUNC-001 | 文言虚词 | "以" |
| K-WW-SYN-001 | 文言句式 | 宾语前置 |
| K-WW-USG-001 | 特殊用法 | 名词作动词 |

节点属性：

```yaml
Knowledge:
  id: K-WW-FUNC-001          # 全局唯一，前缀编码领域+子类
  label: 虚词"以"
  domain: classical_reading    # 所属任务能力
  sub_type: function_word
  contexts: [narrative, argumentative]  # 适用情境
  common_errors: ["义项混淆", "语境误判"]
  typical_items: [ITEM001, ITEM109]
  related_resources: [RES-001]
  version: 1.0
```

### 2.2 L2 Cognitive Process

描述"完成题任务需执行什么认知动作"。MVP 枚举：

`RECALL / UNDERSTAND / ANALYZE / INFER / EVALUATE / TRANSFER / EXPRESS`

过程链示例（虚词"以"）：

```
语境识别 → 义项判断 → 语义推断 → 迁移
```

用于：错误归因、任务设计、诊断探针、学习干预。

### 2.3 L3 Task Capability

```
CA01 文言文阅读
 ├── 文意理解
 ├── 实词语境判断
 ├── 虚词辨析
 ├── 句式分析
 ├── 翻译
 ├── 信息概括
 └── 推断
CA02 现代文阅读（MVP 不做）
CA03 古诗词鉴赏（MVP 不做）
CA04 写作（MVP 不做）
CA05 综合语言运用（MVP 不做）
```

> L3 是"可观察的任务表现维度"，不等于不可直接观察的心理能力本体。

### 2.4 L4 Core Literacy

四素养：语言建构与运用 / 思维发展与提升 / 审美鉴赏与创造 / 文化传承与理解。

映射为**概率性证据关系**，非确定性因果：

```
文言文阅读任务表现 → 思维分析能力 → 思维发展与提升
```

## 3. 关系模型

不使用线性权重（实词0.6+虚词0.3+句式0.1），改用结构关系 + 条件概率 + 证据权重。

### 3.1 关系类型

| 关系 | 语义 | 示例 |
| --- | --- | --- |
| prerequisite | 支撑前提 | K-WW-WORD-001 → K-WW-SYN-001 |
| support | 辅助支持 | 虚词义项 → 句意理解 |
| similarity | 相似易混 | "以"作介词 vs "以"作连词 |
| contrast | 对比区分 | 宾语前置 vs 判断句 |
| composition | 组合构成 | 文言文阅读 → 实词+虚词+句式 |
| transfer | 可迁移 | 课内义项 → 课外陌生文本 |

### 3.2 条件依赖表达

```
P(TaskSuccess | KnowledgeState, CognitiveProcess, Context, Item)
```

可表达：门槛效应 / 协同效应 / 情境效应 / 认知过程差异 / 迁移差异。

## 4. Task ↔ Core Literacy 映射矩阵

允许一个任务能力映射多个素养：

```
CA01 文言文阅读
 ├── Language（语言建构）
 ├── Thinking（思维发展）
 └── Culture（文化传承）
```

权重为待校准参数（V2.2 §5.1），非固定常数。

## 5. ID 规约

```
K-<DOMAIN>-<SUBTYPE>-<SEQ>   知识节点
C-<PROCESS>                   认知过程
CA<NN>                        任务能力
L<NN>                         核心素养
R-<SEQ>                       关系
```

MVP domain 枚举：`classical_reading`。扩展时增加 `modern_reading` 等。

## 6. 存储模型

| 存储 | 用途 |
| --- | --- |
| PostgreSQL（关系模型） | 节点、关系、属性、版本 |
| Graph DB / PG Graph | 认知关系遍历（路径、迁移链） |
| Vector DB | 知识资源/文本相似（资源检索） |

> MVP 可先用 PostgreSQL + 邻接表，避免过早引入图数据库。

## 7. 标准版本与纵向等值（V2.2 §4.3）

- 课标改版时，知识节点与映射矩阵版本化。
- 跨版本用**共同锚题等值**，保证学生长期能力曲线连续。
- 历史诊断结果标注所用图谱版本，跨版本比较走等值转换。

## 8. 验收

- [ ] 四层节点定义完整，MVP 知识节点 ≥ 100。
- [ ] 关系类型可表达门槛/协同/情境/迁移。
- [ ] Task↔Literacy 映射矩阵支持一对多。
- [ ] ID 规约一致，可被 Item/Evidence/State 文档引用。
- [ ] 版本化与等值机制有接口。
