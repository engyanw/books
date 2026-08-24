
# Capability Operating System 技术白皮书 V1.0

## ——资源池化、能力原子化、动态能力地图与自进化运行时

---

# 摘要

传统软件平台以“应用、服务、产品”为基本组织单元。资源被绑定在应用或产品之下，能力被固化在服务代码之中，业务流程被预先编排，系统运行时主要负责执行已经确定的程序。

AI、Agent、Serverless、云原生以及动态业务环境的发展，使这种模式逐渐暴露出新的局限：

* 能力重复建设严重，难以跨业务复用；
* 能力与资源、Runtime 高度耦合；
* 新能力开发、验证、上线周期长；
* 动态业务需求难以实时映射到能力和资源；
* 新能力上线存在较大的生产风险；
* 服务弹性主要围绕 Container、Pod、VM 等资源载体，而非业务能力；
* 发布、监控、故障、成本、性能和安全往往相互割裂；
* 系统运行经验无法沉淀为下一次能力选择的依据。

本白皮书提出一种新的平台架构范式：

> **Capability Operating System（Capability OS）**

其核心思想是：

> **资源池化，让资源成为平台级公共生产资料；能力原子化，让能力成为平台级可组合生产单元；Graph 描述能力关系，Map 将 Graph 封装为可运行能力边界；Runtime 根据需求按需实例化能力；Control Plane 持续观测、评估并调整运行；Capability Experience 反哺后续能力选择；当现有能力无法满足需求时，由 Code Agent 自动生成、测试、验收新的 Capability。**

整个系统形成如下闭环：

```text
Business Intent
      ↓
Intent Understanding
      ↓
Capability Requirement
      ↓
Capability Discovery
      ↓
Capability Generation（必要时）
      ↓
Capability Validation
      ↓
Graph Planning
      ↓
Map Definition
      ↓
Map Runtime
      ↓
Lazy Expansion
      ↓
Capability Instantiation
      ↓
Elastic Execution
      ↓
Telemetry / Trace / Log
      ↓
DFX Assessment
      ↓
Control / Adaptation
      ↓
Capability Experience
      ↓
Capability Pool
      ↺
```

最终形成：

> **Intent → Capability → Graph → Map → Runtime → Resource → Outcome → Experience → Capability**

其目标不是简单地构建一个更好的微服务平台，而是建立一种新的数字生产方式：

> **从“部署产品”走向“按业务意图动态生产结果”。**

---

# 1. 背景与问题

## 1.1 传统软件平台的基本模式

传统平台基本遵循：

```text
Business
   ↓
Application
   ↓
Service
   ↓
Runtime
   ↓
Resource
```

例如一个安全平台可能包含：

```text
DDoS Product
 ├── Detection
 ├── Cleaning
 ├── Rate Limit
 └── Blocking
```

WAF 又拥有：

```text
WAF
 ├── Inspection
 ├── Detection
 ├── Blocking
 └── Challenge
```

大量能力存在重复。

---

## 1.2 资源层面的烟囱

传统模式下：

```text
Product A → CPU/GPU/Memory
Product B → CPU/GPU/Memory
Product C → CPU/GPU/Memory
```

资源被产品边界锁定。

问题包括：

* 利用率低；
* 容量无法全局调度；
* 资源无法跨产品复用；
* 成本无法精细归因。

---

## 1.3 能力层面的烟囱

传统方式：

```text
DDoS Detection
WAF Detection
Bot Detection
AI Detection
```

即使内部算法高度相似，也往往以不同产品形式存在。

因此需要将：

> **功能从产品中解耦。**

---

# 2. 核心架构原则

Capability OS 建立七条核心原则。

## 原则一：资源池化

任何可被统一分配、计量、隔离、调度和回收的有限资源，都应进入资源管理体系。

包括：

* CPU；
* CPU Time Slice；
* GPU；
* HBM；
* Memory；
* Disk；
* IOPS；
* Network Bandwidth；
* Connection；
* Queue；
* KV Cache；
* Runtime Capacity。

资源不是产品私有资产，而是平台公共生产资料。

---

## 原则二：能力原子化

Capability 是：

> **独立可实例化、独立可执行、可复用、可组合的最小能力生产单元。**

每个 Capability 不依赖其他 Capability 才能成立。

---

## 原则三：能力与资源解耦

Capability 描述：

> “能做什么、需要什么、产生什么、有哪些约束。”

Resource 描述：

> “运行这个能力时消耗什么生产资料。”

Capability 不拥有 Resource。

---

## 原则四：Graph 与 Capability 分离

Capability 是能力本体。

Graph 是 Capability 之间的关系。

> **Capability 是节点语义，Graph 是组织结构。**

---

## 原则五：Map 是唯一外部能力边界

外部请求不能直接调用 Capability。

外部只能：

```text
External
   ↓
Map
   ↓
Graph
   ↓
Capability
```

因此 Map 是：

> **External Invocation Boundary**

