# CCI V2.3 工程落地实施计划（刷新版）

## —— From Technical Contract to Reproducible Cognitive Runtime

---

# 一、版本目标

CCI V2.3 已经完成：

> **Reference Architecture → Technical Contract**

下一阶段的目标是完成：

> **Technical Contract → Reference Implementation → Reproducible Validation**

因此，本阶段不再扩展新的顶层架构概念，而是围绕：

```text
Contract
   ↓
Event
   ↓
State
   ↓
Policy
   ↓
Runtime
   ↓
Replay
   ↓
Experiment
```

建立一套真正可以：

* 实现
* 运行
* 回放
* 测试
* 审计
* 纠错
* 验证

的 CCI Runtime。

---

# 二、核心工程原则

综合多轮评审，最终冻结以下五条工程不变量。

## 1. Event Store 是唯一事实源

> **Event Store = Source of Truth**

CognitiveState、Search Index、Analytics 等均属于：

> **可重建的派生状态。**

---

## 2. 状态转换必须满足版本一致性

任何状态变化都必须经过：

```text
Command
→ Version Check
→ Guard
→ Event
→ Projection
```

禁止直接修改当前状态。

---

## 3. Rollback 永远产生新版本

例如：

```text
V6
 ↓
V7
 ↓
Rollback
 ↓
V8
```

V6、V7 均永久保留。

V8 表示：

> 当前状态重新采用 V6 的语义，但它本身是一个新的历史版本。

---

## 4. 验证任务必须在授权 Budget 内运行

任何：

* Validation
* Challenge
* Simulation
* Attribution

都必须：

```text
Reserve
→ Execute
→ Settle
```

不得无预算执行。

---

## 5. Golden Replay 必须可重复

相同：

* Dataset
* Context
* Model
* Boundary
* Policy
* Runtime Version

在 Replay Mode 下必须得到：

> **一致的 State / Policy / Boundary / Decision Class。**

LLM 等具有随机性的结果允许存在定义好的容差，但确定性控制链必须一致。

---

# 三、总体路线

```text id="0ldk1w"
                     CCI V2.3
                        │
                        ▼
        ┌────────────────────────────┐
        │ Phase 0                    │
        │ Contract & Version Freeze  │
        └──────────────┬─────────────┘
                       ▼
        ┌────────────────────────────┐
        │ Phase 1                    │
        │ Data + Event Foundation    │
        └──────────────┬─────────────┘
                       ▼
        ┌────────────────────────────┐
        │ Phase 2                    │
        │ FSM + Consistency          │
        └──────────────┬─────────────┘
                       ▼
        ┌────────────────────────────┐
        │ Phase 3                    │
        │ Runtime + Policy MVP       │
        └──────────────┬─────────────┘
                       ▼
        ┌────────────────────────────┐
        │ Phase 4                    │
        │ Control Plane + Budget     │
        └──────────────┬─────────────┘
                       ▼
        ┌────────────────────────────┐
        │ Phase 5                    │
        │ Attribution + Security     │
        └──────────────┬─────────────┘
                       ▼
        ┌────────────────────────────┐
        │ Phase 6                    │
        │ Golden Dataset + Replay    │
        └──────────────┬─────────────┘
                       ▼
        ┌────────────────────────────┐
        │ Phase 7                    │
        │ Adversarial Validation     │
        └──────────────┬─────────────┘
                       ▼
        ┌────────────────────────────┐
        │ Phase 8                    │
        │ Controlled Experiment      │
        └────────────────────────────┘
```

其中：

> **Phase 0–3 是 P0 主链。**

> **Phase 4–6 是 P1 核心能力。**

> **Phase 7–8 是 P2 价值与鲁棒性验证。**

但 Golden Dataset 与实验设计会在早期就同步启动，不能等系统做完再开始。

---

# 四、Phase 0：Contract & Version Freeze

## P0

这是整个实施周期的第一道闸门。

### 0.1 冻结核心契约

冻结：

* API Contract
* Cognitive Data Model
* Event Model
* FSM
* Policy Model
* Attribution Model
* Boundary Model
* Tenant Identity Model
* Audit Model

---

## 0.2 Versioning Policy

建立统一：

