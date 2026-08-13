# CCI Reference Architecture V2.2

## —— Cognitive Infrastructure for Verifiable, Evolving Human Cognition

### 可运行、可验证、可归因、可回滚的认知基础设施参考架构

> **V2.2 Engineering Baseline Revision**：本次修订不新增顶层概念，重点将状态机、数据/事件规范、参数基线、运行时处置和安全纠错下沉为可执行机制。

---

# Executive Summary

过去几十年，信息系统解决的问题不断演进：

**文件系统保存信息 → 数据库保存数据 → 知识库保存知识 → RAG 检索知识 → Agent 调用工具。**

但这些系统始终存在一个更深层的问题：

> **系统能够保存“发生了什么”，却很难保存“当时为什么这样判断，以及这个判断在什么条件下成立”。**

大量真正具有长期价值的组织能力，并不存在于文档、数据库或者代码中，而存在于人的决策过程中：

- 为什么选择 A，而没有选择 B；
- 当时有哪些上下文；
- 哪些证据真正影响了判断；
- 哪些条件是隐含前提；
- 哪些经验来自失败；
- 什么情况下这个判断不再成立；
- 后来发生了什么；
- 这个认知是否被其他人成功复用。

因此，CCI（Cognitive Infrastructure）不是下一代知识库，也不是 RAG 的增强版，更不是 Agent Memory。

CCI 的核心对象不是 **Document**，而是：

> **Decision + Context + Evidence + Reasoning + Outcome + Boundary + Provenance**

CCI 的核心目标也不是“保存更多知识”，而是：

> **让高价值认知能够被捕获、验证、运行、复用、归因、演化，并在错误时可回滚。**

V2.2 在 V2.1 的基础上进一步明确五个核心能力：

1. **Capture** —— 捕获真实决策，而不是事后编写正确答案；
2. **Verify** —— 用证据、反例和挑战验证认知；
3. **Runtime** —— 让认知真正进入决策运行时；
4. **Attribute** —— 判断认知是否真实改变了决策；
5. **Evolve** —— 根据环境、结果和反例持续升级、降级、拆分或衰减。

因此：

> **CCI is not a Knowledge Store.**
> **CCI is a Cognitive Runtime with persistent memory, evidence, attribution and evolution.**

V2.2 的“正式基线”含义是：核心架构已经稳定，但参数、状态、事件和策略采用**默认基线 + 领域配置**模式，而不是宣称存在一套适用于所有行业的固定常数。任何自动晋升、自动交付和自动归因都必须受到状态、证据、风险、漂移和人类权限的共同约束。

---

# 1. Why CCI

## 1.1 人类真正损失的不是信息，而是认知

组织每天产生海量信息：

- 文档；
- 邮件；
- 会议纪要；
- Ticket；
- Git Commit；
- RFC；
- 事故报告；
- Chat；
- API Log；
- Metrics。

但是这些信息并不等于认知。

一个事故报告可能告诉我们：

> 数据库连接池耗尽。

但真正有价值的认知可能是：

> 当业务流量增长超过某一阈值，同时连接建立延迟开始上升时，不应该首先扩容数据库，而应该检查连接池复用率；因为该业务采用长连接模型，数据库扩容无法解决连接生命周期问题。

真正需要传承的不是：

**发生了什么。**

而是：

**为什么这样判断、在什么条件下成立、什么时候不成立。**

---

# 2. CCI First Principles

CCI V2.2 建立在八条第一性原理之上。

## Principle 1 — Cognition is Context-Bound

认知不是绝对真理，而是：

> **在特定 Context 下成立的 Decision Model。**

因此任何 Cognitive Model 都必须绑定：

- 时间；
- 环境；
- 业务；
- 技术；
- 约束；
- 风险；
- 目标。

---

## Principle 2 — Decision Must Preserve Its Original State

决策必须保留其发生时的真实状态。

因此：

**T0 Decision Snapshot ≠ T2 Outcome**

结果不能反向修改决策时的：

- Context；
- Evidence；
- Reasoning；
- Confidence。

防止 Hindsight Bias。

---

## Principle 3 — Evidence Precedes Abstraction

认知不能因为“看起来合理”而升级。

必须满足：

> **Evidence Sufficiency → Promotion**

而不是：

> **Sample Count → Promotion**

---

## Principle 4 — Cognition Must Be Falsifiable

任何 Cognitive Model 都必须允许：

- Challenge；
- Counter Evidence；
- Boundary Discovery；
- Demotion；
- Split；
- Retirement。

不能验证的认知，不应该成为高等级认知资产。

---

## Principle 5 — Conflict Is Information

认知冲突不是简单的错误。

冲突可能意味着：

- Context 不同；
- Evidence 不同；
- Fact 错误；
- Reasoning 错误；
- Objective 不同。

因此：

> **Conflict → Classification → Resolution / Boundary Discovery**

---

## Principle 6 — Cognition Has a Lifecycle

认知不是永久资产。

其生命周期为：

