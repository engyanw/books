# CCI 参考实现 V2.3

## —— Cognitive Runtime 技术规范

### API · 数据模型 · 状态机 · 事件模型 · Policy · Runtime · POC

---

# 0. 文档定位

V2.2 定义了 CCI 的参考架构，并建立了 Capture、Evidence、Runtime、Attribution 和 Evolution 五大核心机制。

V2.3 **不引入新的架构范式**，其目标是将 V2.2 转化为一份工程团队可以直接实现、测试和验证的：

> **Reference Implementation / Technical Specification（参考实现与技术规范）**

V2.3 遵循一个核心原则：

> **不增加顶层概念，只将已有概念转化为可执行技术契约。**

因此，本版本重点下沉以下内容：

* API 契约
* 核心数据 Schema
* Cognitive Asset 状态机
* Event Sourcing 事件模型
* Runtime 执行流程
* Policy 模型与决策规则
* Attribution 协议
* Evidence 与 Promotion 规则
* Drift 与 Verification Budget
* Security 与 Rollback
* Observability
* POC 架构与验收标准

V2.3 是一份**参考实现规范**，而不是强制性的生产实现标准。

底层存储、向量数据库、LLM Provider、部署平台均可以替换，但必须保持本规范定义的**语义、状态、不变量和安全边界**不变。

---

# 1. 设计原则

V2.3 继承 V2.2 的八条第一性原理。

在此基础上，增加六条工程实现不变量。

## I1 —— 历史不可变

T0 时刻的决策状态以及历史事件：

> **MUST NOT be overwritten**

不得被后续结果覆盖、修改。

历史是事实，不是当前状态的派生结果。

---

## I2 —— 状态转换必须合法

Cognitive Asset 只能通过：

> **合法状态转换 + 可审计事件**

改变状态。

任何直接修改数据库状态的行为均不属于合法状态转换。

---

## I3 —— 证据先于晋升

任何认知资产：

> **不得仅因为使用量、流行度或 LLM Confidence 而晋升。**

Promotion 必须由 Evidence、Context、Outcome、Counter-Evidence 等正式机制支撑。

---

## I4 —— Policy 先于 Runtime 交付

> **Retrieval ≠ Delivery**

认知被召回，并不意味着认知可以直接交付。

Runtime 必须依次完成：

* Context Check
* Boundary Check
* Trust Check
* Drift Check
* Risk Check
* Policy Check

之后才能决定是否交付。

---

## I5 —— 归因可以修正，历史不能修改

Attribution 可以通过新的补偿事件进行修正：

> Attribution Correction ≠ Historical Mutation

原始 Attribution Event 必须保持不可变。

---

## I6 —— 高风险认知默认 Fail Closed

如果高风险决策所需的：

* Evidence
* Policy
* Trust
* Boundary

无法获得或状态未知，Runtime：

> **不得默默将该认知作为权威认知交付。**

---

# 2. 参考实现架构

```text
Experience / Application
        |
        v
+-----------------------------+
| Cognitive Runtime           |
| API Gateway                 |
| Context Assembly            |
| Retrieval                   |
| Policy Evaluation           |
| Boundary / Drift / Risk     |
| Cognitive Delivery          |
| Attribution Capture        |
+-------------+---------------+
              |
       Cognitive Data Plane
              |
+-------------v---------------+
| Cognitive Memory             |
| Episode / Pattern / Model   |
| Evidence / Boundary         |
| Provenance / Attribution    |
+-------------+---------------+
              |
+-------------v---------------+
| Cognitive Control Plane      |
| Validation / Challenge       |
| Promotion / Demotion         |
| Split / Merge / Decay        |
| Drift / Budget / Governance  |
| Security / Rollback          |
+-------------+---------------+
              |
+-------------v---------------+
| Event & Evidence Foundation |
| Event Store / Object Store  |
| PostgreSQL / pgvector       |
| Audit / Hash / Relations    |
+-----------------------------+
```

## 2.1 Plane 语义

### Cognitive Data Plane

同步、面向决策。

负责：

* Cognitive Retrieval
* Context Assembly
* Boundary Evaluation
* Drift Evaluation
* Policy Evaluation
* Cognitive Delivery

并具有明确的 Runtime Latency 目标。

### Cognitive Control Plane

异步、面向演化。

负责：

* Validation
* Challenge
* Promotion / Demotion
* Split / Merge
* Decay
* Drift
* Budget
* Governance
* Security
* Rollback

### Cognitive Memory

持久化的认知状态。

### Event & Evidence Foundation

不可变的：

* 历史事件
* Evidence
* Audit
* Hash
* Provenance

底座。

核心关系可以归纳为：

> **Data Plane 让认知生效；Control Plane 决定认知是否继续生效。** 

---

# 3. API 规范

CCI V2.3 提供四类逻辑接口：

1. Capture API
2. Runtime API
3. Control API
4. Attribution API

参考实现统一采用：

> JSON over HTTPS

内部服务可以采用 gRPC。

---

## 3.1 公共 Header

```http
Authorization: Bearer <token>
X-Tenant-ID: <tenant>
X-Request-ID: <request-id>
X-Correlation-ID: <correlation-id>
X-CCI-Version: 2.3
Idempotency-Key: <key>
```

其中：

* `X-Tenant-ID`：租户边界
* `X-Request-ID`：单次请求标识
* `X-Correlation-ID`：端到端因果链路
* `X-CCI-Version`：CCI API Contract Version
* `Idempotency-Key`：保证 Command 幂等

---

# 3.2 Capture API

## POST `/v1/episodes`

创建 Cognitive Episode。

