

Intent-Driven Capability Engineering

IDCE 工程方法论 V1.0

面向 Capability Operating System 的系统设计、研发与持续演进方法论

版本：V1.0  |  2026年8月

# 摘要

传统软件工程通常围绕“需求—架构—设计—编码—部署”建立方法论。Capability Operating System（Capability OS）改变了软件系统的基本对象：能力成为可独立执行和复用的生产单元，Graph负责能力关系，Map负责统一能力边界，Runtime负责动态实例化，Resource Pool提供公共生产资料，Control Plane基于Telemetry与DFX持续控制系统。

因此，传统工程方法需要升级为 Intent-Driven Capability Engineering（IDCE，意图驱动的能力工程）。IDCE 不以“实现用户提出的具体功能”为唯一目标，而以“理解并对齐业务意图、评估当前能力充分性、选择正确的实现路径、构建可执行地图、验证非功能属性、运行并从结果中持续学习”为完整工程闭环。

> **说明：** 核心定义：IDCE 是一套将开放的业务意图逐步编译成可验证、可执行、可演进的 Capability Graph / Map / Runtime 的工程方法论。

```text
Intent
  ↓
Intent Alignment
  ↓
Current System Assessment
  ↓
Intent Decision
  ├─ Query
  ├─ Policy
  ├─ Optimization
  ├─ Composition
  ├─ Capability Generation
  └─ Evolution
  ↓
Capability / Policy / Graph Engineering
  ↓
Security + DFX Closure
  ↓
Physical Planning / Map Compilation
  ↓
Sandbox → Canary → Production
  ↓
Runtime → Outcome → Experience
  ↓
Evolution
```

# 目录与阅读方式

- 方法论定位与适用范围

- 核心原则与第一性原理

- IDCE 总体生命周期

- 五看三定

- 阶段 0：项目模式选择——RECOMPOSE / REBUILD / EMERGE

- 阶段 1：Intent Understanding

- 阶段 2：Intent Dialogue 与 Intent Contract

- 阶段 3：Current System Assessment 与 Capability Sufficiency

- 阶段 4：Intent Decision 与实现路径选择

- 阶段 5：Capability Engineering

- 阶段 6：Graph Engineering

- 阶段 7：Map Engineering

- 阶段 8：Map Compilation & Physical Planning

- 阶段 9：Security / DFX Closure

- 阶段 10：Validation、Sandbox 与 Progressive Delivery

- 阶段 11：Runtime Engineering

- 阶段 12：Control Plane 与 Operations

- 阶段 13：Experience Engineering

- 阶段 14：Evolution Engineering

- 三类业务系统建设模式

- 设计制品与模板体系

- 九大评审 Gate

- Code Agent 工程规范

- 研发组织与角色模型

- 实施路线与成熟度模型

- 验收体系、反模式与工程边界

- 结论

# 1. 方法论定位与适用范围

IDCE 是 Capability OS 的配套工程规范，服务于产品经理、业务架构师、系统架构师、Capability 工程师、Runtime 工程师、SRE、Security、DFX、Code Agent 等角色。它既适用于从零构建新产品，也适用于存量系统重构和友商成熟产品对标重建。

| 传统工程 | IDCE |
|---|---|
| 需求相对确定 | 意图可能模糊、可演进，需要对齐 |
| 产品/应用是基本对象 | Capability / Graph / Map 是核心对象 |
| 服务先部署后运行 | Capability 默认 Dormant，按需实例化 |
| NFR 在后期补充 | DFX 从设计开始进入约束闭包 |
| 发布是版本替换 | Session/Generation aware progressive delivery |
| 运行数据主要用于监控 | 运行数据沉淀为 Experience 并参与下一次决策 |
| 新增需求→写代码 | 先评估能力充分性，再决定配置/组合/优化/生成 |

# 2. 核心原则与第一性原理