**Capture → Validate → Promote → Reuse → Attribute → Challenge → Evolve → Decay → Reactivate**

---

## Principle 7 — Cognitive Value Must Be Attributable

认知价值不能用：

- 点击量；
- 调用量；
- 引用次数

简单定义。

必须回答：

> **如果没有这条认知，这次决策是否可能不同？**

---

## Principle 8 — AI Must Augment, Not Erase Human Agency

CCI 的目标不是让人停止思考。

AI 应承担：

- Capture Cost；
- Search Cost；
- Validation Cost；
- Simulation Cost。

人类必须保留：

- Semantic Authority；
- Final Judgment；
- High-Risk Approval；
- Value Alignment。

---

# 3. What Is Cognitive Infrastructure

CCI 的核心对象不是 Document，而是 **Cognitive Episode**。

## 3.1 Cognitive Episode

一个 Episode 至少包含：

```
Episode
│
├── Decision
│
├── Context
│
├── Evidence
│
├── Reasoning
│
├── Constraint
│
├── Confidence
│
├── Outcome
│
├── Boundary
│
├── Provenance
│
└── Attribution

```

其中：

### Decision

当时做出了什么决定。

### Context

当时处于什么环境。

### Evidence

当时知道什么。

### Reasoning

为什么这样判断。

### Constraint

有哪些约束。

### Confidence

当时有多大把握。

### Outcome

后来发生了什么。

### Boundary

在哪些条件下成立或失效。

### Provenance

认知从哪里产生、经过哪些演化。

### Attribution

认知是否真正影响了后续决策。


## 3.2 Minimum Cognitive Asset Schema

为了让参考架构能够直接进入 MVP，CCI 定义最小数据契约。具体实现可以映射到关系表、文档库或图存储，但语义字段必须保持一致。

```text
CognitiveAsset
├── asset_id                 # 全局唯一标识
├── asset_type               # Episode / Pattern / Model / Principle
├── version                  # 单调递增版本号
├── status                   # 生命周期状态
├── decision_snapshot        # T0 决策快照引用
├── context                  # 时间、环境、业务、技术、约束
├── evidence_refs            # Evidence 引用及来源
├── reasoning                # 当时的判断依据
├── outcome_refs             # T2+ 结果引用，不修改 T0
├── boundary                 # 成立/失效条件
├── evidence_score           # ES 及其分项
├── confidence               # 当前可信度
├── drift_score              # 当前环境漂移
├── attribution              # 使用、影响、结果、归因记录
├── provenance               # 来源及演化链
├── owner / steward / reviewer
├── trust_domain             # 信任域
├── policy_refs              # 访问、使用、归因、保留策略
├── created_at / updated_at
└── schema_version           # 数据契约版本
```

**最小约束：**

1. `asset_id + version` 唯一；
2. T0 Snapshot 只能追加，不能被 Outcome 更新；
3. 所有 Evidence 必须可追溯到来源；
4. 状态变化必须产生 Event；
5. 高价值资产必须具备 Owner、Provenance、Boundary 和 Trust Domain。

## 3.3 Event Model

Event Sourcing 的最小事件集合：

| Event | 关键字段 | 说明 |
|---|---|---|
| `EpisodeCreated` | asset_id, snapshot_ref, actor | 创建 Episode |
| `EvidenceAttached` | evidence_id, source_ref | 增加证据 |
| `ValidationCompleted` | validator, result, score | 验证完成 |
| `ChallengeExecuted` | level, cost, finding | 挑战执行 |
| `Promoted` / `Demoted` | from, to, reason | 状态升降级 |
| `Split` / `Merged` | source, targets | 模型拆分/合并 |
| `DriftDetected` | drift_type, score | 环境漂移 |
| `AttributionRecorded` | influence, attribution, evidence | 归因记录 |
| `Quarantined` / `Released` | reason, reviewer | 安全隔离/解除 |
| `RollbackRequested` / `RollbackCompleted` | target_version, reason | 状态回滚 |

每个事件必须包含 `event_id`、`asset_id`、`event_type`、`event_time`、`actor`、`correlation_id`、`schema_version` 和 `payload_hash`。事件只追加，不原地修改；事件 Schema 升级采用向后兼容的版本化策略。

---

# 4. Cognitive Abstraction Model

CCI 不把所有 Episode 都提升为高层知识。

认知存在四个抽象层：

```
Episode
   │
   ▼
Pattern
   │
   ▼
Model
   │
   ▼
Principle

```

但这不是单向晋升树，而是：

> **Evidence-driven Cognitive State Space**

即认知可以：

- Promote；
- Demote；
- Split；
- Merge；
- Suspend；
- Reactivate。


## 4.1 Cognitive Asset State Machine

所有认知资产共享一套最小生命周期状态机，避免 Runtime、Control Plane 和 Memory 使用不同状态语义。