```text
Major → Breaking Change
Minor → Backward Compatible Extension
Patch → Bug Fix / Clarification
```

分别适用于：

* API Schema
* Data Schema
* Event Schema
* Policy
* Boundary
* FSM

---

## 0.3 Version Anchor

每个重要 Decision Snapshot 必须绑定：

```text
Decision Snapshot
│
├── Cognitive Model Version
├── Boundary Version
├── Policy Version
├── Evidence Set Version
├── Runtime Version
└── Environment Snapshot
```

形成：

> **Decision Version Anchor**

它是未来 Replay、Audit、Attribution 和 Rollback 的基础。

### Phase 0 完成标准

必须能够回答：

> **2026-08-01 14:32 发生的一次决策，当时究竟使用了什么认知、什么 Boundary、什么 Policy？**

如果无法准确回答，则 Phase 0 不通过。

---

# 五、Phase 1：Data + Event Foundation

## P0

## 1.1 Event Store

明确：

> Event Store = 唯一事实源。

推荐 MVP：

```text
PostgreSQL
    ↓
Append-only Event Table
```

事件至少包含：

```text
event_id
event_type
aggregate_id
aggregate_version
actor
tenant_id
correlation_id
causation_id
schema_version
payload_hash
occurred_at
payload
```

---

## 1.2 Projection

建立：

```text
Event Store
    ↓
Projection Worker
    ↓
CognitiveState
```

原则：

> Projection 可删除、可重建、可重放。

---

## 1.3 Projection Failure

定义：

```text
Success
  ↓
Commit Projection

Failure
  ↓
Retry
  ↓
Exponential Backoff
  ↓
Max Retry
  ↓
Dead Letter Queue
  ↓
Manual Remediation
```

必须支持：

* Idempotency
* Checkpoint
* Replay
* DLQ
* Rebuild

---

## 1.4 Snapshot

当 Aggregate Event 数量达到阈值时：

```text
Events
  ↓
Snapshot
  ↓
Continue Events
```

Snapshot 必须：

* 带 Version
* 带 Hash
* 可验证
* 可丢弃后重新生成

因此：

> Snapshot 是性能优化，不是 Source of Truth。

---

# 六、Phase 2：FSM + State Consistency

## P0

## 2.1 正式状态

```text
DRAFT
QUARANTINED
VALIDATING
VALIDATED
ACTIVE
DEGRADED
SUSPENDED
ARCHIVED
```

回滚过渡状态：

```text
ROLLBACK_PENDING
ROLLBACK_EXECUTING
```

---

## 2.2 Transition Contract

每个 Transition 定义：

```text
Trigger
Precondition
Version Guard
Policy Guard
Action
Success Event
Failure Strategy
Compensation
```

---

## 2.3 并发控制

采用：

> **Optimistic Concurrency Control**

例如：

```text
expected_version = 7
```

只有：

```text
current_version == 7
```

才能修改。

否则：

```text
VERSION_CONFLICT
```

进入：

```text
Retry
Re-evaluate
Reject
Manual Review
```

高优先级命令可以：

> **抢占调度优先级**

但不能：

> **绕过 FSM invariant。**

---

## 2.4 Rollback 版本规则

明确：

```text
V6
↓
V7
↓
Rollback
↓
V8
```

V8：

```text
source_version = V6
rollback_from = V7
rollback_reason = ...
```

历史 V6/V7 均保持不变。

---

# 七、Phase 3：Runtime + Policy MVP

## P0

这是第一阶段真正可以“跑起来”的部分。

## 3.1 Runtime

```text
Request
 ↓
Identity
 ↓
Context Snapshot
 ↓
Recall
 ↓
Filter
 ↓
Evidence
 ↓
Boundary
 ↓
Drift
 ↓
Risk
 ↓
Policy
 ↓
Delivery
 ↓
Outcome
 ↓
Attribution
```

---

## 3.2 Retrieval

采用：

```text
Recall
 ↓
Deterministic Filter
 ↓
Re-rank
 ↓
Policy
```

明确：

> Retrieval Score ≠ Authorization

---

## 3.3 Boundary

V2.3 Reference Implementation 默认使用：

> **CEL**