```json
{
  "decision": {
    "summary": "优先进行 KV Cache 优化",
    "options": [
      "GPU 扩容",
      "KV 优化"
    ],
    "selected": "KV 优化"
  },
  "context": {
    "service": "inference-api",
    "model": "model-x",
    "traffic_level": "high",
    "context_length": 32768
  },
  "evidence": [
    {
      "source_id": "metric-123",
      "type": "metric"
    }
  ],
  "reasoning": "KV pressure increased before compute saturation",
  "constraints": [
    "当前窗口禁止 GPU 扩容"
  ],
  "confidence": 0.78,
  "value_level": "A"
}
```

返回：

```json
{
  "episode_id": "ep_01J...",
  "state": "QUARANTINED",
  "event_id": "evt_01J...",
  "created_at": "2026-08-11T12:00:00Z"
}
```

新认知默认进入：

> **QUARANTINED**

而不是直接进入 ACTIVE。

---

# 3.3 Runtime API

## POST `/v1/runtime/query`

```json
{
  "intent": "诊断 P99 延迟",
  "context": {
    "service": "inference-api",
    "model": "model-x",
    "traffic": 12000,
    "context_length": 32768
  },
  "risk": "high",
  "requested_mode": "explain"
}
```

返回：

```json
{
  "decision": "USE_COGNITION",
  "delivery_mode": "EXPLAIN",
  "candidates": [
    {
      "asset_id": "model_a",
      "confidence": 0.87,
      "applicability": 0.91,
      "evidence_refs": [
        "ev_123",
        "ev_456"
      ],
      "boundary": "context_length >= 16K"
    }
  ],
  "policy": {
    "risk_level": "R2",
    "action": "ALLOW_WITH_EXPLANATION"
  }
}
```

---

# 3.4 Attribution API

## POST `/v1/attributions`

```json
{
  "decision_id": "dec_123",
  "asset_id": "model_a",
  "level": "KEY_INFLUENCE",
  "source": "EXPLICIT",
  "confidence": 0.90,
  "outcome_id": "out_123"
}
```

---

# 3.5 Control API

```text
GET  /v1/assets/{id}
GET  /v1/assets/{id}/history

POST /v1/assets/{id}/validate
POST /v1/assets/{id}/challenge
POST /v1/assets/{id}/promote
POST /v1/assets/{id}/demote
POST /v1/assets/{id}/split
POST /v1/assets/{id}/rollback
POST /v1/assets/{id}/reactivate
```

所有 Promotion、Rollback 等操作均为：

> **Command**

而不是直接修改数据库。

其执行链必须是：

```text
API Command
     ↓
Event
     ↓
State Machine
     ↓
Materialized State
```



---

# 4. 核心数据模型

参考实现采用 PostgreSQL 作为 System of Record。

---

## 4.1 CognitiveAsset

```text
CognitiveAsset
----------------------------
id
asset_type              # EPISODE | PATTERN | MODEL | PRINCIPLE
version
state
value_level             # S | A | B | C
owner_id
steward_id
trust_level
confidence
applicability
es_score
risk_level
created_at
updated_at
valid_from
valid_to
parent_asset_id
canonical_hash
schema_version
```

---

# 4.2 Episode

```text
Episode
----------------------------
episode_id
asset_id
decision_snapshot_id
context_snapshot_id
evidence_set_id
reasoning_snapshot_id
constraint_snapshot_id
outcome_id
boundary_id
provenance_id
attribution_id
confidence
capture_source
created_at
```

Episode 必须能够独立保存：

* T0 Decision Snapshot
* Context Snapshot
* Evidence
* Reasoning
* Constraint

从数据层面保证：

> **后续 Outcome 不得污染 T0 决策事实。**

---

# 4.3 Evidence

```text
Evidence
----------------------------
evidence_id
source_id
source_type
content_hash
observed_at
valid_from
valid_to
quality_score
independence_score
provenance
verification_status
```

Evidence 采用：

> **Reference，而非静默复制。**

原始 Evidence 必须保持可寻址、可验证。

---

## 4.3.1 Evidence Quality 与 Independence

Quality 和 Independence 均归一化到：

```text
[0,1]
```

参考来源质量先验：

| Evidence 来源    | Quality Prior |
| -------------- | ------------: |
| 直接系统指标 / Trace |          0.90 |
| 结构化应用日志        |          0.85 |
| 已验证运维文档        |          0.75 |
| 专家观察           |          0.70 |
| 用户陈述           |          0.50 |
| 未验证外部信息        |          0.30 |

这些只是：

> **Reference Default**

不是行业真理。

最终 Quality 必须结合：

* Verification Status
* Freshness
* Integrity
* Provenance

并保留各分项用于审计。

Evidence Independence 必须追溯到：

> **Root Source**

如果多个 Evidence 实际来自同一个上游源，则不能被视为多个独立证据。

参考规则：

```text
independence = 1 - max(source_correlation_weight)
```

验证等级：

```text
UNVERIFIED
    <
PARTIALLY_VERIFIED
    <
VERIFIED
    <
INDEPENDENTLY_VERIFIED
```

高风险 Promotion 不能仅依赖 UNVERIFIED Evidence。

---

# 4.4 Boundary

```text
Boundary
----------------------------
boundary_id
asset_id
condition_expression
condition_type
confidence
source
status
last_verified_at
```

例如：

```text
context_length >= 16384
AND concurrency >= 1000
AND kv_pressure >= 0.75
```

Boundary 必须满足：

* Deterministic
* Auditable
* Versioned
* Runtime Executable

---

## 4.4.1 Boundary Expression Standard