```text
DRAFT
  │
  ▼
QUARANTINED ──reject──> ARCHIVED
  │
  ▼
VALIDATED
  │
  ▼
ACTIVE ──drift/error──> DEGRADED
  │                         │
  │                         ▼
  │                    SUSPENDED
  │                         │
  └────reactivate───────────┘
  │
  └────────retire──────────> ARCHIVED

Any ACTIVE/DEGRADED/SUSPENDED version
          │
          └── rollback ──> previous VALIDATED version
```

状态转换必须满足三类约束：

- **Pre-condition**：证据、信任、边界、权限满足要求；
- **Transition Event**：每次状态变化产生不可变事件；
- **Post-action**：更新 Runtime 可见性、挑战预算、告警和审计状态。

默认原则：**AI 可以提出状态转换，Control Plane 可以执行低风险自动转换，高风险转换必须经过授权人确认。**

---

# 5. Evidence Sufficiency

## 5.1 从“数量”转向“证据充分性”

定义：

**ES = Evidence Sufficiency**

由六类因素共同决定：

```
ES =
Evidence Quality
× Context Diversity
× Outcome Stability
× Counter-Evidence Resistance
× Expert Validation
× Temporal Stability

```

但 ES 不采用全球统一阈值。

CCI V2.2 引入：

> **Domain Evidence Profile**

不同领域可以定义不同权重。

例如：

### SRE

```
Outcome Stability       High
Evidence Quality        High
Context Diversity       Medium
Expert Validation       Medium

```

### 架构设计

```
Context Diversity       High
Evidence Quality        High
Outcome Stability       Medium
Expert Validation       High

```

因此：

> **CCI 提供计算框架，不强制所有领域使用同一套参数。**

### 5.2 Default Evidence Baseline

为了避免“领域可配置”退化为“没有默认值”，V2.2 提供 0~100 的参考基线。ES 采用**加权几何平均**作为工程实现建议；六项指标先归一化到 0~100，再按 Domain Evidence Profile 配置权重。

默认晋升门槛：

| Transition | ES 基线 | 最低证据护栏 |
|---|---:|---|
| Episode → Pattern | ≥60 | 至少 3 个相互独立的有效 Episode |
| Pattern → Model | ≥75 | 至少 5 个跨 Context 的有效 Episode |
| Model → Principle | ≥85 | 至少 8 个跨 Context 的证据 + 专家终审 |

同时满足 Cross-Context Validation、Counter-Evidence 可接受、时间稳定性和 Human Authority。**ES 阈值不是行业真理，而是 MVP 默认值；连续验证结果应通过治理机制校准。**

降级参考：ES < 60 或出现关键事实推翻、核心边界失效、连续高风险失败时进入 DEGRADED；若无法证明继续适用，则进入 SUSPENDED。

---

# 6. Cognitive Promotion & Demotion

## 6.1 Promotion

认知升级至少需要满足：

```
Evidence Sufficiency
        +
Cross-Context Validation
        +
Stable Outcome
        +
Acceptable Counter-Evidence
        +
Human Authority

```

---

## 6.2 Promotion Guardrail

自动晋升最多到 **Model**。Principle 的形成必须经过领域专家或明确授权的人类评审；S 级资产不得仅凭模型评分自动晋升。任何 Promotion 都必须引用 Evidence、Context Diversity、Counter-Evidence 和审查记录。

## 6.3 Demotion

以下情况触发降级：

- 新环境持续失败；
- 反例增加；
- 核心前提消失；
- 结果稳定性下降；
- 环境发生重大漂移；
- 事实基础被推翻。

---

## 6.4 Split

如果两个模型都正确，但适用条件不同：

```
Model A
   │
   ├── Context X → valid
   │
   └── Context Y → invalid

```

则不是删除 A，而是：

```
Model
  │
  ├── Model-X
  └── Model-Y

```

---

# 7. Cognitive Runtime

## 7.1 Runtime 是 CCI 的核心

CCI 不应该被理解为：

> Cognitive Store + RAG

而应该理解为：

> **Cognitive Runtime + Cognitive Memory**

Runtime 负责：

- Context Assembly；
- Cognitive Retrieval；
- Decision Support；
- Boundary Checking；
- Risk Evaluation；
- Attribution；
- Runtime Feedback。

Memory 负责：

- Episode；
- Pattern；
- Model；
- Evidence；
- Provenance；
- Event History。

---

# 8. CCI Reference Architecture

```
┌───────────────────────────────────────────────────────┐
│                 Experience / Application              │
│   Human · Agent · Copilot · Enterprise Application    │
└───────────────────────────┬───────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────┐
│                Cognitive Runtime Layer                │
│                                                       │
│ Context Assembly │ Cognitive Retrieval │ Decision     │
│ Boundary Check   │ Risk Evaluation     │ Attribution  │
└───────────────────────────┬───────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────┐
│                 Cognitive Control Plane               │
│                                                       │
│ Validation │ Challenge │ Conflict │ Promotion         │
│ Demotion   │ Split     │ Decay    │ Reactivation      │
└───────────────────────────┬───────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────┐
│                  Cognitive Memory                     │
│                                                       │
│ Episode │ Pattern │ Model │ Principle │ Evidence      │
│ Context │ Outcome │ Boundary │ Provenance              │
└───────────────────────────┬───────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────┐
│              Evidence & Event Foundation              │
│                                                       │
│ Event Sourcing │ Evidence Store │ Vector Index        │
│ Metadata       │ Audit Log      │ Graph / Relations   │
└───────────────────────────┬───────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────┐
│           Infrastructure / Data / AI Foundation       │
│ PostgreSQL · Object Storage · Vector DB · LLM · GPU   │
└───────────────────────────────────────────────────────┘

```