---

## 原则六：运行时按需展开

Capability 默认不运行、不占用运行资源。

只有在 Map 的一次运行过程中，被真正需求触达并满足入口条件时，才进行实例化。

> **Capability 是 Dormant-by-Default。**

---

## 原则七：所有运行行为都进入闭环控制

Runtime 必须持续产生：

* Metrics；
* Logs；
* Trace；
* State；
* Security Signals；
* Resource Signals；
* Business Signals。

管控面根据这些证据进行 DFX、状态、安全、容量和风险评估，并反向调整 Runtime。

形成：

> **Observe → Assess → Decide → Control → Observe**

---

# 3. 核心对象模型

Capability OS 最重要的是划清对象边界。

---

## 3.1 Resource

Resource 是：

> 能够被分配、占用、计量、限制和释放的有限生产资料。

### 资源分类

```text
Physical Resource
├── CPU
├── GPU
├── Memory
├── HBM
├── Disk
└── NIC

Virtual Resource
├── vCPU
├── vMemory
├── vDisk
└── vNIC

Runtime Resource
├── Thread
├── Connection
├── Queue
├── File Descriptor
└── Concurrency

AI Runtime Resource
├── GPU Compute
├── HBM
├── KV Cache
├── Prefill Budget
├── Decode Budget
└── Context Capacity
```

---

# 4. Capability 定义

Capability 是平台最核心的对象。

推荐采用以下模型：

```text
Capability
├── Identity
├── Intent
├── Input Contract
├── Output Contract
├── Preconditions
├── Postconditions
├── Resource Contract
├── State Contract
├── Policy Contract
├── Security Contract
├── Cost Model
├── SLA / QoS
├── Side Effects
├── Observability
├── Version
└── Lifecycle
```

---

## 4.1 Capability 的核心特征

### 独立执行

Capability 必须能够脱离其他 Capability 独立执行。

### 自描述

Decision Engine 能够理解：

* 能做什么；
* 输入是什么；
* 输出是什么；
* 需要什么资源；
* 有什么限制；
* 成本如何。

### 可度量

Capability 必须能够度量：

* 延迟；
* 吞吐；
* 成功率；
* 资源消耗；
* 成本；
* 风险。

### 可组合

Capability 可以被 Graph 引用。

### 可实例化

Capability 本身是静态定义，运行时才能形成 Instance。

---

# 5. Capability、Runtime 与 Interface

三个概念必须严格分离。

```text
Capability
    │
    ├── Interface
    │      ├── API
    │      ├── RPC
    │      ├── Event
    │      └── Message
    │
    └── Runtime
           ├── Thread
           ├── Process
           ├── Container
           ├── VM
           ├── Serverless Function
           └── Remote Runtime
```

因此：

* API 是调用接口；
* Thread / Process / Container / VM / Serverless 是 Runtime；
* Capability 是能力定义。

---

# 6. Composite Capability 的重新定义

Composite Capability 不是多个能力的静态打包。

正确模型是：

> **Composite Capability 是在一次运行过程中，根据 Relationship Graph 动态解析并实例化多个独立 Capability 所形成的运行态复合能力。**

因此：

```text
Capability A
Capability B
Capability C
```

始终各自独立存在。

运行时：

```text
Composite Request
       ↓
Relationship Graph
       ↓
A + B + C
```

形成一次动态组合。

因此：

> **Composition 是 Runtime 行为，而不是 Capability Definition 本身。**

---

# 7. Graph 模型

Graph 定义 Capability 之间的关系。

例如：

```text
A
├── requires B
├── optional C
├── parallel D
├── condition E
├── fallback F
└── aggregate G
```

Graph 可以支持：

* Dependency；
* Sequence；
* Parallel；
* Condition；
* Branch；
* Join；
* Fallback；
* Retry；
* Compensation；
* Aggregation。

---

# 8. Graph 与 Map 的关系

这是整个体系最容易混淆、也是最关键的部分。

## Graph

回答：

> **Capability 如何连接？**

Graph 是关系结构。

---

## Map

回答：

> **这组 Capability 如何作为一个统一能力对外提供和运行？**

因此：

> **Graph 是 Map 的结构内核；Map 是 Graph 的可运行能力边界。**

可表示为：

```text
Map
├── External Interface
├── Entry Contract
├── Capability Relationship Graph
├── Expansion Policy
├── Resource Policy
├── Routing Policy
├── Scaling Policy
├── Security Policy
├── Lifecycle Policy
└── DFX Contract
```

因此：

> **Map = Graph + Runtime Semantics**

---

# 9. Graph 与 Map 的运行时模型

需要区分：

```text
Graph Definition
Map Definition
Map Instance
Capability Instance
```

生命周期：

```text
Graph Definition
      ↓
Map Definition
      ↓
Map Instance
      ↓
Graph Expansion
      ↓
Capability Instance
```

---

# 10. Map-only Invocation

外部请求：