| 原则 | 工程含义 |
|---|---|
| P1 Intent First | 先理解用户想达成的结果，而不是先接受“功能列表”。 |
| P2 Alignment Before Execution | 未形成可验证的 Intent Contract，不进入生产设计。 |
| P3 Assess Before Build | 先评估现有系统能力，能配置就不开发，能组合就不重造。 |
| P4 Capability Independence | 每个 Capability 必须能独立实例化和执行。 |
| P5 Graph for Relationship | Graph 负责关系与编排，不把业务流程硬编码进单个 Capability。 |
| P6 Map as Boundary | 只有 Map 对外提供统一能力边界，内部 Capability 不直接暴露。 |
| P7 Logic/Physical Separation | Logical Graph 与 Physical Execution Graph 分离。 |
| P8 Safety & DFX by Construction | 安全与 DFX 是设计闭包，不是上线后的附加监控。 |
| P9 Lazy & Elastic | 能力按需实例化，Runtime 根据需求弹性伸缩。 |
| P10 Learn & Evolve | 运行结果必须转化为 Experience，持续驱动选择与演进。 |
| P11 Open Creativity, Closed Execution | 允许意图探索，但执行必须受到安全、资源、合规等硬边界约束。 |
| P12 Product Emerges from Use | 成熟产品模式可以从用户真实路径中涌现，而不是必须预先完整定义。 |

# 3. IDCE 总体生命周期

```text
                Business Intent
                     │
              ┌──────▼──────┐
              │ Understand   │
              └──────┬──────┘
                     ▼
                 Align / Contract
                     ▼
              Current System Assessment
                     ▼
                Intent Decision
        ┌────────────┼──────────────┐
        ▼            ▼              ▼
     Policy       Compose        Generate
        │            │              │
        └────────────┼──────────────┘
                     ▼
              Capability / Graph
                     ▼
             Security + DFX Closure
                     ▼
           Physical Planning / Link
                     ▼
              Map / Executable
                     ▼
           Sandbox → Canary → Prod
                     ▼
             Runtime / Outcome
                     ▼
         Telemetry → DFX → Experience
                     ▼
                  Evolution
```

> **说明：** 工程闭环：IDCE 不是一次性生命周期。Outcome 和 Experience 会重新进入 Intent、Capability、Graph、Policy、Runtime 设计，形成持续循环。

# 4. 五看三定

为了让组织内部形成统一的架构语言，IDCE 将架构思考提炼为“五看三定”。

| 五看 | 核心问题 | 主要产物 |
|---|---|---|
| 看意图 | 用户真正想得到什么？ | Intent Contract |
| 看能力 | 当前系统已经有什么？缺什么？ | Capability Inventory / Sufficiency Assessment |
| 看关系 | 能力如何依赖、组合、分支和回退？ | Logical Graph |
| 看运行 | 系统实际如何运行、消耗和退化？ | Runtime / DFX State |
| 看演进 | 下一阶段如何优化、替换和成长？ | Evolution Plan / Experience |

| 三定 | 核心内容 |
|---|---|
| 定目标 | 确定用户目标、成功标准、范围、约束与风险偏好 |
| 定结构 | 确定 Capability、Graph、Map、Physical Plan |
| 定闭环 | 确定 Runtime、Control、DFX、Experience、Evolution |

# 5. 阶段 0：项目模式选择——RECOMPOSE / REBUILD / EMERGE

| 模式 | 起点 | 核心动作 | 主要风险 | 关键目标 |
|---|---|---|---|---|
| RECOMPOSE | 自有存量系统 | X-Ray → Capability Extraction → Recompose → Shadow → Migration | 遗留依赖、迁移兼容 | 能力解耦与低风险迁移 |
| REBUILD | 友商成熟系统 | Capability Benchmark → Rebuild → Differentiate | 追赶式复制、功能对齐陷阱 | 快速追平后转向个性化 |
| EMERGE | 市场全新产品 | Intent → Capability → Graph → Map → Emergent Product | 需求不确定、产品定义不稳定 | 让产品从用户真实路径中涌现 |

项目立项时首先明确 Genesis Mode。三种模式共享同一 Capability OS 底座，但输入、验证方式、产品策略和成功标准不同。

# 6. 阶段 1：Intent Understanding

用户意图不是简单的一句话需求，也不应直接等价于 Capability Demand。Intent Understanding 的任务是把开放表达转化为可计算的目标、范围、约束和预期结果。