但核心契约冻结的是：

* 表达式语义
* 可用变量
* 操作符
* Evaluation Result
* Sandbox
* Complexity Limit

而不是将 CEL 本身永久冻结。

---

## 3.4 Policy

定义：

```text
ALLOW
ALLOW_WITH_WARNING
ALLOW_WITH_EXPLANATION
DEGRADE
REQUIRE_HUMAN_REVIEW
BLOCK
```

DEGRADE 进一步划分：

```text
D1 Confidence Reduction
D2 Scope Reduction
D3 Evidence-only
D4 Challenge-first
D5 Human Review
```

---

## 3.5 Runtime Latency Budget

V2.4 MVP：

> **Evaluate → Policy → Delivery P99 ≤ 50ms**

同时建立预算：

```text
Context
Recall
Evidence
Boundary
Drift
Risk
Policy
Delivery
```

分别计入 Latency Budget。

50ms 是：

> **MVP Engineering Target**

不是永久生产 SLA。

---

# 八、Phase 4：Control Plane + Scheduler + Budget

## P1

## 4.1 Task Model

任务类型：

```text
Validation
Challenge
Drift Detection
Promotion
Demotion
Conflict Detection
Attribution Verification
Rollback
```

---

## 4.2 Scheduler

采用：

```text
Priority Queue
+
Budget-aware Scheduling
+
Retry
+
Deadline
+
Idempotency
+
DLQ
```

---

## 4.3 Priority

```text
P0 Security / Rollback
P1 High Risk / Policy Expiry
P2 Normal Evolution
P3 Background
```

---

# 九、Phase 5：Verification Budget

## P1

验证预算正式引入：

> **Validation Credit（VC）**

作为统一计价单位。

任务成本可综合：

```text
LLM Token
Compute
External Service
Human Review
Simulation
```

折算成：

> Validation Credit

---

## 5.1 Budget Lifecycle

```text
Reserve
   ↓
Execute
   ↓
Settle
   ↓
Consume / Refund
```

支持：

* Period Budget
* Domain Budget
* Asset Budget
* Task Budget
* Emergency Reserve
* Carry-over
* Exhaustion
* Priority Reservation

核心不变量：

> **任务不得消耗超过已授权预算。**

---

# 十、Phase 6：Attribution + Security

## P1

## 6.1 Attribution

三级模型：

```text
L1 Explicit
L2 AI-assisted
L3 Experimental
```

---

## 6.2 Attribution Anti-Gaming

检测：

* 异常集中归因
* 短时间大量高价值归因
* 互相归因
* 归因与 Outcome 严重不一致

触发：

```text
Detect
 ↓
Review
 ↓
Verify
 ↓
Accept / Reject
 ↓
Credit Correction
```

S/A 级认知的高价值 Attribution：

> 应尽可能有独立 Outcome Evidence 支撑。

---

## 6.3 Cognitive Poisoning

```text
Detect
 ↓
Quarantine
 ↓
Investigate
 ↓
Rollback
 ↓
Freeze Attribution/Credit
 ↓
Revalidate
```

---

# 十一、Phase 7：Golden Dataset + Replay

## P0/P1 并行建设

这一阶段虽然排在 Runtime 后面，但**Dataset 和 Ground Truth 的准备应从 Phase 0 就开始**。

---

## 7.1 Golden Dataset v1.0

至少：

> **100 个真实/半真实 Case**

覆盖：

* 正常
* 异常
* Boundary
* Conflict
* Drift
* Poisoning
* Rollback
* Policy Failure

---

## 7.2 Ground Truth

每个 Case 包含：

```text
Input
Context
Expected Evidence
Expected Boundary
Expected Policy
Expected State
Expected Decision
Expected Outcome
```

---

## 7.3 Ground Truth Governance

流程：

```text
Annotation
 ↓
Expert Review
 ↓
Adjudication
 ↓
Freeze
 ↓
Version
```

Ground Truth 不能由实施代码自己生成。

---

## 7.4 Replay Determinism

Replay 固定：

* Dataset
* Model Version
* Boundary Version
* Policy Version
* Runtime Version
* Context Snapshot
* External Dependency
* Time Anchor

然后：