```text
External Request
      ↓
Map Endpoint
      ↓
Map Runtime
      ↓
Graph
      ↓
Capability
```

禁止：

```text
External
 ├── Capability A
 ├── Capability B
 └── Capability C
```

这样能够将：

* 权限；
* Session；
* 灰度；
* Graph；
* LB；
* Scaling；
* DFX；
* Fault Isolation

统一纳入 Map Runtime 管理。

---

# 11. Lazy Graph Expansion

Graph 完整定义可以事先存在，但 Map 不会一次性实例化整张图。

例如：

```text
Root
├── A
│   ├── D
│   └── E
└── B
    └── F
```

第一次请求：

```text
Root
└── A1
```

后续产生需求：

```text
Root
├── A1
│   ├── D1
│   └── E1
└── B1
```

因此：

> **Graph Definition 完整存在，Runtime Graph Instance 按需求逐步展开。**

---

# 12. Capability Instance 生命周期

能力实例默认不存在。

完整生命周期：

```text
DORMANT
   ↓
PROVISIONING
   ↓
WARM
   ↓
RUNNING
   ↓
IDLE
   ↓
DRAINING
   ↓
TERMINATING
   ↓
DORMANT
```

由 Demand 驱动状态转换。

---

# 13. External Capability Call

Graph 中节点之间存在两类调用：

## Local Call

多个 Capability 在同一个 Runtime / Resource Bundle 中运行。

## External Call

Capability A 调用 Capability B 的 Runtime Pool。

外部调用必须具备：

* Downstream Load Awareness；
* Capacity Awareness；
* Load Balancing；
* Elasticity；
* Health；
* Fault Isolation。

---

# 14. Capacity Contract

下游 Capability 必须暴露 Capacity，而不是只有 Health。

例如：

```text
Capability B
├── Current Load
├── Available Capacity
├── Queue Depth
├── Concurrency
├── Latency
├── Error Rate
├── CPU Pressure
├── Memory Pressure
├── GPU Pressure
└── Scale State
```

于是上游实现：

> **Capacity-aware Routing**

而不是简单 Round Robin。

---

# 15. Elastic Capability Runtime

Capability 本身静态，Instance 动态。

```text
Capability B
   ↓
Runtime Pool
   ↓
B1
B2
B3
B4
```

负载增加：

```text
B1
 ↓
Scale Out
 ↓
B1 B2 B3 B4
```

负载下降：

```text
B1 B2 B3 B4
 ↓
Drain
 ↓
B1 B2
```

因此：

> **能力静态，运行态弹性。**

---

# 16. Demand Propagation

上游需求应该逐层向下游传播：

```text
Root Demand
    ↓
A Demand
    ↓
B Demand
    ↓
C Demand
```

如果 Graph 存在分流：

```text
A
├── B 70%
└── C 30%
```

则：

```text
Root = 10,000 QPS

B = 7,000 QPS
C = 3,000 QPS
```

形成：

> **Demand Down / Capacity Up**

双向控制。

---

# 17. Graph Runtime Capacity

整张 Map 的能力上限不是各节点能力简单相加，而受到瓶颈限制。

对于串行路径：

```text
Graph Capacity
≈ min(
    Node Capacity,
    Edge Capacity,
    Resource Capacity
)
```

因此需要 Graph-aware Scheduling。

---

# 18. Graph 的动态演进

Graph 会随着业务的发展不断变化：

```text
Graph v1
A → B → C

Graph v2
A → B → D

Graph v3
A → E → D
```

因此 Graph 必须：

* Versioned；
* Validated；
* Published；
* Canary；
* Activated；
* Draining；
* Retired。

---

# 19. Graph Generation

Graph Version 与 Runtime Generation 必须区分。

例如：

```text
Graph v12
Generation 107
```

新版本：

```text
Graph v13
Generation 108
```

新 Session 使用：

```text
G108
```

存量 Session 继续：

```text
G107
```

直到自然结束。

---

# 20. Session-aware Gray Release

灰度的基本单位不能只是 Request。

应以 Session 为核心：

```text
Session
   ↓
Session Assignment
   ↓
Graph Generation
```

一旦：

```text
Session S1 → G107
```

则：

```text
Request 1 → G107
Request 2 → G107
Request 3 → G107
```

在正常生命周期内不发生漂移。

---

# 21. 灰度策略模型

灰度支持：

### User

* User；
* Tenant；
* Customer Segment。

### Geography

* Country；
* Region；
* City；
* IDC；
* AZ；
* PoP。

### Device

* Mobile；
* Desktop；
* Tablet；
* OS；
* Device Model。

### Network

* IP；
* ASN；
* ISP；
* IPv4/IPv6。

### Time

* Time of Day；
* Weekday；
* Business Window。

### Business

* Product；
* API；
* Service；
* Traffic Class。

形成：

> **Multi-dimensional Rollout Policy**

---

# 22. 灰度生命周期