| 字段 | 说明 | 示例 |
|---|---|---|
| Goal | 最终希望改变什么 | 降低误报率 |
| Scope | 影响谁、哪里、何时 | 欧洲移动用户、22:00-06:00 |
| Context | 业务背景 | 登录风控 |
| Outcome | 可验证的结果 | 误报率下降30% |
| Constraints | 不能破坏什么 | 高风险拦截能力不得下降 |
| SLA | 性能/可用性 | P99<100ms |
| Risk Preference | 风险偏好 | 优先安全还是体验 |
| Cost | 预算约束 | 成本不增加20%以上 |
| Exclusions | 明确不做什么 | 不改变支付流程 |

# 7. 阶段 2：Intent Dialogue 与 Intent Contract

系统第一次理解的意图只能被视为 Draft。必须通过多轮澄清、回显、反问和确认，将歧义逐渐收敛为 Intent Contract。

```text
User Intent
  ↓
Interpretation
  ↓
Ambiguity / Risk Detection
  ↓
High-information Question
  ↓
User Answer
  ↓
Intent Model Update
  ↓
Residual Ambiguity == 0 ?
  ├─ No → continue dialogue
  └─ Yes → Intent Contract
```

> **说明：** 问题选择原则：不是把所有字段都问一遍，而是优先询问对后续架构选择影响最大的变量，即具有高信息增益的问题。

| Intent Contract 必备项 | 验收条件 |
|---|---|
| 目标与范围 | 无关键歧义 |
| 成功标准 | 可验证、可度量 |
| 风险偏好 | 冲突场景下有明确优先级 |
| 约束 | 性能、成本、安全、合规明确 |
| 排除项 | 明确不可触碰的边界 |
| 确认状态 | 用户确认或授权代理确认 |

# 8. 阶段 3：Current System Assessment 与 Capability Sufficiency

Intent 对齐后，系统必须先检查当前系统，而不是默认进入开发。建议构建 System Capability Digital Twin，维护 Capability、Policy、Graph、Map、Runtime、Resource、DFX、Security、Experience 的当前状态。

```text
Intent Contract
   +
System Digital Twin
   ↓
Capability Sufficiency Assessment
   ├─ Fully Satisfied
   ├─ Capability Exists / Policy Missing
   ├─ Capability Exists / Resource or DFX Insufficient
   └─ Capability Missing
```

| 评估结果 | 后续动作 |
|---|---|
| 能力完全满足 | 直接复用，必要时调整策略 |
| 能力有但策略不满足 | 进入 Policy Compiler |
| 能力有但容量/DFX不足 | 进入 Optimization / Resource / Runtime 调整 |
| 能力缺失 | 进入 Capability Discovery / Factory |

# 9. 阶段 4：Intent Decision 与实现路径选择

| Intent 类型 | 定义 | 典型动作 |
|---|---|---|
| Query | 查询、分析、诊断 | Query Engine |
| Policy | 改变规则、阈值、策略 | Policy Compiler |
| Optimization | 改善性能、成本、可靠性 | Optimization Engine |
| Composition | 组合已有能力 | Graph Planning |
| Capability | 需要新增能力 | Capability Discovery / Factory |
| Evolution | 改变系统长期结构 | Graph/Capability Evolution |

> **说明：** 核心原则：Intent 不等于 Capability Demand。Capability Demand 只是 Intent 的一种可能结果。

# 10. 阶段 5：Capability Engineering

Capability 是独立可实例化、可执行、可复用的最小能力生产单元。每个 Capability 应以 Contract 作为工程边界。

```text
Capability
├── Identity / Version
├── Intent
├── Input / Output Contract
├── Preconditions / Postconditions
├── Resource Contract
├── State Contract
├── Security Contract
├── DFX Contract
├── Cost Model
├── Side Effects
├── Observability
└── Trust / Experience
```