---

# 9. Data Plane and Control Plane

CCI V2.2 保留双平面架构，但进一步明确其职责。

## Cognitive Data Plane

面向实时决策：

```
Context
  ↓
Retrieve
  ↓
Assemble
  ↓
Evaluate
  ↓
Deliver
  ↓
Decision

```

目标：

> **Low Latency / High Availability**

---

## Cognitive Control Plane

面向长期演化：

```
Observe
  ↓
Validate
  ↓
Challenge
  ↓
Attribute
  ↓
Promote / Demote / Split
  ↓
Decay / Reactivate

```

目标：

> **Correctness / Evolution / Governance**

因此：

> **Data Plane 负责让认知生效。**
> **Control Plane 负责决定认知是否仍然值得生效。**

### 9.1 Runtime / Plane / Memory Mapping

- **Cognitive Runtime** 是实时执行核心；
- **Cognitive Data Plane** 是 Runtime 的同步决策路径；
- **Cognitive Control Plane** 是 Runtime 的异步验证、治理与演化路径；
- **Cognitive Memory** 是 Runtime 的持久化记忆，不承担状态决策；
- **Event/Evidence Foundation** 提供不可变历史、证据和审计基础。

Runtime 可以采集 Attribution Signal，但**权威归因结论属于 Control Plane 的治理结果**，避免实时路径被高成本反事实计算阻塞。

---

# 10. Capture Engine

CCI 不追求“什么都记录”。

采用：

> **Decision-driven Capture**

---

## 10.1 Cognitive Value

认知价值由四个维度组成：

```
CV =
Impact × Rarity × Cost × Irreplaceability

```

进一步分为：

| Level特征捕获策略 |               |             |
| ----------- | ------------- | ----------- |
| S           | 高影响、高稀缺、高不可替代 | 完整捕获 + 人工确认 |
| A           | 高价值、可复用       | 结构化捕获       |
| B           | 一般价值          | AI 自动提取     |
| C           | 低价值           | 轻量记录或不记录    |

---

## 10.2 Capture Friction

CCI 不追求最低捕获摩擦。

而是：

> **Friction should be proportional to Cognitive Value.**

即：

```
S → High Quality / High Friction
A → Medium
B → Low
C → Near Zero

```

---

# 11. Snapshot Isolation

每个高价值决策建立：

```
T0
│
├── Context Snapshot
├── Evidence Snapshot
├── Reasoning Snapshot
├── Constraint Snapshot
└── Confidence

```

随后：

```
T1 → Decision Execution
T2 → Outcome
T3 → Validation
T4 → Attribution

```

**Outcome 永远不能修改 T0。**

Event Sourcing 保证：

> **历史不可被未来重写。**

---

# 12. Cognitive Attribution

CCI V2.2 将归因定义为：

> **Decision Impact Attribution**

而不是 Usage Attribution。

## 12.1 三级归因

### L1 — Explicit Attribution

用户直接标记：

```
Not Used
Partially Used
Key Influence

```

适用于 MVP。

---

### L2 — Assisted Attribution

AI 比较：

```
Initial Decision
      vs
CCI-informed Decision

```

并结合：

- Recommendation；
- User Action；
- Outcome；
- Counterfactual。

生成：

> **Cognitive Contribution Candidate**

由人确认。

---

### L3 — Experimental Attribution

在高价值领域采用：

- A/B；
- Shadow Mode；
- Controlled Trial；
- Counterfactual Evaluation。

测量：

> **CCI 对决策质量的边际贡献。**

### 12.2 Attribution Confidence & Correction

归因结果必须携带 `Attribution Confidence`，并允许后续纠偏：

| Confidence | 来源 | 用途 |
|---|---|---|
| Low | L1 显式标注或弱行为信号 | 运营统计，不直接用于高价值 Credit |
| Medium | L2 反事实候选 + 人工确认 | 企业归因与治理 |
| High | L3 受控实验或强证据链 | 高价值资产评价、经济结算 |

归因可以被更正，但不能覆盖历史：更正通过新的 `AttributionCorrected` Event 追加记录，并重新计算相关 Credit、模型评价和实验结果。

---

# 13. Attribution Is Not Outcome

必须严格区分：

```
Usage
≠
Influence
≠
Outcome
≠
Attribution

```

例如：

用户看到了 CCI 推荐，但没有采用：

```
Usage = 1
Influence = 0
Attribution = 0

```