```text
Prepare
  ↓
Validate
  ↓
Sandbox
  ↓
Shadow
  ↓
Canary
  ↓
Progressive Expansion
  ↓
100%
  ↓
Old Generation Drain
  ↓
Retire
```

---

# 23. 故障自动隔离

隔离层级：

```text
Instance
   ↓
Capability Version
   ↓
Graph Node
   ↓
Sub-Map
   ↓
Graph Generation
   ↓
Map
```

原则：

> **故障发生在哪里，就尽可能隔离在哪里。**

---

# 24. 新能力必须先进入 Sandbox

由 Code Agent 生成的新 Capability，不能直接进入普通生产 Runtime。

强制过程：

```text
Code Agent
 ↓
Build
 ↓
Test
 ↓
Validate
 ↓
Admission
 ↓
Production Sandbox
 ↓
Shadow / Canary
 ↓
DFX Evaluation
 ↓
Promotion
 ↓
Normal Runtime
```

---

# 25. Sandbox 的核心边界

必须控制：

* CPU；
* Memory；
* GPU；
* Network；
* Disk；
* Identity；
* Secret；
* Data Access；
* Concurrency；
* Side Effects。

采用：

> **Least Privilege + Least Data Access + Least Resource + Default Deny**

---

# 26. Sandbox 与 Gray 的区别

Sandbox 回答：

> **“这个能力以什么权限、资源和隔离级别运行？”**

Gray 回答：

> **“哪些 Session 使用这个能力？”**

两者是正交维度。

---

# 27. Capability Trust Model

新能力通过逐步运行获得生产信任。

```text
Trust 0
   ↓
Sandbox
   ↓
Shadow
   ↓
Canary
   ↓
Restricted Production
   ↓
Normal Production
```

Trust 由：

```text
Code Trust
Test Trust
Security Trust
Runtime Trust
DFX Trust
Business Trust
Historical Trust
```

共同构成。

---

# 28. DFX 总体模型

DFX 应覆盖 Capability 的整个生命周期。

本白皮书采用九维参考模型：

```text
Runtime Excellence
├── Performance / Scalability
├── Availability / Resilience
└── Security

Evolution & Lifecycle
├── Extensibility
├── Maintainability / Observability
└── Portability / Compatibility

Engineering & Economics
├── Deployability
├── Testability
└── Cost / FinOps
```

说明：

> 本白皮书将上述维度作为 Capability OS 的工程 DFX Reference Model，而不是宣称这些具体缩写由 ISO/IEC 25010 直接定义。ISO/IEC 25010 提供软件质量模型框架，具体 DFX 维度与命名可根据平台工程实践进行组织。

---

# 29. DFX 的真正作用

DFX 不是 Dashboard 分数。

它应该成为：

> **Decision Input**

例如：

```text
Performance = Poor
Security = Good
Cost = High
Reliability = Good
```

管控面可直接决定：

```text
Scale
Re-route
Isolate
Rollback
Change Graph
Change Capability
```

---

# 30. DFX Fast Loop / Slow Loop

## Fast Loop

负责：

* LB；
* Rate Limit；
* Admission Control；
* Circuit Break；
* Instance Health；
* Resource Protection；
* Security Enforcement。

特点：

> Deterministic / Fast / Local。

---

## Slow Loop

负责：

* 趋势预测；
* 容量预测；
* Graph Optimization；
* Capability Replacement；
* Cost Optimization；
* Rollout Promotion；
* Architecture Evolution。

特点：

> Model-driven / Global / Adaptive。

---

# 31. Runtime Telemetry

Runtime 必须实时向 Control Plane 上报：

### Metrics

```text
Latency
QPS
Concurrency
Queue
Error
Retry
CPU
Memory
GPU
Network
```

### Logs

```text
Execution
Error
Policy
Resource
Scale
Lifecycle
```

### Trace

完整记录：

```text
Map
 → Capability
 → Capability
 → Sub-Map
 → Capability
```

### Security Signals

```text
Anomaly
Policy Violation
Privilege Change
Attack Pattern
```

### Provenance

```text
Tenant
Session
Map
Graph
Capability
Version
Instance
Resource
Outcome
```

---

# 32. State Assessment Engine

Telemetry 是观测，不是真实状态。

Control Plane 需要将：

```text
Metrics
Logs
Trace
Security
History
Topology
```

融合为：

```text
Current State
Trend
Risk
Capacity
Health
Confidence
```

---

# 33. DFX Control Loop

完整过程：

```text
Telemetry
   ↓
State Assessment
   ↓
DFX Evaluation
   ↓
Risk Assessment
   ↓
Policy Decision
   ↓
Action
   ↓
Runtime
```

---

# 34. Control Plane

建议形成九个核心引擎：

```text
1. Intent & Decision Engine
2. Capability Registry / Knowledge Engine
3. Graph Management / Compiler
4. Map Runtime Controller
5. Policy / Security / Governance
6. DFX / State Assessment Engine
7. Rollout / Release Controller
8. Capacity / Elasticity Controller
9. Experience / Learning Engine
```