参考实现采用：

> **CEL（Common Expression Language）语义子集**

允许：

```text
&&
||
!
比较运算
in
基础类型
受限集合访问
```

禁止：

* 网络访问
* 文件系统访问
* 数据库访问
* Process API
* 任意函数调用

Runtime 必须拒绝：

* 未声明变量
* 超过 AST 限制
* 超过 Evaluation Cost
* 非授权函数
* 非确定性表达式

Boundary Evaluation 只能返回：

```text
MATCH
MISMATCH
UNKNOWN
INVALID
```

其中：

> `UNKNOWN ≠ MATCH`

对于 R2/R3：

* UNKNOWN → 不得直接允许
* INVALID → Fail Closed

并生成审计事件。

---

# 4.5 Attribution

```text
Attribution
----------------------------
attribution_id
decision_id
asset_id
source
influence_level
confidence
counterfactual_method
outcome_id
reviewer_id
status
created_at
```

---

# 5. Event Model

CCI 使用 Event Sourcing 保存历史认知状态。

---

## 5.1 Event Envelope

```json
{
  "event_id": "evt_123",
  "event_type": "AssetPromoted",
  "aggregate_type": "CognitiveAsset",
  "aggregate_id": "model_123",
  "aggregate_version": 7,
  "occurred_at": "2026-08-11T12:00:00Z",
  "actor": {
    "type": "human",
    "id": "user_123"
  },
  "correlation_id": "corr_123",
  "causation_id": "evt_122",
  "schema_version": "2.3",
  "payload_hash": "sha256:...",
  "payload": {}
}
```

---

# 5.2 核心事件

```text
EpisodeCreated
EvidenceAttached
ValidationStarted
ValidationCompleted
ChallengeStarted
ChallengeCompleted
ConflictDetected
BoundaryDiscovered
AssetPromoted
AssetDemoted
AssetSplit
AssetMerged
AssetSuspended
AssetDecayed
AssetReactivated
AttributionRecorded
AttributionCorrected
DriftDetected
PolicyEvaluated
CognitiveDelivered
RollbackRequested
RollbackCompleted
PoisoningDetected
QuarantineApplied
```

---

# 5.3 Event Rules

1. Event 只能追加，不能删除；
2. Aggregate Version 单调递增；
3. Event 必须支持幂等处理；
4. Consumer 必须能够容忍重复 Event；
5. Schema Evolution 必须保持向后读取能力；
6. Correction 必须通过新 Event 实现；
7. 历史 Event 永远不能被修改。

因此：

> **Correction 是新的事实，而不是对旧事实的覆盖。** 

---

# 6. Cognitive Asset 状态机

## 6.1 状态

```text
DRAFT
  ↓
QUARANTINED
  ↓
VALIDATED
  ↓
ACTIVE
  ↓
DEGRADED
  ↓
SUSPENDED
  ↓
ARCHIVED
```

额外操作状态：

```text
ROLLBACK_PENDING
ROLLBACK_IN_PROGRESS
```

---

## 6.2 状态语义

| 状态          | 含义         | Runtime |
| ----------- | ---------- | ------- |
| DRAFT       | 不完整资产      | 不可见     |
| QUARANTINED | 未可信新认知     | 不可见     |
| VALIDATED   | 证据足够，可受控使用 | 受限      |
| ACTIVE      | 正式生效       | 正常      |
| DEGRADED    | 可信度/适用性下降  | 风险相关    |
| SUSPENDED   | 暂时停用       | 不可用     |
| ARCHIVED    | 历史归档       | 不可用     |

---

# 6.3 Promotion

### QUARANTINED → VALIDATED

要求：

* 最低 Evidence Quality
* 完整 Provenance
* 必要时必须存在 Boundary
* 不存在未解决的高风险 Poisoning Alert

### VALIDATED → ACTIVE

要求：

* ES Threshold
* 跨 Context Evidence
* Counter-Evidence 可接受
* A/S 级资产需要相应人工授权

---

# 6.4 Demotion

### ACTIVE → DEGRADED

触发：

* Drift
* Counter-Evidence 增加
* Outcome Stability 下降
* Confidence 下降

### DEGRADED → SUSPENDED

当发生：

* 高风险 Boundary 违规
* Trust 不满足
* Policy 不允许

则进入 SUSPENDED。

---

# 6.5 Rollback

Rollback：

> **永远不能删除历史。**

例如：

```text
ACTIVE V7
   ↓
ROLLBACK_PENDING
   ↓
ROLLBACK_IN_PROGRESS
   ↓
SUSPENDED / V6
   ↓
REVALIDATION
   ↓
ACTIVE V8
```

---

## 6.6 Transition Contract

所有状态转换必须检查：

1. 当前状态；
2. 是否允许转换；
3. Guard Condition；
4. 是否生成对应 Event。

未列出的状态转换：

> **一律拒绝。**

| From                 | To                   | Trigger / Guard               |
| -------------------- | -------------------- | ----------------------------- |
| DRAFT                | QUARANTINED          | Submit + Schema Valid         |
| QUARANTINED          | VALIDATED            | Evidence / Provenance         |
| VALIDATED            | ACTIVE               | ES + Domain Guard + Authority |
| ACTIVE               | DEGRADED             | Drift / Counter-Evidence      |
| DEGRADED             | ACTIVE               | Revalidation                  |
| DEGRADED             | SUSPENDED            | High-risk Boundary / Policy   |
| SUSPENDED            | VALIDATED            | Evidence / Policy Restored    |
| SUSPENDED            | ARCHIVED             | Retirement                    |
| Mutable              | ROLLBACK_PENDING     | Authorized Rollback           |
| ROLLBACK_PENDING     | ROLLBACK_IN_PROGRESS | Target Version Exists         |
| ROLLBACK_IN_PROGRESS | SUSPENDED            | Rollback Verified             |