用户没有直接点击 CCI，但通过团队成员间接获得认知：

```
Usage = 0
Influence = 1
Attribution > 0

```

决策采用了认知但最终失败：

```
Influence = 1
Outcome = Failure

```

这并不意味着：

```
Cognition = Wrong

```

必须继续判断：

- 使用是否正确；
- Context 是否匹配；
- Boundary 是否满足；
- Outcome 是否受到其他因素影响。

---

# 14. Verification Budget

Challenge Engine 必须受到资源约束。

定义：

```
Challenge Priority
=
Risk × Impact × Uncertainty × Drift
÷ Verification Cost

```

---

## 14.1 Verification Budget

每个周期建立：

```
Global Budget
      │
      ├── S Models
      ├── A Models
      ├── B Models
      └── C Models

```

---

## 14.2 Budget Feedback

挑战之后评估：

```
Challenge Cost
        vs
Risk Reduction
        vs
New Knowledge Gain

```

如果：

```
High Cost
+
Low Discovery
+
Low Risk

```

则降低未来预算。

如果：

```
High Discovery
+
High Risk

```

则提高预算。

因此：

> **Verification is itself an economic optimization problem.**

### 14.3 Default Budget Policy

MVP 可采用以下默认配额作为起始点：S/A/B/C = **50% / 30% / 15% / 5%**。其中高风险、强漂移资产可以跨等级获得额外预算；配额不是永久固定值，每个周期根据 Risk Reduction、Knowledge Gain、Cost Efficiency 重新校准。

默认反馈规则：

- 连续 3 个周期高成本且无有效发现 → 配额下调一级；
- 发现高价值反例、边界或事实错误 → 下一周期预算提升 25%~100%；
- 预算消耗效率低于全局基准 → 降低挑战等级或转为按需验证；
- S 级高风险资产不得因为预算不足而永久跳过验证，必须升级人工审查。

---

# 15. Challenge Levels

CCI 不采用全量挑战。

```
Level 0
Passive Validation

Level 1
On-Demand Validation

Level 2
Active Challenge

Level 3
Red Team / Simulation

```

只有满足：

```
Risk × Impact × Uncertainty × Drift

```

达到对应阈值时，才升级挑战等级。

---

# 16. Environmental Drift

认知衰减不应该简单等于：

> 时间越久 → 权重越低。

真正导致认知失效的是：

> **成立环境发生变化。**

---

## 16.1 三类 Drift

### Technology Drift

来源：

- CMDB；
- Git；
- CI/CD；
- Infrastructure；
- Version Management。

---

### Business Drift

来源：

- Traffic；
- User Behavior；
- Business KPI；
- Product Model。

---

### Policy Drift

来源：

- Regulations；
- Security Policy；
- Compliance Rule；
- Organizational Policy。

---

## 16.2 Drift Score

CCI 将不同漂移信号归一化为：

```
Drift Score ∈ [0,1]
```

工程实现建议采用：

```
Drift Score = Σ(wᵢ × dᵢ)
Σwᵢ = 1
```

其中 `dᵢ` 为单项漂移信号归一化值，`wᵢ` 由 Domain Drift Profile 配置。默认参考权重：Technology 0.40、Business 0.30、Policy 0.20、Operational 0.10；安全/合规敏感领域可提高 Policy 权重。

默认处置区间：

| Drift Score | 状态影响 | 默认动作 |
|---|---|---|
| 0.00–0.20 | 无明显影响 | 正常运行 |
| 0.20–0.40 | 轻微漂移 | 提高观察频率 |
| 0.40–0.60 | 中度漂移 | 降低 Confidence，增加 Challenge |
| 0.60–0.80 | 高度漂移 | 进入 DEGRADED，限制自动交付 |
| >0.80 | 极高漂移 | SUSPENDED / 强制重新验证 |

再映射到：

```
Applicability
Confidence
Decay Rate
Challenge Priority
```

因此：

> **Decay is driven by environmental change, not merely age.**

---

# 17. Cognitive Conflict Engine

冲突首先分类。

```
Conflict
   │
   ├── Boundary Conflict
   │       → Split
   │
   ├── Fact Conflict
   │       → Evidence Verification
   │
   ├── Reasoning Conflict
   │       → Logic Validation
   │
   └── Value Conflict
           → Objective Alignment

```

---

## 17.1 Human-AI Boundary

### AI

负责：

- Detect；
- Classify；
- Generate Candidate；
- Compare Evidence；
- Suggest Resolution。

### Human

负责：

- High-risk approval；
- Semantic Authority；
- Final Split；
- Final Principle Promotion。

---

# 18. Cognitive Safety

CCI 必须假设：

> **认知可能被攻击，也可能被错误生成。**

因此采用：

```text
New Cognition
     ↓
Quarantine
     ↓
Validation
     ↓
Trust Accumulation
     ↓
Production
```

## 18.1 Cognitive Poisoning Defense

检测维度包括：