| 能力来源 | 处理方式 |
|---|---|
| 内部现有能力 | 抽取、规范化、封装为 Capability |
| 第三方 API/SaaS | Adapter 封装后进入 Capability Ecosystem |
| 第三方 SDK/Library | 依赖与供应链检查后 Capability 化 |
| AI / MCP / Remote | 统一 Capability Contract + Provider 管理 |
| Code Agent 生成 | Build/Test/Security/DFX/Sandbox/Canary 后入池 |

# 11. 阶段 6：Graph Engineering

Graph 不是 Capability 的静态打包，而是能力在一次或一类运行场景中的动态关系编排模型。Graph 定义可以版本化并在运行时加载，Map Instance 绑定某个 Graph Generation。

| 关系类型 | 语义 |
|---|---|
| Sequence | 顺序依赖 |
| Parallel | 并行执行 |
| Condition | 条件分支 |
| Fallback | 失败替代 |
| Retry | 受控重试 |
| Aggregate | 汇聚 |
| Compensation | 补偿 |
| Dependency | 前置能力依赖 |

> **说明：** 逻辑/物理分离：Logical Graph 描述业务如何组合；Physical Graph 根据 DFX、Security、Resource、ABI、Latency、Isolation、Cost 决定实际运行拓扑。

# 12. 阶段 7：Map Engineering

Map 是唯一对外提供能力的边界。外部调用进入 Map，Map 根据 Session、Generation、Policy 和 Graph 动态展开内部能力。

```text
External Request
  ↓
Map Entry
  ↓
Session Assignment
  ↓
Graph Generation
  ↓
Lazy Expansion
  ↓
Capability Instance Pool
  ↓
Capacity-aware LB
  ↓
Runtime
```

| Map 必备对象 | 作用 |
|---|---|
| Entry Contract | 对外接口与业务边界 |
| Session Policy | 会话与版本亲和 |
| Graph Reference | 逻辑结构 |
| Rollout Policy | 灰度与渐进发布 |
| Security Policy | 安全约束 |
| DFX Contract | 运行质量目标 |
| Resource Policy | 资源预算与调度 |
| Lifecycle Policy | 扩缩、排空、回收 |

# 13. 阶段 8：Map Compilation & Physical Planning

在 Capability OS 中，Map Runtime 不只是执行器，还承担逻辑 Graph 到物理执行产物的编译、链接和装配。

```text
Logical Graph
  ↓
Capability Resolution
  ↓
Dependency / ABI Check
  ↓
Physical Planning
  ├─ In-process Link
  ├─ Runtime Embedded
  └─ External Adapter
  ↓
Binary Link / Script Bundle
  ↓
Map Executable Artifact
  ↓
Artifact Cache
  ↓
Runtime Instance
```

| 执行模式 | 适用条件 |
|---|---|
| In-process Linked | 高性能、ABI兼容、可信、隔离需求低 |
| Embedded Runtime | 脚本/WASM/受控运行时 |
| External Capability | 第三方系统、SaaS、远程模型或高隔离需求 |

> **说明：** 关键不变量：Link 是 Graph Generation 级别的操作，不应在每个 Request 上重复 Link。Map Executable 必须可缓存、可追溯、可复现。

# 14. 阶段 9：Security / DFX Closure

安全和 DFX 不是用户必须显式配置的功能，而是 Intent-to-Execution 编译过程中的自动闭包。

```text
User Intent
  ↓
Functional Capability Closure
  +
Security Overlay
  +
DFX Overlay
  +
Resource / Compliance Overlay
  ↓
Executable Plan
```

| 闭包层 | 自动补充内容 |
|---|---|
| Security | 身份、授权、审计、限流、隔离、异常检测、数据边界 |
| Performance | 容量、LB、队列、延迟预算、扩缩策略 |
| Availability | 健康检查、熔断、Fallback、恢复 |
| Observability | Metrics、Logs、Trace、Provenance |
| Cost | 资源上限、单位经济学、预算告警 |
| Compliance | 数据地域、留存、访问边界 |

## 14.1 Policy Safety Closure

当用户意图属于策略配置时，系统首先验证已有 Capability 是否能够实现目标，再通过 Policy Compiler 生成策略，并自动执行 Security / DFX Closure。