ARCHIVED 对 Runtime 来说是终态。

重新激活必须经过：

> Explicit Command → Validation



---

# 7. Evidence Sufficiency

V2.3 保留 V2.2 的 ES 模型，同时增加可执行评分机制。

```text
ES = Σ(wᵢ × sᵢ)
```

其中：

```text
Σwᵢ = 1
0 ≤ sᵢ ≤ 1
0 ≤ ES ≤ 1
```

六个维度：

1. Evidence Quality
2. Context Diversity
3. Outcome Stability
4. Counter-Evidence Resistance
5. Expert Validation
6. Temporal Stability

---

## 7.1 SRE 默认基线

| 维度                          |   权重 |
| --------------------------- | ---: |
| Evidence Quality            | 0.20 |
| Context Diversity           | 0.15 |
| Outcome Stability           | 0.25 |
| Counter-Evidence Resistance | 0.15 |
| Expert Validation           | 0.15 |
| Temporal Stability          | 0.10 |

参考晋升基线：

```text
Episode → Pattern
ES >= 0.60

Pattern → Model
ES >= 0.75

Model → Principle
ES >= 0.85 + Expert Approval
```

这些是：

> **Reference Defaults**

而不是绝对标准。

---

## 7.2 Guard Conditions

即使 ES 达标，如果存在以下情况也不能 Promotion：

* Provenance 不完整；
* 关键 Counter-Evidence 未解决；
* 高风险 Model 的 Boundary Unknown；
* Policy 已过期；
* Poisoning Investigation 尚未关闭。

---

## 7.3 Domain Evidence Profile

不同领域可以覆盖默认：

* ES Weights
* Thresholds
* Independent Evidence Requirements
* Expert Review Conditions

但 Profile 必须：

* Versioned
* Owned
* Reviewable

Profile 发生变化：

> **不能重写历史 ES。**

新 Profile 只适用于生效时间之后的计算，并产生对应 Event。

---

# 8. Policy Model

Policy 是 Runtime 交付前的：

> **最终权威控制点。**

---

## 8.1 Policy Object

```json
{
  "policy_id": "pol_001",
  "scope": "inference-api",
  "risk_level": "R2",
  "min_trust": 0.80,
  "max_drift": 0.40,
  "required_es": 0.75,
  "required_evidence": true,
  "human_approval": false,
  "action_on_failure": "DEGRADE"
}
```

---

# 8.2 风险等级

```text
R0 — 信息型
R1 — 低影响
R2 — 具有实际业务影响
R3 — 高影响 / 安全 / 财务 / 监管
```

---

# 8.3 Runtime Decision

```text
IF trust < min_trust
    → BLOCK

ELSE IF drift > max_drift
    → DEGRADE / REVIEW

ELSE IF ES < required_es
    → BLOCK for R2/R3
    → WARN for R0/R1

ELSE IF boundary mismatch
    → BLOCK

ELSE
    → ALLOW
```

---

# 8.4 Policy Actions

```text
ALLOW
ALLOW_WITH_WARNING
ALLOW_WITH_EXPLANATION
DEGRADE
REQUIRE_HUMAN_REVIEW
BLOCK
```

Policy Evaluation 必须先于：

> `CognitiveDelivered`

并生成 `PolicyEvaluated` Event。

---

# 8.5 DEGRADE 的正式语义

DEGRADE 不能只是一个模糊的“降低可信度”。

参考定义五种降级：

```text
D1 Confidence Reduction
D2 Scope Reduction
D3 Evidence-Only Delivery
D4 Challenge-First Delivery
D5 Human-Review Required
```

| Failure                    | 默认    | R2/R3       |
| -------------------------- | ----- | ----------- |
| Moderate Drift             | D1/D2 | D2/Review   |
| ES 不足                      | D3    | BLOCK       |
| Boundary UNKNOWN           | D3    | BLOCK       |
| Trust 不足                   | D3    | BLOCK       |
| Policy 过期                  | D5    | BLOCK       |
| Infrastructure Uncertainty | D3    | Fail Closed |

任何 Degraded Response：

> **必须明确标记为 Non-Authoritative。**

不能表现为 `ALLOW`。

---

# 9. Runtime 执行规范

Runtime 请求链路：

```text
Request
  ↓
Authenticate
  ↓
Build Context Snapshot
  ↓
Retrieve Candidate Cognition
  ↓
Filter by Trust / State
  ↓
Evaluate Boundary
  ↓
Evaluate Drift
  ↓
Evaluate Evidence / ES
  ↓
Evaluate Risk
  ↓
Evaluate Policy
  ↓
Select Delivery Mode
  ↓
Deliver Cognition
  ↓
Record Decision
  ↓
Observe Outcome
  ↓
Attribution
```

Runtime 必须保证：

* ARCHIVED 不可交付；
* QUARANTINED 不得作为权威认知交付；
* 高风险 Boundary Failure 不得忽略；
* T0 Snapshot 不可修改；
* Retrieval Rank ≠ Trust；
* Outcome Success ≠ Causal Attribution。

---

# 9.3 Retrieval Contract

Runtime Retrieval：

```text
Candidate Recall
      ↓
Deterministic Filtering
      ↓
Re-ranking
      ↓
Policy Evaluation
```

参考 Ranking：