- 异常高频贡献；
- 短时间大量晋升；
- 归因异常集中；
- 异常引用网络；
- 协同刷量；
- 证据来源单一；
- 反例被系统性忽略。

### 18.2 Poisoning Response

检测必须形成“检测 → 隔离 → 调查 → 回滚 → 恢复”的闭环：

```text
Anomaly
  ↓
Risk Scoring
  ├─ Low    → Observe
  ├─ Medium → Quarantine + Review
  └─ High   → Block + Rollback + Incident
```

默认触发规则：

- 单一异常信号达到 Critical → 立即隔离相关资产；
- 两个及以上 High 信号同时出现 → 自动进入 Quarantine；
- 发现证据伪造、越权修改历史或协同操纵 → 直接进入 High 处置。

确认污染后：

1. 回滚受污染资产及其派生版本；
2. 标记相关 Attribution 与 Cognitive Credit 为 Pending Review；
3. 重新验证受污染资产的下游依赖；
4. 对贡献者实施限流、冻结贡献权限或人工审查；
5. 保留完整审计链，不删除原始事件。

安全策略本身也必须版本化，避免“检测规则更新”破坏历史可解释性。

---

# 19. Cognitive Rollback

Event Sourcing 不仅用于审计。

它还必须支持：

> **Cognitive State Rollback**

例如：

```
Model V7
   ↓
发现错误
   ↓
Rollback
   ↓
Model V6
   ↓
重新验证
   ↓
修复 V8

```

任何：

- 错误晋升；
- 错误归因；
- 错误拆分；
- 错误合并；
- 恶意污染

都必须可回溯、可修正。

---

# 20. Cognitive Metabolism

CCI 的核心运行闭环：

```
        ┌──────────────┐
        │    Capture   │
        └──────┬───────┘
               ↓
        ┌──────────────┐
        │  Validation  │
        └──────┬───────┘
               ↓
        ┌──────────────┐
        │     Reuse    │
        └──────┬───────┘
               ↓
        ┌──────────────┐
        │ Attribution  │
        └──────┬───────┘
               ↓
        ┌──────────────┐
        │   Evolution  │
        └──────┬───────┘
               ↓
       Promote / Demote
       Split / Decay
               │
               └──────────→ Reuse

```

这就是：

> **Cognitive Metabolism**

---

# 21. Cognitive Context Profile

CCI 不采用固定用户等级。

每个用户拥有：

> **Cognitive Context Profile**

至少包含：

```
Domain Expertise
Historical Performance
Interaction Pattern
Decision Quality
Self Assessment
Challenge Performance
Risk Profile

```

因此：

> **认知交付深度 = 用户能力 × 场景 × 风险**

---

# 22. Cognitive Delivery Modes

为了避免 Cognitive Atrophy，CCI 提供四种模式。

## Direct

低风险、低复杂度：

> 直接给答案。

## Explain

中高风险：

> 展示 Evidence、Boundary、Reasoning。

## Challenge

要求用户：

> 先做判断，再显示系统认知。

## Practice

提供：

> 模拟场景 + 自主决策 + 结果反馈。

因此：

> **CCI 不只是帮助人做决定，也帮助人变得更会做决定。**

---

# 23. Cognitive Economy

CCI 不采用：

> Citation = Credit

而采用：

```
Contribution
×
Validation
×
Attribution
×
Outcome
×
Impact

```

形成：

> **Proof of Valid Cognitive Outcome**

---

## 23.1 Enterprise Incentive

Cognitive Credit 可以成为：

- 专家贡献证明；
- 技术晋升依据；
- 内部专家评级；
- 培训资源分配；
- 专项算力资源；
- 创新奖励。

但：

> **Credit 不能直接等同于绩效。**

必须经过治理与人工复核。

---

# 24. Governance

CCI 的治理对象不是单纯的数据，而是：

> **Cognitive Asset**

认知资产至少分为：

```
Public
Shared
Internal
Confidential
Restricted

```

每个 Cognitive Asset 绑定：

- Owner；
- Steward；
- Reviewer；
- Trust Level；
- Access Policy；
- Usage Policy；
- Attribution Policy；
- Retention Policy。

---

## 24.1 Governance Roles

| Role | 核心职责 | 关键权限 |
|---|---|---|
| Contributor | 提交 Episode / Evidence | 创建、补充证据 |
| Steward | 生命周期管理 | 标记、维护、发起验证 |
| Reviewer | 质量与证据审查 | 批准/拒绝 A 级转换 |
| Domain Expert | 领域语义权威 | Model/Principle 终审 |
| Security/Admin | 权限与安全 | 隔离、回滚、封禁 |

高风险资产至少需要 Reviewer + Domain Expert 的双重授权。

---

# 25. Five Trust Domains

```
Individual
   ↓
Team
   ↓
Enterprise
   ↓
Industry
   ↓
Public / Civilization

```

认知不能默认跨域传播。

必须满足：

```
Identity
+
Authorization
+
Provenance
+
Policy
+
Compliance

```

---

# 26. Cognitive Graph