```text
Policy Intent
  ↓
Capability Sufficiency
  ↓
Policy Synthesis
  ↓
Security Risk Assessment
  ↓
DFX Assessment
  ↓
Policy Safety Closure
  ↓
Validation / Canary / Activation
```

## 14.2 Graph-level Safety

安全评估不能只看单个 Capability。合法能力的危险组合必须能够被识别，因此需要同时评估 Capability、Edge、Graph、Map、Runtime 五个层级。

# 15. 阶段 10：Validation、Sandbox 与 Progressive Delivery

新 Capability、Graph 或 Map 不得未经验证直接进入普通生产 Runtime。

```text
Candidate
  ↓
Static Validation
  ↓
Sandbox
  ↓
Shadow
  ↓
Session-aware Canary
  ↓
Progressive Promotion
  ↓
Normal Runtime
  ↓
Old Generation Drain
```

| 阶段 | 目标 |
|---|---|
| Sandbox | 真实生产上下文下限制资源、网络、身份和副作用 |
| Shadow | 真实流量镜像，不影响用户真实结果 |
| Canary | 少量新 Session 使用新 Generation |
| Progressive | 按 Cohort、地域、用户、终端、时间等维度逐步扩大 |
| Drain | 停止新 Session 进入旧 Generation，等待存量会话自然结束 |

# 16. 阶段 11：Runtime Engineering

Runtime 的基本单位不是固定 Service，而是按需求动态产生的 Capability Instance / Map Executable Instance。

```text
Demand Down
──────────────→
Map → Capability → Sub-Map

Capacity Up
←──────────────
Runtime ← Resource Pool
```

| 机制 | 工程要求 |
|---|---|
| Lazy Instantiation | 需求触达且满足入口条件才实例化 |
| Capacity-aware LB | 基于容量、负载、延迟、队列和资源压力分发 |
| Elasticity | 按需求扩缩实例 |
| Lifecycle | Warm / Running / Idle / Draining / Terminating |
| External Capability | 必须感知 Provider Capacity，并支持限流、熔断、Failover |

# 17. 阶段 12：Control Plane 与 Operations

```text
Runtime
  ↓ Metrics / Logs / Trace / Events
State Assessment
  ↓
DFX / Risk / Security
  ↓
Policy Decision
  ├─ LB
  ├─ Scale
  ├─ Isolate
  ├─ Rollback
  ├─ Policy Update
  └─ Graph Evolution
```

| 控制环 | 典型动作 | 特征 |
|---|---|---|
| Fast Loop | LB、限流、熔断、隔离、资源保护 | 低延迟、确定性、边界优先 |
| Slow Loop | 趋势、预测、Graph优化、能力替换、成本优化 | 模型驱动、全局、渐进 |

# 18. 阶段 13：Experience Engineering

运行数据必须被结构化为 Capability Experience，而不是仅保留为日志或监控。

```text
Capability Experience
├── Scenario
├── Capability / Version
├── Graph / Generation
├── Runtime
├── Resource
├── DFX Metrics
├── Security Signals
├── Outcome
├── Fitness
├── Adaptability
└── Trust
```

| 指标 | 含义 |
|---|---|
| Fitness | 对当前场景是否合适 |
| Adaptability | 环境变化后是否仍保持效果 |
| Trust | 经测试、Sandbox、生产运行后形成的可信等级 |
| Experience | 历史真实运行证据 |
| Graph Fitness | 整张执行路径的历史效果 |

# 19. 阶段 14：Evolution Engineering

Evolution Engineering 将产品、能力、Graph、Policy 和 Runtime 都视为可持续演进对象。

```text
Experience
  ↓
Gap / Drift / Opportunity
  ↓
Candidate Evolution
  ├─ Capability Change
  ├─ Graph Change
  ├─ Policy Change
  └─ Runtime / Resource Change
  ↓
Simulation
  ↓
Canary
  ↓
Promotion / Rollback
```

# 20. 三类业务系统建设模式

## 20.1 RECOMPOSE：自有存量系统

```text
Existing System
  ↓
System X-Ray
  ↓
Capability Extraction
  ↓
Capability Normalization
  ↓
New Graph / Map
  ↓
Shadow / Co-run
  ↓
Partial Migration
  ↓
Full Migration
```