```text
RetrievalScore =
  0.35 × SemanticSimilarity
+ 0.20 × ContextMatch
+ 0.15 × BoundaryMatch
+ 0.15 × Applicability
+ 0.10 × Trust
+ 0.05 × EvidenceSufficiency
```

参考最低 Semantic Similarity：

```text
R0/R1 ≥ 0.65
R2    ≥ 0.72
R3    ≥ 0.80
```

但是：

> **Retrieval Score 永远不能作为 Authorization Decision。**



---

# 9.4 Runtime 性能参考目标

这些是：

> **POC Engineering Target**

而不是生产环境 SLA。

| 指标                    |     参考目标 |
| --------------------- | -------: |
| Runtime p50           |  ≤ 80 ms |
| Runtime p95           | ≤ 150 ms |
| Runtime p99           | ≤ 300 ms |
| Retrieval p99         | ≤ 100 ms |
| Policy Evaluation p99 |  ≤ 20 ms |

容量验证建议至少覆盖：

```text
10K Assets
100K Assets
1M Assets
```

规模增长不能破坏安全语义和尾延迟目标。

---

# 9.5 Runtime Failure Semantics

```text
Boundary Failure
    → BLOCK / D3

Policy Failure
    → BLOCK

Evidence Failure
    → D3 / BLOCK

Retrieval Failure
    → SAFE FALLBACK

Infrastructure Failure
    → SAFE FALLBACK

LLM Failure
    → Deterministic Fallback / No-Authority Response
```

任何 Fallback：

> **不得把不可用认知静默升级成权威认知。**

---

# 10. Attribution Protocol

Attribution 是独立于 Outcome Recording 的生命周期。

---

## 10.1 Attribution Levels

```text
NONE
PARTIAL
INFLUENTIAL
KEY_INFLUENCE
```

---

## 10.2 Confidence

```text
LOW       < 0.60
MEDIUM    0.60–0.85
HIGH      > 0.85
```

这些为参考默认值。

---

# 10.3 Attribution Correction

```text
AttributionRecorded
        ↓
Later Evidence
        ↓
AttributionCorrectionRequested
        ↓
Review
        ↓
AttributionCorrected
```

原始 Attribution Event 永远保留。

---

# 10.4 L2 Assisted Attribution

L2 AI 辅助归因：

> **只能生成 Candidate，不能成为最终权威。**

核心变量：

1. Decision Delta
2. Exposure
3. Adoption Evidence
4. Outcome Consistency

参考公式：

```text
AttributionScore =
  0.35 × DecisionDelta
+ 0.20 × Exposure
+ 0.25 × AdoptionEvidence
+ 0.20 × OutcomeConsistency
```

结果必须携带：

> **Uncertainty**

对于 R2/R3：

> L2 Attribution 不得仅凭模型判断升级为 `KEY_INFLUENCE`。

必须具有：

* Explicit Evidence
* Experimental Evidence

之一。

同时需要使用人工审核样本进行 Calibration。

---

# 11. 环境漂移

V2.3 将 V2.2 的 Drift Score 转化为可执行流水线：

```text
Technology Drift
Business Drift
Policy Drift
        ↓
Signal Normalization
        ↓
Weighted Drift Score
        ↓
Asset Applicability
        ↓
Confidence / Decay
        ↓
Challenge Priority
```

参考：

```text
Drift =
  0.40 × Technology
+ 0.35 × Business
+ 0.25 × Policy
```

---

## Drift Action Bands

```text
0.00–0.20   Normal
0.20–0.40   Observe
0.40–0.60   Challenge
0.60–0.80   Degrade
0.80–1.00   Suspend / Revalidate
```

这些参数均属于：

> **Implementation Default**

可由 Domain Evidence Profile 配置。

---

# 12. Verification Budget

Challenge Engine 必须运行在有限预算内。

参考预算：

```text
S   40%
A   30%
B   20%
C   10%
```

Challenge Priority：

```text
Risk × Impact × Uncertainty × Drift
-----------------------------------
Verification Cost
```

形成完整反馈：

```text
Challenge
    ↓
Cost
    ↓
Risk Reduction
    ↓
Knowledge Gain
    ↓
Budget Adjustment
```

连续三次低收益 Challenge：

> 可以降低该资产后续预算。

如果发现：

* Material Boundary
* High-Severity Counter-Example
* Policy Violation

则提高后续 Challenge Priority。

---

# 12.1 Control Plane Task Scheduling

控制平面任务必须：

* Durable
* Idempotent

参考优先级：

```text
P0 Security / Rollback / High-Risk Boundary
P1 Critical Drift / Policy Expiry
P2 Promotion / Demotion / Validation
P3 Challenge / Attribution Review
P4 Background Maintenance
```

每个 Task 必须携带：

```text
task_id
idempotency_key
priority
budget_reservation
retry_policy
deadline
execution_lease
terminal_outcome
```

触发方式支持：

* Event Trigger
* Schedule Trigger
* Command Trigger

预算必须在执行前 Reservation。

取消或超时后返还。

参考 Retry：

```text
Transient Failure
→ 最多 3 次指数退避

Deterministic Validation Failure
→ 不自动 Retry

Security Failure
→ Quarantine / Manual Review
```



---

# 13. Security 与 Cognitive Poisoning

## 13.1 Detection

重点监测：

* Contribution Burst
* 异常 Promotion Concentration
* Attribution Concentration
* Suspicious Reference Graph
* Coordinated Behavior
* Weak Evidence Diversity
* Counter-Evidence Suppression

---

# 13.2 Poisoning Response