---

# 35. Operations Plane

Operations Plane 面向：

* SRE；
* Platform Operator；
* Capability Operator；
* Security Operator；
* Business Operator；
* FinOps；
* Release Operator。

主要系统：

```text
O&M
SRE
Incident Management
Problem Management
Release Operations
Security Operations
Capability Operations
FinOps
Capacity Planning
Business Operations
```

---

# 36. 四平面总体架构

最终推荐：

```text
                 Experience Plane
              Business / Operator
                       │
                       ▼
                 Operations Plane
              O&M / SRE / FinOps
                       │
                       ▼
                  Control Plane
       Decision / Policy / DFX / Graph
                       │
                       ▼
                  Runtime Plane
          Map / Graph / Capability Runtime
                       │
                       ▼
                 Resource Plane
        CPU / GPU / Network / Storage / KV
```

---

# 37. Capability Ecosystem

Capability Pool 不能只是代码仓库。

应该保存：

```text
Capability
├── Definition
├── Implementation
├── Contract
├── Version
├── Graph Compatibility
├── Resource Profile
├── DFX Profile
├── Security Profile
├── Historical Performance
├── Reliability
├── Scenario Fitness
├── Adaptability
├── Cost
├── Provenance
├── Trust
└── Experience
```

形成：

> **Capability Knowledge + Implementation + Experience**

统一资产池。

---

# 38. Capability Discovery

Capability Discovery 不应该单纯做向量搜索。

推荐采用：

```text
Intent
 ↓
Semantic Retrieval
 ↓
Capability Graph Retrieval
 ↓
Contract Filtering
 ↓
Resource Filtering
 ↓
Security Filtering
 ↓
DFX Filtering
 ↓
Cost Filtering
 ↓
Fitness Ranking
```

---

# 39. Capability Fitness

对于候选 Capability：

```text
Fitness =
Functional Fit
× Performance Fit
× Security Fit
× Reliability Fit
× Resource Fit
× Cost Fit
× Context Fit
```

Fitness 是场景相关的。

例如：

```text
Capability B
高并发：0.93
低延迟：0.84
海外：0.52
```

意味着：

> 能力没有绝对“好坏”，只有场景适应性。

---

# 40. Capability Generation

当 Capability Pool 无法满足 Capability Requirement 时：

```text
Capability Gap
      ↓
Code Agent
      ↓
Architecture
      ↓
Code
      ↓
Unit Test
      ↓
Integration Test
      ↓
Security Test
      ↓
Performance Test
      ↓
Resource Test
      ↓
Contract Test
      ↓
DFX Test
      ↓
Acceptance
      ↓
Capability Package
```

Code Agent 是：

> **Capability Factory**

而不是直接生产可执行代码后立即上线。

---

# 41. Intent-to-Capability

LLM 的首要职责不是直接调用工具，而是：

> **理解业务意图并转换成 Capability Requirement。**

例如：

```text
Business Intent
├── Objective
├── Scope
├── SLA
├── Security
├── Cost
├── Performance
└── Compliance
```

然后：

```text
Intent
 ↓
Capability Requirement
```

---

# 42. Graph Planning

获取能力后：

```text
Capability Set
 ↓
Graph Planning
 ↓
Candidate Graph
```

LLM/Decision Engine 可以提出候选 Graph。

但生产 Graph 必须经过：

```text
Contract Validation
Dependency Validation
Cycle Check
Security Check
Resource Feasibility
DFX Check
Cost Check
Compatibility Check
```

---

# 43. Map Runtime Acceptance

Graph 形成 Map 后，不应直接全量生产。

应该：

```text
Map
 ↓
Simulation
 ↓
Shadow
 ↓
Canary
 ↓
Functional Acceptance
 ↓
Performance Acceptance
 ↓
Security Acceptance
 ↓
DFX Acceptance
 ↓
Progressive Production
```

---

# 44. Capability Experience

运行产生的数据需要沉淀成：

> **Capability Experience Record**

例如：

```text
Capability B v3
Scenario:
Singapore / Mobile / Peak

Observed:
P99 = 182ms
Error = 0.02%
Cost = 0.71
Security = 0.95
Fitness = 0.93
```

未来选择能力时重新利用。

---

# 45. Capability Adaptability

除了 Fitness，还需要：

> **Adaptability**

即：

> 业务、流量、环境、资源发生变化以后，Capability 能否继续保持效果。

因此能力池可同时记录：

```text
Fitness
Adaptability
Trust
Cost
Reliability
Security
Performance
```

---

# 46. Capability 生命周期

完整生命周期：

```text
DISCOVER
   ↓
GENERATE
   ↓
VALIDATE
   ↓
ADMIT
   ↓
SANDBOX
   ↓
CANARY
   ↓
PROMOTE
   ↓
ACTIVE
   ↓
DEPRECATE
   ↓
DRAIN
   ↓
RETIRE
```