## 20.2 REBUILD：友商成熟系统对标

```text
Competitor Capability Baseline
  ↓
Capability Benchmark
  ↓
Rebuild on Capability OS
  ↓
Feature Parity
  ↓
Personalization
  ↓
Differentiation
  ↓
Autonomous Evolution
```

## 20.3 EMERGE：全新产品

```text
World / User Need
  ↓
Intent Alignment
  ↓
Capability Discovery / Factory
  ↓
Graph
  ↓
Map
  ↓
Early Users
  ↓
Pattern Mining
  ↓
Emergent Product
```

> **说明：** 产品哲学：“地上本没有路，走的人多了，便有了路。”在 IDCE 中可转化为：产品不一定先被完整定义，而可以由真实用户意图、重复路径、稳定 Graph 与可验证 Outcome 逐步沉淀。

# 21. 设计制品与模板体系

| 制品 | 用途 | 最少内容 | 负责人 |
|---|---|---|---|
| Intent Contract | 冻结业务意图 | 目标、范围、约束、风险、验收 | 产品/业务+AI |
| Capability Inventory | 能力盘点 | 能力、版本、来源、状态、Experience | 架构师 |
| Capability Contract | 能力工程边界 | I/O、资源、安全、DFX、Side Effect | Capability Owner |
| Logical Graph | 业务编排 | Node、Edge、条件、回退 | 架构师 |
| Physical Graph | 物理执行 | Link、Runtime、Resource、Isolation | Runtime Architect |
| Map Spec | 业务边界 | Entry、Session、Policy、Lifecycle | Map Owner |
| DFX Contract | 非功能要求 | P/A/S/E/M/P/D/T/C | DFX/SRE |
| Rollout Plan | 发布方案 | Cohort、Generation、Canary、Rollback | Release Owner |
| Experience Record | 运行经验 | Scenario、Outcome、Fitness、Trust | Control Plane |
| Evolution Plan | 持续演进 | Gap、Candidate、验证、推广 | Product/Architecture |

# 22. 九大评审 Gate

| Gate | 关键问题 | 必须通过的证据 |
|---|---|---|
| G1 Intent | 是否真正理解需求？ | Intent Contract |
| G2 Sufficiency | 是不是已经有能力？ | Sufficiency Assessment |
| G3 Capability | 能力边界是否清晰？ | Capability Contract |
| G4 Graph | 关系是否正确？ | Logical Graph + Safety Check |
| G5 Physical | 实际怎么跑？ | Physical Graph + Resource Plan |
| G6 Security | 是否存在越权/组合风险？ | Security Closure |
| G7 DFX | 非功能是否满足？ | DFX Contract / Test |
| G8 Runtime | 是否可灰度、伸缩、回滚？ | Runtime Plan |
| G9 Outcome | 是否真的实现目标？ | Acceptance Evidence |

# 23. Code Agent 工程规范

Code Agent 不应接收模糊自然语言后直接写生产代码，而应消费经过 IDCE 编译的工程制品。

```text
Intent Contract
   ↓
Capability Requirement
   ↓
Capability Contract
   ↓
DFX / Security Contract
   ↓
Implementation Task
   ↓
Code Agent
   ↓
Build / Unit / Integration / Security / Performance Tests
   ↓
Sandbox
   ↓
Canary
   ↓
Capability Registry
```

| Code Agent 输入 | 禁止行为 |
|---|---|
| 明确 Capability Contract | 自行扩大业务范围 |
| 明确 DFX/Security Contract | 绕过测试门禁 |
| 明确依赖与运行环境 | 直接修改生产策略 |
| 明确验收标准 | 绕过 Sandbox/Canary |

# 24. 研发组织与角色模型