```text
Replay
 ↓
Actual
 ↓
Expected
 ↓
Diff
 ↓
PASS / FAIL
```

确定性要求：

### 必须 Exact

* State Transition
* Boundary Evaluation
* Policy Decision
* Event Sequence

### 允许容差

* LLM Semantic Output
* Natural Language Explanation

---

# 十二、Phase 8：Golden Path 量化验收

## P0

Golden Path：

> AI 推理服务 P99 延迟异常

完整：

```text
T0 Decision Snapshot
T1 Episode
T2 Evidence
T3 Pattern
T4 Model
T5 Runtime
T6 Attribution
T7 Drift
T8 Policy
T9 Rollback / Evolution
T10 Replay
```

每个节点必须定义：

```text
Input
Expected State
Expected Event
Metric
Threshold
Pass / Fail
```

例如：

| 节点  | 核心验收                     |
| --- | ------------------------ |
| T0  | Snapshot 100% 不可变        |
| T2  | Evidence 可追溯             |
| T4  | ES + Guard 满足晋升          |
| T5  | Runtime P99 达标           |
| T6  | Attribution 可解释          |
| T7  | Drift 正确触发               |
| T8  | Policy Decision 正确       |
| T9  | Rollback 保留历史            |
| T10 | Replay 与 Ground Truth 一致 |

---

# 十三、Phase 9：Adversarial Test

## P2

覆盖：

### Cognitive Poisoning

### Attribution Gaming

### Boundary Bypass

### Policy Bypass

### Event Replay

### Duplicate Command

### State Race

### Evidence Manipulation

### Tenant Isolation

### Rollback Abuse

---

# 十四、Phase 10：Controlled Cognitive Experiment

## P2，但实验设计从 P0 启动

不等系统做完才设计实验。

Phase 0 即冻结：

## 三组基线

### Group A

> Human Only

### Group B

> Traditional RAG / Knowledge Base

### Group C

> CCI-assisted

---

## 指标体系

### Decision Quality

* Accuracy
* Expert Blind Score
* Error Rate

### Decision Efficiency

* Time to Decision
* MTTR
* Investigation Time

### Cognitive Reuse

* Reuse Rate
* Repeated Investigation
* Boundary Match

### Safety

* Unsafe Recommendation
* Boundary Violation
* Policy Violation

### Cost

* Runtime Cost
* Verification Cost
* Human Review Cost

---

## 统计方法

不预设单一 t-test。

根据数据选择：

* paired t-test
* Wilcoxon
* bootstrap
* confidence interval
* effect size

最终同时判断：

> **Statistical Significance + Effect Size + Business Significance**

---

# 十五、Phase 11：审计与多租户

## P1/P2

即使完整多租户能力是 P2：

> **tenant_id / domain_id / trust_domain 必须在 P0 数据模型中预留。**

---

## Audit

统一：

```text
Actor
Tenant
Action
Target
Before
After
Reason
Correlation ID
Policy Version
Timestamp
```

---

## Tenant

默认：

> **Deny by Default**

明确：

* Identity
* Authorization
* Tenant Boundary
* Cross-domain Grant
* Expiration
* Revocation

---

# 十六、Reference Implementation 技术基线

为了避免工程团队陷入无休止选型，V2.4 提供默认实现：

```text
API
  FastAPI

Language
  Python

System of Record
  PostgreSQL

Vector
  pgvector

Event Store
  PostgreSQL Append-only Table

Cache
  Redis

Scheduler
  Celery / Temporal Reference Profile

Policy
  CEL / OPA

Observability
  OpenTelemetry
Prometheus
Grafana

Container
  Docker

Test
  Pytest
```

这里必须明确：

> **Reference Stack ≠ Frozen Architecture**

任何组件都可以替换，只要通过：

> **CCI Conformance Test**

即可。

---

# 十七、最终 P0 / P1 / P2 优先级

## P0 —— 不完成就不能进入正式 POC

```text
1. API Contract
2. Data Model
3. Version Anchor
4. Versioning Policy
5. Event Store
6. Projection
7. Projection Failure / DLQ
8. FSM
9. FSM Failure / Compensation
10. Concurrency Control
11. Boundary / Policy
12. Runtime MVP
13. Policy Engine
14. Runtime Latency Budget
15. Golden Dataset
16. Ground Truth Governance
17. Golden Path Acceptance Matrix
```