---

# 47. Graph 生命周期

```text
DRAFT
 ↓
VALIDATE
 ↓
PUBLISHED
 ↓
CANARY
 ↓
ACTIVE
 ↓
DRAINING
 ↓
DEPRECATED
 ↓
RETIRED
```

---

# 48. Map 生命周期

Map 作为外部能力边界：

```text
DEFINE
 ↓
VALIDATE
 ↓
READY
 ↓
RUNNING
 ↓
DEGRADED
 ↓
ISOLATED
 ↓
DRAINING
 ↓
RETIRED
```

---

# 49. 故障模型

整个系统需要形成多级 Fault Domain：

```text
Resource
   ↓
Runtime
   ↓
Capability Instance
   ↓
Capability Version
   ↓
Graph Node
   ↓
Sub-Map
   ↓
Graph Generation
   ↓
Map
   ↓
Business
```

核心设计原则：

> **Failure should be contained at the smallest possible boundary.**

---

# 50. 自动调整策略

Control Plane 可以调整：

```text
Instance Count
LB Weight
Routing
Admission
Rate Limit
Circuit Break
Resource Allocation
Graph Version
Capability Version
Gray Policy
Sandbox Level
Security Policy
```

但必须存在控制边界。

---

# 51. Policy Safety

自动调整不能允许 AI 任意修改生产行为。

建议：

```text
AI Recommendation
      ↓
Policy Validation
      ↓
Safety Boundary Check
      ↓
Deterministic Controller
      ↓
Runtime
```

AI 负责：

> 推荐与优化。

确定性系统负责：

> 最终边界执行。

---

# 52. 安全架构

建议至少包含：

```text
Identity
Authentication
Authorization
Sandbox
Network Isolation
Data Isolation
Secret Isolation
Capability Permission
Graph Permission
Runtime Permission
Resource Quota
Audit
Provenance
```

形成：

> **Capability Security Boundary**

---

# 53. 资源与能力的绑定模型

Capability：

```text
Resource Requirement
```

Runtime：

```text
Resource Allocation
```

例如：

```text
ImageAnalysis
Requires:
CPU ≥ 2
Memory ≥ 4GB
GPU ≥ 0.5
```

运行时：

```text
CPU = 2 Core
Memory = 4GB
GPU = 0.5
```

所以：

> **Requirement 是静态的，Allocation 是动态的。**

---

# 54. Resource Bundle

复杂 Capability 可以一次获得复合资源：

```text
4 CPU
+
8GB Memory
+
20GB Disk
+
1Gbps Network
```

形成：

> **Resource Bundle**

这允许整个 Map Subtree 或 Composite Runtime 以整体方式获得资源。

---

# 55. 整体执行与子能力执行

Graph 可以选择：

## Whole-Map Resource Allocation

```text
Composite Capability
      ↓
Resource Bundle
      ↓
Single Runtime
```

## Child Capability Allocation

```text
Composite Capability
 ├── A → Resource A
 ├── B → Resource B
 └── C → Resource C
```

这由 Graph / Resource Policy 决定。

---

# 56. 运维核心视图

Operations Console 应至少支持以下视图：

### Business View

```text
Outcome
SLA
Business Impact
Cost
```

### Map View

```text
Map
Graph
Session
Expansion State
```

### Capability View

```text
Capability
Version
Fitness
Trust
DFX
```

### Runtime View

```text
Instances
Load
Capacity
Queue
Health
```

### Resource View

```text
CPU
GPU
Memory
Network
Storage
```

### Security View

```text
Risk
Policy
Isolation
Violation
```

### Release View

```text
Graph Generation
Rollout
Cohort
Canary
Promotion
Rollback
```

---

# 57. 从业务向下钻取

例如：

```text
Business Outcome
 ↓
Map
 ↓
Graph Generation
 ↓
Capability
 ↓
Instance
 ↓
Resource
```

---

# 58. 从故障向上钻取

例如：

```text
GPU Saturation
 ↓
Runtime
 ↓
Capability B
 ↓
Graph G12
 ↓
Map A
 ↓
Business SLA
```

这形成真正的：

> **End-to-End Causal Operations**

---

# 59. 研发系统整体模块划分

建议首版代码工程划分为：

```text
capability-platform/
│
├── intent/
├── decision/
├── capability-registry/
├── capability-discovery/
├── capability-factory/
├── graph-engine/
├── graph-compiler/
├── map-runtime/
├── session-manager/
├── capability-runtime/
├── resource-scheduler/
├── capacity-controller/
├── load-balancer/
├── rollout-controller/
├── sandbox/
├── policy-engine/
├── security/
├── telemetry/
├── dfx-engine/
├── state-engine/
├── incident-engine/
├── experience-engine/
├── finops/
├── operations-console/
└── api-gateway/
```

---

# 60. 数据模型建议