| 角色 | 主要职责 |
|---|---|
| Business / Product | 定义价值目标、Intent、Outcome、风险偏好 |
| Intent Architect | 负责意图建模、对齐与 Contract |
| Capability Architect | 能力拆解、契约和能力生态 |
| Graph Architect | 逻辑关系和 Graph 设计 |
| Map Architect | Map 边界、Session、Policy、Lifecycle |
| Runtime Architect | 编译、Link、实例化、调度、LB、扩缩 |
| DFX / SRE | 性能、可靠性、可用性、成本、可观测性 |
| Security Architect | Security Closure、隔离、身份、供应链 |
| Control Plane Engineer | State、Policy、自动控制、Experience |
| Code Agent Engineer | Agent Harness、代码生成、自动测试与验收 |

# 25. IDCE 成熟度模型

| 等级 | 特征 | 典型能力 |
|---|---|---|
| L0 Product-centric | 应用/服务/资源中心 | 传统方法 |
| L1 Capability-aware | 识别能力对象 | Capability Registry |
| L2 Capability-native | 能力/Graph/Map成为基本对象 | Capability Contract / Graph |
| L3 Runtime-adaptive | 运行时按需展开 | Lazy / Elastic / Gray / Sandbox |
| L4 Intent-driven | 从意图驱动配置/组合/生成 | Intent Contract / Capability Factory |
| L5 Autonomous Evolution | 系统自主发现、优化和演进 | World Sensing / Experience / Product Emergence |

# 26. 实施路线

- 建立统一对象模型：Intent、Capability、Graph、Map、Runtime、Resource、Policy、DFX、Experience。

- 完成 Intent Contract 与 Capability Contract 模板，建立设计评审门禁。

- 实现 Capability Registry、Graph Engine、Map Runtime 的最小闭环。

- 加入 Lazy Expansion、Capacity-aware LB、Elastic Runtime。

- 加入 Session / Generation / Gray / Sandbox / Rollback。

- 建立 Telemetry、State Assessment、DFX Control Plane。

- 加入 Capability Experience、Fitness、Trust 和 Adaptability。

- 加入 Capability Factory 与 Code Agent。

- 形成 RECOMPOSE / REBUILD / EMERGE 三类项目模板。

- 逐步引入 World Sensing、Demand Intelligence 和 Autonomous Evolution。

# 27. 反模式与工程边界

| 反模式 | 问题 | 替代原则 |
|---|---|---|
| 先开发再问用户 | 意图错位 | Intent Alignment First |
| 用户说什么就创建什么能力 | Capability 泛滥 | Assess Before Build |
| Graph 直接调用第三方 | 外部依赖耦合 | External Capability Adapter |
| 所有 Capability 都 Link 到一个进程 | Blast Radius 过大 | DFX-driven Physical Planning |
| 每个请求重新 Link | 性能不可接受 | Generation-level Artifact Cache |
| 只做 Capability 安全，不做 Graph 安全 | 危险组合逃逸 | Graph-level Safety |
| 只做监控，不做控制 | 闭环缺失 | Observe → Assess → Decide → Act |
| 每次发布迁移老 Session | 状态漂移 | Session Generation Affinity |
| AI 可以突破平台边界 | 自治失控 | Hard Safety Boundary |
| 追求功能数量对标友商 | 产品陷入复制 | Capability / Personalization / Evolution |

# 28. 验收体系

IDCE 的验收不是“代码是否完成”，而是检查从 Intent 到 Outcome 的闭环是否成立。

| 验收域 | 示例指标 |
|---|---|
| Intent | 关键歧义=0，成功标准明确 |
| Capability | 独立执行、Contract稳定、可观测 |
| Graph | 依赖正确、无非法循环、安全通过 |
| Map | 边界明确、版本可追踪、可回滚 |
| Compilation | 构建可复现、Artifact可追溯 |
| Runtime | 扩缩正确、LB感知容量、实例可回收 |
| DFX | P95/P99、可用性、故障恢复、成本达标 |
| Security | 最小权限、隔离、供应链、审计 |
| Outcome | 真实业务目标达到定义阈值 |
| Evolution | 运行经验能进入下一版选择与设计 |

# 29. 项目启动检查表

- 是否明确项目属于 RECOMPOSE、REBUILD 还是 EMERGE？

- 是否已经形成 Intent Draft，并识别关键歧义？

- 是否形成 Intent Contract 和成功标准？

- 是否完成 Current System / Competitor / Market Baseline？