---

## P1 —— 核心能力完善

```text
18. Control Plane Scheduler
19. Verification Credit
20. Attribution
21. Attribution Anti-Gaming
22. Cognitive Poisoning Defense
23. Audit Model
24. Replay Framework
25. Observability
26. Tenant Isolation Contract
```

---

## P2 —— 价值和规模验证

```text
27. Adversarial Testing
28. Human vs RAG vs CCI Experiment
29. Statistical Validation
30. Performance Benchmark
31. Multi-tenant Runtime
32. Distributed Event Store
33. Advanced Attribution
34. Advanced Conflict Resolution
```

---

# 十八、最终交付物

最终不以“文档完成”作为交付，而以以下工程资产作为完成标志：

```text
CCI V2.3 Reference Implementation
│
├── API Contract
├── Data Model
├── Version Anchor
├── Event Model
├── Projection Engine
├── FSM
├── Policy Engine
├── Runtime MVP
├── Control Plane
├── Verification Budget
├── Attribution
├── Security / Rollback
├── Audit
├── Golden Dataset v1.0
├── Replay Engine
├── Conformance Test
├── Golden Path
├── Adversarial Test Suite
└── Controlled Experiment Report
```

---

# 十九、最终验收标准

这一阶段真正完成，不是因为：

> “代码写出来了。”

而是必须同时证明：

### 1. 历史可追溯

> 任意重大决策可以还原当时的 Model、Boundary、Policy、Evidence。

### 2. 状态可重建

> 删除 Projection 后，可以从 Event Store 重建相同状态。

### 3. 决策可回放

> Golden Dataset 能够重复得到一致的控制链结果。

### 4. 策略可复现

> 同一 Version Anchor + Context 下，Policy Decision 一致。

### 5. 错误可恢复

> 错误认知能够 Quarantine、Rollback、Revalidate。

### 6. 资源受约束

> Challenge / Validation 不得突破 Budget。

### 7. 价值可验证

> CCI 与 Human / RAG Baseline 的决策差异能够通过受控实验进行测量。

---

# 二十、下一步最重要的工作顺序

综合所有专家意见后，我建议团队实际启动时按以下顺序执行：

```text
① 冻结 Contract + Versioning
          ↓
② 冻结 Data Model + Version Anchor
          ↓
③ 冻结 Event + Projection + FSM
          ↓
④ 建立 Golden Dataset + Ground Truth
          ↓
⑤ 开发 Runtime + Policy
          ↓
⑥ 开发 Control Plane + Budget
          ↓
⑦ 开发 Attribution + Security
          ↓
⑧ 建立 Replay + Conformance Test
          ↓
⑨ Adversarial Test
          ↓
⑩ Human / RAG / CCI Controlled Experiment
```

其中有一个很重要的调整：

> **Golden Dataset、实验基线、Version Anchor 不应该等系统开发完成以后再做，而应该与 Contract Freeze 并行启动。**

这样可以避免最常见的工程陷阱：

> **系统开发了几个月，最后才发现“到底应该证明什么”还没有定义。**

---

## 最终版本定位

经过这几轮专家评审，现在 CCI 的演进已经可以非常清晰地收敛：

```text
V1.0
定义 CCI
        ↓
V2.0
设计 CCI
        ↓
V2.1
验证认知
        ↓
V2.2
冻结参考架构
        ↓
V2.3
冻结技术契约
        ↓
V2.4
Reference Implementation
        ↓
V2.5
Empirical Validation
        ↓
V3.0
Enterprise Cognitive Runtime
```

因此，**现在最重要的已经不是继续写架构，而是开始构建和验证。**

下一阶段真正需要拿出来的，不应该再是一份几十页的概念文档，而应该是：

> **一个能运行的 Runtime、一个能回放的 Event Store、一个可重复的 Golden Dataset、一套自动化 Conformance Test，以及一组能够证明 CCI 价值的实验数据。**

这将是 CCI 从“架构思想”真正跨入“技术体系”的关键一步。