```text
Detection
    ↓
Quarantine
    ↓
Investigation
    ↓
Decision
 ┌───────┴────────┐
 ↓                ↓
False Positive   Confirmed Poisoning
 ↓                ↓
Restore          Rollback
                  ↓
             Freeze Credit
                  ↓
             Revalidation
```

Security Event：

> **不能修改历史 Evidence。**

只能产生：

> Compensating State + Compensating Event

---

# 13.3 Poisoning Risk

风险统一归一化：

```text
[0,1]
```

参考：

```text
0.00–0.30   Observe
0.30–0.60   Enhanced Review
0.60–0.80   Quarantine
0.80–1.00   Immediate Quarantine + Rollback Review
```

确认 Poisoning 后必须：

1. Quarantine 受影响资产；
2. Freeze Cognitive Credit；
3. 找出依赖资产；
4. 产生 Rollback / Revalidation Event；
5. 检查相关 Attribution；
6. Independent Revalidation；
7. 验证通过后才允许恢复。

Credit Correction 同样必须采用 Event Sourcing。

---

# 14. Governance 与 Authorization

参考角色：

```text
Contributor
Steward
Reviewer
Domain Expert
Security Administrator
System Administrator
```

核心原则：

> **任何单一角色都不应独立控制高价值认知的贡献、验证、晋升和最终治理。**

S/A 级 Promotion 应采用 SoD。

---

# 14.1 Trust Domains

```text
Individual
Team
Enterprise
Industry
Public
```

跨域共享必须具备：

```text
Identity
Authorization
Provenance
Purpose
Compliance
Revocation
```

---

# 14.2 RBAC

| Role           | Capture         | Validate        | Promote S/A | Promote B/C | Rollback           | Policy Admin |
| -------------- | --------------- | --------------- | ----------- | ----------- | ------------------ | ------------ |
| Contributor    | Create          | No              | No          | No          | No                 | No           |
| Steward        | Create          | Yes             | No          | Yes         | Request            | No           |
| Reviewer       | No              | Yes             | Yes         | Yes         | Request            | No           |
| Domain Expert  | No              | Yes             | Yes         | Yes         | Approve            | No           |
| Security Admin | Security Review | Security Review | Veto        | Veto        | Execute            | No           |
| System Admin   | Limited         | No              | No          | No          | Technical Recovery | Yes          |

权限可以进一步收紧，但不能削弱 S/A 的职责分离。

---

# 14.3 Multi-Tenant Isolation

参考实现默认采用：

> **Tenant-aware Row-Level Authorization**

更高安全要求可以采用：

* Schema Isolation
* Database Isolation

所有：

* Asset
* Event
* Evidence
* Attribution
* Policy

必须携带 Tenant / Security Domain Scope。

跨租户共享必须存在显式授权：

```text
Source
Target
Purpose
Asset / Version
Expiration
Revocation
Audit Reference
```

最重要的一条：

> **Vector Similarity 永远不产生 Authorization。**



---

# 15. Observability

V2.3 定义三类 Observability。

## Runtime

```text
p50 / p95 / p99 Latency
Retrieval Latency
Policy Evaluation Latency
Candidate Count
Block Rate
Fallback Rate
```

## Cognitive

```text
ES
Promotion Accuracy
Demotion Accuracy
Boundary Discovery Rate
Attribution Confidence
Rollback Rate
```

## Business

```text
Decision Quality
Time to Decision
Incident Recurrence
Expert Escalation
Cost Avoidance
Business Outcome
```

每次 Runtime Decision 都必须通过：

```text
X-Correlation-ID
```

贯穿：

> Retrieval → Policy → Delivery → Outcome → Attribution

---

# 15.1 Metric Definitions

```text
Block Rate
= Blocked Requests / All Runtime Requests

High-Risk Block Rate
= Blocked R2/R3 / All R2/R3

Promotion Accuracy
= Correct Promotions / Evaluated Promotions

Demotion Accuracy
= Correct Demotions / Evaluated Demotions

Safe Delivery Rate
= Policy-Compliant Deliveries / All Deliveries
```

指标必须至少支持：

* Tenant
* Domain
* Risk Level
* Policy Version

维度切分。

告警参考：

```text
High-risk Fail-Open
Poisoning containment failure
→ P0

Boundary UNKNOWN spike
p99 breach
→ P1

Promotion Accuracy < 95%
Attribution Calibration degradation
→ P1/P2
```

Runtime Trace 最小字段必须包括：

* Correlation ID
* Request ID
* Tenant ID
* Policy Version
* Context Snapshot
* Candidate Set
* Selected Asset
* Boundary Result
* Drift
* ES
* Policy Action
* Delivery Mode
* Outcome
* Attribution Reference



---

# 16. Reference Implementation 技术栈

最小实现保持简单：

```text
PostgreSQL
 ├── Cognitive Asset Metadata
 ├── State
 ├── Policy
 └── Attribution

pgvector
 └── Semantic Retrieval

Object Storage
 └── Evidence / Large Payload

Event Store
 └── Immutable Event History

LLM
 ├── Extraction
 ├── Candidate Generation
 ├── Explanation
 └── Assisted Attribution

Worker / Control Plane
 ├── Validation
 ├── Challenge
 ├── Drift
 ├── Promotion
 ├── Demotion
 └── Rollback
```

Graph Database 在 V2.3 中不是强制组件。

Evidence Relationship 初期可以直接由 PostgreSQL 表实现。

---

# 17. POC 架构

POC 的核心目标：

> **验证 Semantic Contract，而不是验证基础设施规模。**