- 是否做过 Capability Sufficiency Assessment？

- 是否明确“配置、组合、优化、生成、演进”的决策？

- 每个 Capability 是否具备独立 Contract？

- Logical Graph 与 Physical Graph 是否分离？

- Map 是否作为唯一外部能力边界？

- 是否完成 Security / DFX Closure？

- 是否定义 Sandbox / Canary / Generation / Session 策略？

- 是否具备 Telemetry → Control → Experience 闭环？

- 是否定义 Capability / Graph / Map / Policy 的版本生命周期？

- Code Agent 是否只在明确契约和验收条件下运行？

# 30. 结论

IDCE 的核心不是发明一套新的流程术语，而是让工程方法与 Capability Operating System 的基本对象和运行规律保持一致。它把“用户想要什么”放在工程入口，把“当前系统有什么”放在开发之前，把“能力如何组织”放在模块设计之上，把“逻辑如何变成物理执行”显式化，把安全与 DFX 变成设计闭包，把运行经验变成下一轮设计输入。

> **说明：** 最终方法论：从 Intent 出发，经 Alignment、Assessment 和 Decision，进入 Configure / Compose / Optimize / Generate / Evolve，再经过 Capability、Graph、Map、Physical Planning、Runtime 和 DFX 闭环，最终以 Outcome 和 Experience 驱动下一轮演进。

```text
IDCE =
Intent Alignment
+ Capability Sufficiency
+ Capability Engineering
+ Graph Engineering
+ Map Engineering
+ Physical Compilation
+ Security / DFX Closure
+ Runtime Engineering
+ Experience Engineering
+ Evolution Engineering
```

最重要的组织层原则是：不要把 AI 当作“更快的程序员”，而应把 AI Code Agent 放置在经过 Intent Contract、Capability Contract、Graph Contract 和 DFX/Security Contract 约束后的工程体系中。这样，AI 才真正成为 Capability Factory，而不是不可控的代码生成器。

# 附录 A：Intent Contract 模板

```text
Intent ID:
Owner:
Version:

Goal:
Scope:
Context:
Actors:
Expected Outcome:

Functional Requirements:
Policy Requirements:
Security Requirements:
Performance / Availability:
Cost Constraints:
Compliance Constraints:
Risk Preference:
Exclusions:

Success Criteria:
Acceptance Criteria:
Open Questions:
User Confirmation:
```

# 附录 B：Capability Contract 模板

```text
Capability ID:
Name:
Version:
Source: Native / Existing / External / Generated

Purpose:
Input Contract:
Output Contract:
Preconditions:
Postconditions:
Resource Contract:
State Contract:
Security Contract:
DFX Contract:
Cost Model:
Side Effects:
Observability:
Dependencies:
ABI / Runtime Requirements:
Trust Level:
Experience References:
Lifecycle State:
```

# 附录 C：Graph Specification 模板

```text
Graph ID:
Version:
Generation:
Root Capability / Entry:

Nodes:
Edges:
Relationships:
Conditions:
Fallback:
Retry:
Aggregation:
Security Closure:
DFX Closure:
Resource Constraints:
Physical Planning Hints:
Rollback Strategy:
```

# 附录 D：Map Specification 模板

```text
Map ID:
Version:
External Interface:
Entry Contract:
Session Policy:
Graph Binding:
Generation Strategy:
Rollout Policy:
Security Policy:
DFX Contract:
Resource Policy:
Lifecycle Policy:
Observability:
Acceptance Criteria:
```

# 附录 E：九大 Gate 评审记录

```text
G1 Intent: PASS / FAIL / WAIVED
G2 Sufficiency: PASS / FAIL / WAIVED
G3 Capability: PASS / FAIL / WAIVED
G4 Graph: PASS / FAIL / WAIVED
G5 Physical: PASS / FAIL / WAIVED
G6 Security: PASS / FAIL / WAIVED
G7 DFX: PASS / FAIL / WAIVED
G8 Runtime: PASS / FAIL / WAIVED
G9 Outcome: PASS / FAIL / WAIVED

Exceptions:
Evidence:
Approver:
Date:
```