CCI 不试图一开始建立完整因果图。

采用三阶段路线。

### Phase 1 — Evidence Graph

```
Entity
Relation
Time
Source

```

解决：

- Traceability；
- Retrieval；
- Association。

### Phase 2 — Human-Validated Causal Graph

针对高价值领域人工标注：

```
Cause
Condition
Decision
Outcome
Counter Evidence

```

### Phase 3 — Cognitive Causal Intelligence

基于积累的数据逐步实现：

- Causal Extraction；
- Counterfactual；
- Boundary Discovery；
- Predictive Validation。

---

# 27. Cognitive Runtime Safety Model

Runtime 必须遵循：

```text
Retrieve
   ↓
Check Context
   ↓
Check Boundary
   ↓
Check Trust
   ↓
Check Drift
   ↓
Check Risk
   ↓
Decision / Treatment
   ↓
Deliver Cognition
   ↓
Observe Outcome
```

检索到认知并不等于允许交付。Runtime 将校验结果映射为四级处置：

| Risk / State | Runtime 处置 | 说明 |
|---|---|---|
| R0：低风险、边界匹配、Trust 高 | **Allow** | 正常交付 |
| R1：轻微漂移或证据不足 | **Allow + Warning** | 附带证据、边界和风险提示 |
| R2：高风险、明显漂移、信任不足 | **Degrade / Review** | 降低权重、限制自动执行，必要时人工确认 |
| R3：边界冲突、资产挂起、疑似污染 | **Block** | 不进入自动决策链，进入 Control Plane 处置 |

处置结果必须产生 Runtime Decision Event，并进入后续 Attribution / Validation。

### 27.1 Risk Mapping Baseline

风险评分可以采用：

```
Risk = Impact × Uncertainty × Drift × Exposure
```

各维度归一化到 0~1。默认：

- R0：Risk < 0.20；
- R1：0.20 ≤ Risk < 0.40；
- R2：0.40 ≤ Risk < 0.70；
- R3：Risk ≥ 0.70，或命中任何 Critical 安全条件。

该阈值仅作为 MVP 基线，高风险行业应通过治理配置收紧。

---

# 28. End-to-End Example

以：

> **AI 推理服务 P99 延迟异常**

为例。

---

## T0 — Decision Snapshot

系统发现：

```
P99 Latency ↑
GPU Utilization ↑
KV Cache Pressure ↑

```

工程师决定：

> 暂不扩容 GPU，优先检查 KV Cache 管理。

此时记录：

- Context；
- Evidence；
- Reasoning；
- Confidence。

---

## T1 — Execution

执行：

> 调整 KV Cache eviction policy。

---

## T2 — Outcome

结果：

```
P99 ↓ 28%
GPU Cost unchanged

```

Outcome 单独记录。

---

## T3 — Episode

系统生成：

> 在高并发长上下文场景下，KV Cache pressure 可能比 GPU capacity 更早成为 P99 latency 的主要瓶颈。

---

## T4 — Pattern

多个类似案例出现：

```
Long Context
+
High Concurrency
+
KV Pressure
→
Latency Degradation

```

形成 Pattern。

---

## T5 — Challenge

在不同模型、不同 GPU、不同业务负载下验证。

发现：

> 当 Context Length < X 时，该 Pattern 并不成立。

因此产生 Boundary。

---

## T6 — Model Split

形成：

```
Model-A
Long Context + High Concurrency
→ KV Pressure dominant

Model-B
Short Context
→ Compute dominant

```

原有模型不删除，而是拆分。

---

## T7 — Reuse & Attribution

新的故障发生时，系统调用 Model-A。

工程师因此避免 GPU 扩容，选择 KV 优化。

系统记录：

```
Usage = 1
Influence = 1
Outcome = Success
Attribution = High

```

---

## T8 — Evolution

环境发生变化：

> Runtime 升级，新 KV Cache 管理机制上线。

Drift Score 上升。

Model-A 自动：

```
Confidence ↓
Challenge Priority ↑

```

重新进入验证。

这就是完整的：

> **Capture → Validate → Reuse → Attribute → Evolve**

---

# 29. Metrics

CCI 不再追求单一 KPI。

建立三层指标。

## Layer 1 — Operational

- Capture Rate；
- Validation Rate；
- Challenge Cost；
- Runtime Latency；
- Reuse Rate；
- Error Rate。

---

## Layer 2 — Cognitive

- Evidence Sufficiency；
- Promotion Accuracy；
- Demotion Accuracy；
- Boundary Discovery Rate；
- Attribution Accuracy；
- Cognitive Recovery Rate；
- State Transition Correctness；
- Poisoning Detection / Containment Rate；
- Runtime Safe Delivery Rate。

---

## Layer 3 — Business

- Decision Quality；
- Time to Decision；
- Incident Recurrence；
- Expert Dependency；
- Cost Avoidance；
- Business Outcome。

最终关注：

> **Cognitive Loss Rate**

而不是：

> 文档数量。

---