核心实体至少包括：

```text
Tenant
User
Session

Capability
CapabilityVersion
CapabilityContract
CapabilityExperience

Graph
GraphVersion
GraphGeneration
GraphNode
GraphEdge

Map
MapVersion
MapInstance

Runtime
RuntimeInstance

Resource
ResourcePool
ResourceAllocation

RolloutPolicy
Cohort
Assignment

DFXAssessment
RiskAssessment
HealthState

Incident
Action
Policy

TelemetryEvent
Trace
Log
Metric

Outcome
CostRecord
```

---

# 61. 研发阶段建议

## Phase 0：对象模型

先不要做复杂 Agent。

完成：

* Capability Model；
* Resource Model；
* Graph Model；
* Map Model；
* Session Model；
* Runtime Model；
* Telemetry Model。

目标：

> **把语义边界建立起来。**

---

## Phase 1：单 Map MVP

实现：

```text
External Request
 ↓
Map
 ↓
Graph
 ↓
Capability
 ↓
Runtime
```

Capability 先使用静态服务实现。

---

## Phase 2：Lazy Expansion

加入：

* Lazy Instantiation；
* Resource Allocation；
* Instance Pool；
* LB；
* Scale-out；
* Scale-in。

---

## Phase 3：Session + Gray Release

加入：

* Session Assignment；
* Graph Generation；
* Cohort；
* Multi-dimensional Gray；
* Progressive Rollout；
* Drain；
* Rollback。

---

## Phase 4：Sandbox

加入：

* Sandbox Runtime；
* Resource Quota；
* Network Isolation；
* Data Isolation；
* Identity Isolation；
* Shadow；
* Canary。

---

## Phase 5：DFX Control Plane

建立：

* Metrics；
* Logs；
* Traces；
* State Engine；
* DFX Engine；
* Fault Isolation；
* Automatic Policy Adjustment。

---

## Phase 6：Capability Experience

加入：

* Fitness；
* Adaptability；
* Trust；
* Scenario Experience；
* Graph Experience；
* Recommendation。

---

## Phase 7：Code Agent

最后再加入：

```text
Intent
 ↓
Capability Gap
 ↓
Code Agent
 ↓
Build/Test
 ↓
Sandbox
 ↓
Canary
 ↓
Capability Pool
```

这样可以避免一开始就把系统复杂度推到最高。

---

# 62. MVP 推荐最小闭环

第一个真实 POC 不需要实现全部能力。

只需完成：

```text
Intent
 ↓
Capability Registry
 ↓
Graph
 ↓
Map
 ↓
Session
 ↓
Lazy Capability Instance
 ↓
Resource Allocation
 ↓
LB
 ↓
Scale
 ↓
Telemetry
 ↓
DFX
 ↓
Gray
 ↓
Rollback
```

形成完整闭环。

然后再引入：

> Code Agent Capability Factory。

---

# 63. 关键技术选型原则

具体组件可以变化，但必须满足以下架构要求：

### Registry

需要支持：

* Version；
* Metadata；
* Contract；
* Dependency；
* Experience。

### Graph

需要支持：

* DAG / Graph；
* Version；
* Diff；
* Validation；
* Dynamic Loading。

### Runtime

需要支持：

* Multi-runtime；
* Lazy Instantiate；
* Elasticity；
* Isolation。

### Telemetry

需要：

* Metric；
* Log；
* Trace；
* Event；
* Streaming。

### Control

需要：

* Policy；
* State；
* DFX；
* Decision；
* Action。

不要从某个具体中间件反推架构。

---

# 64. 关键工程不变量

建议把以下不变量直接写入系统设计和自动化测试。

### I1 — Capability Independence

任何 Capability 可以独立实例化执行。

### I2 — Map-only External Invocation

外部只允许调用 Map。

### I3 — Capability Dormancy

未被需求触达的 Capability 不占用 Runtime。

### I4 — Lazy Expansion

Map 只有在需求触达并满足入口条件时才展开。

### I5 — Generation Affinity

Session 在生命周期内默认绑定 Graph Generation。

### I6 — Capacity-aware Routing

LB 不得只根据健康状态分发。

### I7 — Fault Containment

故障应在最小可隔离边界内封闭。

### I8 — Safety Boundary

AI 不得突破确定性资源和安全边界。

### I9 — Sandbox Admission

新 Capability 不得绕过 Sandbox 直接进入普通生产 Runtime。

### I10 — Experience Feedback

运行结果必须进入 Experience Pool。

---

# 65. 核心架构的最终形态