```text
             +------------------+
             | Demo Application |
             +---------+--------+
                       |
                 Runtime API
                       |
             +---------v--------+
             | Cognitive Runtime|
             +----+--------+----+
                  |        |
             Data Plane   Policy
                  |        |
             +----v--------v----+
             | PostgreSQL       |
             | pgvector         |
             | Event Store      |
             +----+--------+----+
                  |        |
             +----v--------v----+
             | Control Workers  |
             | Validate/Challenge|
             | Drift/Rollback   |
             +------------------+
```

---

# 17.1 POC 场景

沿用 V2.2 的 AI 推理服务 P99 延迟异常案例：

```text
High Context
+
High Concurrency
+
KV Pressure
        ↓
P99 Latency Degradation
```

POC 必须完整演示：

```text
1. Capture T0 Snapshot
2. Create Episode
3. Quarantine
4. Attach Evidence
5. Promote Pattern / Model
6. Runtime Retrieval
7. Boundary Check
8. Policy Evaluation
9. Decision Delivery
10. Outcome Recording
11. Attribution
12. Drift Event
13. Challenge
14. Demotion / Split
15. Rollback
16. Revalidation
```

---

# 17.2 POC 性能与规模

性能测试属于：

> **Non-functional Validation**

不能改变语义验收标准。

至少测试：

```text
10K
100K
1M
```

资产规模。

同时测量：

* p50
* p95
* p99
* Retrieval Latency
* Policy Latency
* Control Backlog
* CPU
* Memory
* Storage Growth

无论规模如何增长：

> **Safety 与 Policy Correctness 必须保持不变。** 

---

# 18. POC Acceptance Criteria

## AC-01 Capture

T0 字段不完整：

> Reject 或 Quarantine

有效 Episode 必须保持：

* T0 Fields
* Provenance

完整。

另外，可以使用 100 个高质量 Episode 做：

> Repeatability / Load Test

但：

> **100 不是认知价值指标。**

---

## AC-02 Temporal Integrity

后续 Outcome：

> 不得修改 T0 Snapshot。

---

## AC-03 State Machine

每一次合法 State Transition：

> 必须生成合法 Event。

非法 Transition：

> 必须 Reject。

---

## AC-04 Evidence

所有 Promotion：

> 必须具备可追溯 Evidence + Provenance。

---

## AC-05 Runtime Safety

至少验证：

* 一个 Boundary Mismatch；
* 一个 High Drift。

并按照 Policy 正确：

> Block / Degrade。

---

## AC-06 Attribution

至少验证：

* 一次 Explicit Attribution；
* 一次 Assisted Attribution。

---

## AC-07 Evolution

至少完成：

* 一次 Promotion；
* 一次 Demotion 或 Split；
* 一次 Reactivation。

---

## AC-08 Rollback

人为注入一个错误 Model：

> 能够 Rollback，同时不能删除历史 Event。

---

## AC-09 Poisoning

注入 Synthetic Poisoning Pattern：

> 必须进入 Quarantine，不能进入 ACTIVE。

---

## AC-10 Controlled Experiment

CCI 路径相对于 Control Path：

> 必须能够证明 Decision Quality 或 Decision Time 的改善。

---

## AC-11 Retrieval Determinism

相同：

* Tenant
* Context Snapshot
* Asset State
* Policy Version

下：

> Filtering 与 Policy Evaluation 必须产生相同 Decision Class。

---

## AC-12 Degradation Semantics

不同 Failure：

* Drift
* Evidence
* Boundary

必须映射到预定义：

> Degrade / Block

动作，并明确标记 Non-Authoritative。

---

## AC-13 Multi-Tenant Isolation

Tenant A：

> 不得获取、修改或产生 Tenant B 的 Attribution。

除非存在显式 Share Grant。

---

## AC-14 Observability Completeness

给定 Correlation ID：

> 必须能够重建完整 Runtime Decision。

同时：

> 不允许修改历史 Event。



---

# 19. Test Strategy

V2.3 采用五层测试体系。

### Level 1：Unit Test

测试：

* State Transition
* Policy
* ES
* Drift
* Attribution

### Level 2：Contract Test

测试：

* API Schema
* Event Schema
* Backward Compatibility

### Level 3：Scenario Test

验证：

> End-to-End Cognitive Lifecycle

### Level 4：Adversarial Test

包括：

* Poisoning
* Evidence Manipulation
* Boundary Bypass
* Replay
* Duplicate Events

### Level 5：Controlled Experiment

比较：

```text
CCI-assisted Group
vs
Control Group
```

核心不变量必须转化成自动化 Assertion：

```text
assert(outcome.timestamp > snapshot.timestamp)

assert(snapshot.hash == original_snapshot_hash)

assert(
    state_transition_is_valid(previous, next, event)
)

assert(
    high_risk_boundary_failure
    =>
    delivery != ALLOW
)
```



---

# 20. Conflict 与 Split Specification

Conflict Detection：

* 高影响变更：同步
* Background Reconciliation：异步

Conflict 来源包括：

* Conclusion Conflict
* Boundary Overlap
* Evidence Contradiction
* Policy Contradiction
* Temporal Incompatibility

冲突等级：

```text
C0 Informational
C1 Review
C2 High-impact
C3 Safety / Regulatory
```

只有：

```text
C0 / C1
```

允许自动 Split，并且必须满足：

* Deterministic Partition Predicate
* Provenance-preserving Split

C2/C3：

> 必须经过人工 / Domain Expert Review。

Split 后：

* Parent Immutable
* Child 获得新 Identity
* Child 引用 Parent
* Evidence 显式继承
* 记录 Partition Rule
* 记录 Actor / Reviewer

并且：

> **继承 Evidence 不得重复计为 Independent Evidence。** 