# 30. Controlled Cognitive Experiment

CCI 的价值必须通过实验验证。

基本模型：

```
Control Group
      vs
CCI Group

```

比较：

- Decision Time；
- Decision Quality；
- Error Rate；
- Incident Recurrence；
- Expert Escalation；
- Cost。

并进行：

- Pre/Post；
- A/B；
- Shadow；
- Controlled Trial。

最终计算：

> **CCI Marginal Decision Impact**

---

# 31. MVP

CCI 不需要一开始建设复杂基础设施。

推荐：

```
PostgreSQL
+
pgvector
+
Object Storage
+
LLM
+
Event Store

```

MVP 不追求：

> 10000 个文档。

而验证：

> **100 个高质量 Cognitive Episodes 是否能够形成真正可复用的认知闭环。**

---

## MVP Success Criteria

1. Episode 捕获成功；
2. T0/T2 时间隔离有效；
3. Evidence 可以追溯；
4. 至少形成一批可验证 Pattern；
5. 至少发生一次模型拆分/降级；
6. 至少证明一次 Cognitive Attribution；
7. 至少完成一次受控决策改善实验；
8. 至少验证一次状态回滚或错误认知隔离；
9. 至少验证一次 Runtime 分级处置。

---

# 32. Implementation Roadmap

## Phase 1 — Cognitive Capture

重点：

- Episode；
- Snapshot；
- Provenance；
- Event Sourcing。

---

## Phase 2 — Cognitive Runtime

重点：

- Retrieval；
- Context Assembly；
- Boundary Check；
- Decision Support。

---

## Phase 3 — Cognitive Control Plane

重点：

- Validation；
- Challenge；
- Promotion；
- Demotion；
- Split；
- Decay。

---

## Phase 4 — Cognitive Attribution

重点：

- Explicit Attribution；
- AI-assisted Attribution；
- Controlled Experiment。

---

## Phase 5 — Cognitive Economy

重点：

- Contribution；
- Credit；
- Governance；
- Enterprise Incentive。

---

## Phase 6 — Industry Cognitive Network

最终实现：

```
Individual
   ↓
Team
   ↓
Enterprise
   ↓
Industry
   ↓
Cross-Organization

```

但跨组织认知共享必须建立在：

> **Trust + Provenance + Authorization + Compliance**

之上。

---

# 33. What CCI Is — and Is Not

CCI **不是**：

- Document Management；
- Knowledge Base；
- Vector Database；
- RAG；
- Agent Memory；
- Expert System。

CCI 是：

> **A Runtime for Human Cognition.**

它保存的不是简单的答案，而是：

> **Decision + Context + Evidence + Reasoning + Outcome + Boundary**

它运行的不是静态知识，而是：

> **Evidence-backed Cognitive Models**

它优化的不是：

> Search Relevance

而是：

> **Decision Quality**

它最终要解决的不是：

> “企业知道什么？”

而是：

> **“企业曾经如何思考，以及这些认知今天是否仍然值得相信？”**

---

# 34. Final Architecture Principle

CCI V2.2 最终可以浓缩为一个闭环：

```
        HUMAN EXPERIENCE
               │
               ▼
           CAPTURE
               │
               ▼
          COGNITIVE
           EPISODE
               │
               ▼
          VALIDATION
               │
               ▼
      COGNITIVE RUNTIME
               │
               ▼
             REUSE
               │
               ▼
          ATTRIBUTION
               │
               ▼
           EVOLUTION
          /    |     \
    Promote  Split   Demote
              │        │
              └──Decay─┘
                   │
                   ▼
              REACTIVATE
                   │
                   └──────────→ RUNTIME

```

最终形成：

> **Capture → Evidence → Runtime → Decision → Attribution → Evolution**

这不是一个知识库的生命周期。

这是一个**认知系统的生命周期**。

---

# Conclusion

文字让人类第一次能够跨越个体保存思想。

印刷让知识能够大规模复制。

互联网让知识能够全球传播。

云计算让计算能力成为基础设施。

AI 让机器开始参与认知。

而 CCI 所探索的问题是下一步：

> **当机器开始参与人类决策之后，我们能否把人类真正有价值的认知本身，也变成一种可以运行、验证、传承和持续进化的基础设施？**

因此，CCI 的最终目标不是：

> **保存更多知识。**

而是：

> **降低高价值认知的损失率。**

不是让 AI 永远替人思考。

而是：

> **让每一次重要决策，都能够留下可验证的认知资产；让每一次成功与失败，都能够反过来改善下一次决策。**

最终：

> **Knowledge tells us what is known.**
> **Cognition tells us why we decided.**
> **CCI makes that cognition reusable, verifiable and evolvable.**

这就是 CCI 的核心价值：

> **From Knowledge Management**
> **to Cognitive Runtime.**

> **From Information Preservation**
> **to Cognitive Continuity.**

V2.2 的下一步不是继续增加顶层概念，而是把本版本定义的状态、数据、事件、参数和安全策略进一步固化为接口与实现规范。