```text
                           ┌───────────────────────┐
                           │    Business Intent    │
                           └───────────┬───────────┘
                                       │
                                       ▼
                           ┌───────────────────────┐
                           │ Intent / Decision     │
                           │ Engine                │
                           └───────────┬───────────┘
                                       │
                                       ▼
                           ┌───────────────────────┐
                           │ Capability Ecosystem  │
                           │                       │
                           │ Discover / Generate   │
                           │ Validate / Experience │
                           └───────────┬───────────┘
                                       │
                                       ▼
                           ┌───────────────────────┐
                           │ Graph Planning        │
                           │ Graph Compiler        │
                           └───────────┬───────────┘
                                       │
                                       ▼
                           ┌───────────────────────┐
                           │      Map Definition   │
                           └───────────┬───────────┘
                                       │
                                 Session Assign
                                       │
                                       ▼
                           ┌───────────────────────┐
                           │      Map Runtime      │
                           │                       │
                           │ Graph Resolution      │
                           │ Lazy Expansion        │
                           │ Capacity-aware LB     │
                           │ Elasticity            │
                           └───────────┬───────────┘
                                       │
                                       ▼
                       ┌────────────────────────────────┐
                       │      Capability Runtime Pool   │
                       │                                │
                       │ Thread / Process / Container   │
                       │ VM / Serverless / Remote       │
                       └───────────────┬────────────────┘
                                       │
                                       ▼
                           ┌───────────────────────┐
                           │     Resource Pool     │
                           │ CPU / GPU / Mem /     │
                           │ Network / Storage/KV  │
                           └───────────┬───────────┘
                                       │
                                       ▼
                                  Execution
                                       │
          ┌────────────────────────────┼───────────────────────────┐
          │                            │                           │
          ▼                            ▼                           ▼
       Metrics                       Logs                        Trace
          │                            │                           │
          └────────────────────────────┼───────────────────────────┘
                                       ▼
                           ┌───────────────────────┐
                           │     Control Plane     │
                           │                       │
                           │ State Assessment      │
                           │ DFX                  │
                           │ Security             │
                           │ Risk                 │
                           │ Capacity             │
                           │ Policy               │
                           └───────────┬───────────┘
                                       │
                         ┌─────────────┼─────────────┐
                         ▼             ▼             ▼
                       Scale        Isolate       Graph Update
                         │             │             │
                         └─────────────┼─────────────┘
                                       ▼
                              Runtime Adaptation
                                       │
                                       ▼
                           Experience / Fitness
                                       │
                                       ▼
                              Capability Pool
                                       ↺
```

---

# 66. 最终架构范式

整个 Capability Operating System 可以浓缩为：

## 四个核心资产

> **Resource Pool**

> **Capability Pool**

> **Graph / Map**

> **Capability Experience**

---

## 四个核心引擎

> **Decision Engine**

> **Map Runtime**

> **DFX Control Plane**

> **Capability Factory**

---

## 四个核心运行机制

> **Lazy Instantiation**

> **Elastic Runtime**

> **Progressive Delivery**

> **Closed-loop Adaptation**

---

# 67. 最终战略定位

Capability OS 并不是：

> Microservice 的另一种实现。

也不是：

> Kubernetes 的上层封装。

也不是：

> Agent Tool Registry。

它的核心变化是：

```text
传统
Application
   ↓
Service
   ↓
Runtime
   ↓
Resource

Capability OS
Business Intent
   ↓
Capability Demand
   ↓
Capability
   ↓
Graph
   ↓
Map
   ↓
Runtime
   ↓
Resource
   ↓
Outcome
   ↓
Experience
   ↺
```

最终形成：

> **从“产品中心”走向“能力中心”；**
>
> **从“静态部署”走向“动态实例化”；**
>
> **从“固定流程”走向“Graph-driven Runtime”；**
>
> **从“人工运维”走向“DFX-driven Control”；**
>
> **从“能力复用”走向“能力自生成与自进化”。**

---

# 68. 最终核心定义

本白皮书建议将整套体系最终定义为：

> **Capability Operating System 是一种以 Business Intent 为入口、以 Capability 为基本生产单元、以 Graph 为关系和编排模型、以 Map 为唯一外部能力边界、以 Runtime Instance 为动态执行载体、以 Resource Pool 为底层生产资料、以 DFX Control Plane 为实时闭环控制系统、以 Code Agent 为能力制造系统、以 Experience Pool 为持续学习记忆的下一代数字平台架构。**

其核心运行规律是：

> **能力保持静态与独立，Graph 负责动态组织，Map 负责按需展开，Runtime 负责实例化，Resource 负责承载，Control Plane 负责观察和调整，Experience 负责持续学习。**

最终形成完整闭环：

# **Intent → Discover → Generate → Validate → Compose → Map → Instantiate → Execute → Observe → Assess → Adapt → Learn → Evolve**

这套架构的最终目标不是让系统拥有更多服务，而是让系统具备一种新的生产能力：

> **理解业务需要什么，找到或创造需要的能力，把能力组织成地图，在真实环境中按需展开，以最小资源和最小风险完成目标，并从每次运行中学习下一次应该如何做得更好。**

这构成了 **Capability-Native、Intent-Driven、Runtime-Adaptive、DFX-Controlled、Self-Evolving** 的下一代数字平台基础。