---

# 21. Failure & Recovery Model

系统必须区分五类 Failure：

```text
Business Failure
Cognitive Failure
Policy Failure
Infrastructure Failure
Security Failure
```

对应：

### Business Failure

不自动意味着 Cognitive 失效。

### Cognitive Failure

触发：

> Demotion / Rollback

### Policy Failure

直接：

> BLOCK

### Infrastructure Failure

进入：

> SAFE FALLBACK

### Security Failure

进入：

> QUARANTINE + INVESTIGATION

对于高风险 Runtime：

> Policy / Boundary 信息不可用 → Fail Closed。

---

# 22. API / Event / State Consistency Contract

CCI 的三个核心接口通过一条统一因果链连接：

```text
API Command
     ↓
Event
     ↓
State Transition
     ↓
Materialized View
     ↓
Runtime Behavior
```

任何 API：

> **不得直接修改 Canonical Cognitive State。**

必须产生对应 Event。

最终形成一条完整因果链：

> **谁请求了什么 → 发生了什么 Event → 状态发生了什么变化 → Runtime 因此产生了什么行为。**



---

# 23. Versioning

V2.3 区分：

```text
Architecture Version
API Version
Schema Version
Event Version
Policy Version
Asset Version
```

兼容性原则：

* API Major Version 明确；
* Event Schema 必须向后可读；
* Cognitive Asset 携带 Schema Version；
* Policy Change 必须产生 Policy Version Event；
* Asset Version 与 Event Version 解耦。

---

# 24. Implementation Roadmap

## Stage 1 —— Foundation

* PostgreSQL
* pgvector
* Event Store
* API Gateway
* Asset Schema
* Event Schema

## Stage 2 —— Runtime

* Context Assembly
* Retrieval
* Boundary Evaluation
* Policy Engine
* Delivery Modes

## Stage 3 —— Control Plane

* Validation
* ES
* Promotion / Demotion
* Challenge
* Drift
* Budget

## Stage 4 —— Attribution

* Explicit Attribution
* Assisted Attribution
* Experimental Attribution

## Stage 5 —— Safety

* Poisoning Detection
* Quarantine
* Rollback
* Recovery

## Stage 6 —— POC Validation

* End-to-End Scenario
* Adversarial Test
* Controlled Cognitive Experiment

---

# 25. V2.3 冻结什么

V2.3 冻结的是：

> **Semantic Contracts**

而不是所有实现参数。

必须冻结：

1. Cognitive Asset Semantic Model
2. Episode Minimum Schema
3. State Machine Semantics
4. Event Envelope
5. Runtime Request / Response Semantics
6. Policy Decision Semantics
7. Attribution Semantics
8. Evidence Sufficiency Framework
9. Drift Score Framework
10. Rollback Semantics
11. POC Acceptance Criteria
12. Boundary Expression Semantic Subset
13. Evidence Quality / Independence Semantics
14. Retrieval Pipeline Semantics
15. Degradation Action Semantics
16. Control-plane Task / Idempotency Semantics
17. Tenant Authorization / Isolation Semantics
18. Observability Metric Definitions

而以下保持可配置：

* Database Technology
* LLM Provider
* Vector Index
* ES Domain Weights
* Policy Thresholds
* Budget Allocation
* Deployment Topology
* UI
* Retrieval Weights
* Similarity Threshold
* Promotion Threshold
* Performance Envelope
* Scheduler Worker 数量
* Queue Topology

因此：

> **冻结的是语义，不是实现。**



---

# 26. 最终原则

V2.2 回答的是：

> **What should CCI be?**
> CCI 应该是什么？

V2.3 回答的是：

> **How exactly does CCI run?**
> CCI 究竟如何运行？

完整实现链：

```text
Cognitive Intent
      ↓
API Contract
      ↓
Cognitive Asset
      ↓
Event
      ↓
State Machine
      ↓
Evidence / Policy
      ↓
Cognitive Runtime
      ↓
Decision
      ↓
Outcome
      ↓
Attribution
      ↓
Challenge / Drift
      ↓
Promotion / Demotion / Split / Rollback
      ↓
New Runtime State
```

因此：

> **V2.2 定义架构。**

> **V2.3 定义可执行契约。**

> **POC 证明契约真正有效。**

最终工程原则：

> **如果一个 CCI 机制无法被表达为 API Contract、Data Structure、State Transition、Event、Policy Rule、Observable Metric 或 Executable Test，那么它还没有达到 Implementation-Ready。**

V2.3 最终冻结的是：

> **Semantics，而不是所有 Implementation Parameters。**

不同实现可以采用不同的：

* Storage
* Model
* Index
* Deployment

但必须保持：

> **等价的安全性、治理能力以及认知生命周期行为。** 

### 这一版的定位

经过本轮修订，CCI 的版本演进可以非常清晰地收敛为：

```text
CCI V2.0
    │
    │  定义认知基础设施
    ▼
CCI V2.1
    │
    │  解决“如何验证、如何证明价值”
    ▼
CCI V2.2
    │
    │  收敛为正式 Reference Architecture
    ▼
CCI V2.3
    │
    │  将架构转化为 Executable Technical Contract
    ▼
POC
    │
    │  验证契约是否真正成立
    ▼
V3.0
    │
    └── Production / Enterprise Cognitive Runtime
```

因此，**V2.3 不应该继续扩张成“完整生产系统设计”**。从架构演进控制的角度，当前版本已经比较适合冻结技术语义，下一阶段应该进入**代码实现、POC、真实场景验证和性能/安全测试**，而不是继续添加新的顶层概念。
