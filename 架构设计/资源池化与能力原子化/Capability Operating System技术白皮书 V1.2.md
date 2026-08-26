

**Capability Operating System**

**技术白皮书 V1.2**

资源池化 · 能力原子化 · 动态能力地图 · 自适应运行 · 自主业务演进

从 Intent → Capability → Graph → Map → Runtime → Outcome → Experience →
Evolution

Version 1.2 / Engineering Reference

# 版本说明

V1.2 在完整保留 V1.1
工程体系基础上，新增意图对齐、策略意图、能力充分性评估、Policy
Compiler、Security/DFX Closure、Map 编译链接、个性化业务系统、Product
Genesis 三路径、新产品市场进入与自治演进等内容。

V1.2 以 V1.0
的完整工程模型为基线，不删除核心章节与关键设计，只在其上吸收后续讨论形成的增量能力。新增重点包括：Capability
Ecosystem、第三方能力统一封装、生产 Sandbox、Session-aware Gray、DFX
Control Plane、Capability Factory、Capability Experience、World
Sensing、Demand Intelligence、Competitive Intelligence、Autonomous
Evolution 以及 Autonomous Business Operating System（ABOS）。

版本原则：V1.0 → V1.2
采用“增量演进”而非“重写压缩”。旧定义若发生变化，以“更新定义 + 原因 +
兼容原则”表达，确保本文同时可作为架构蓝图、工程设计基线和后续 PRD
的上游输入。

# 目录

本文采用 35 个主章节与附录体系。Word
可在打开后更新目录字段；章节按照理论、对象、运行时、治理、业务构建、自治演进、产品生成与工程落地的逻辑组织。

# 1. 执行摘要

传统软件平台以 Application、Service、Product
为基本组织单元：资源绑定在应用下，能力固化在服务代码中，流程被预先编排，运行时主要负责执行既定程序。随着
AI、Agent、Serverless、云原生和动态业务环境发展，平台需要从“静态部署”转向“动态生产”。

本白皮书提出 Capability Operating System（Capability
OS），其核心思想是：资源池化，让资源成为平台级公共生产资料；能力原子化，让能力成为独立可执行、可复用、可组合的生产单元；Graph
描述能力关系；Map 将 Graph 封装为唯一外部能力边界；Map Runtime
在需求触达后按需展开 Graph，并实例化 Capability；Resource Pool
为运行态提供弹性资源；Control Plane 持续收集 Runtime Telemetry，以
DFX、状态、安全、可靠性、成本与业务结果进行评估，并反向调整运行策略。

V1.2 进一步将 Capability OS 从“动态执行平台”推进到“自进化业务平台”：当
Capability Pool 不满足业务需求时，Capability Factory 可借助 Code Agent
自动开发、测试、验收新能力；第三方 API、SaaS、SDK、Library、AI/MCP
等外部依赖必须通过 Adapter 封装为 Capability
后进入能力生态；系统持续沉淀 Capability Fitness、Adaptability、Trust 和
Experience；更高阶段则通过 World Sensing、Demand Intelligence 与
Competitive Intelligence
自动发现用户痛点、竞争差距并驱动业务与能力持续演进。

最终系统目标不是“拥有更多服务”，而是实现：理解业务意图、发现或创造能力、自动形成
Map、按需展开、弹性执行、实时控制、持续学习，并在硬性安全/资源/合规边界内完成自主业务演进。

Business Intent

↓

Capability Requirement

↓

Discover / Generate Capability

↓

Graph Planning

↓

Map Definition

↓

Session Assignment

↓

Lazy Graph Expansion

↓

Capability Instances

↓

Capacity-aware Routing / Elasticity

↓

Execution

↓

Telemetry / DFX / Risk

↓

Control / Adaptation

↓

Experience / Fitness

↺ Capability Ecosystem

# 2. 设计目标与核心原则

## 2.1 目标

- 把资源从产品边界中解耦，实现跨业务资源池化与统一调度。

- 把能力从产品和应用中解耦，形成独立、可复用、可组合的 Capability。

- 通过 Graph 将 Capability 关系建模，并由 Map 在运行时按需展开。

- 实现 Session-aware、Generation-aware、Capacity-aware 的弹性运行。

- 让新能力必须经过 Sandbox、灰度和 DFX Gate 才能进入普通生产环境。

- 统一纳管内部能力、Code Agent 生成能力以及第三方系统/库封装能力。

- 建立 Control Plane，使运行数据持续转化为状态、风险、DFX 和控制动作。

- 建立 Capability Experience Pool，使运行经验反哺后续能力选择。

- 最终支持从人工设计逐渐迈向条件自治和自主业务演进。

## 2.2 十二条核心不变量

| **编号** | **不变量**                             | **含义**                                                                           |
|----------|----------------------------------------|------------------------------------------------------------------------------------|
| I1       | Capability Independence                | 任何 Capability 都具备独立实例化与执行能力。                                       |
| I2       | Map-only Invocation                    | 外部请求只能进入 Map，不能直接调用内部 Capability。                                |
| I3       | Capability Dormancy                    | Capability Definition 默认不运行、不占用运行资源。                                 |
| I4       | Lazy Expansion                         | 只有需求触达且满足入口条件时才展开 Graph、实例化能力。                             |
| I5       | Generation Affinity                    | Session 在正常生命周期内绑定 Graph Generation，灰度切换只影响新 Session。          |
| I6       | Capacity-aware Routing                 | LB 必须考虑下游实际 Capacity，而不仅是健康状态。                                   |
| I7       | Fault Containment                      | 故障优先在最小可隔离边界内封闭。                                                   |
| I8       | Safety Boundary                        | AI 决策不得突破确定性的资源、安全、数据和合规边界。                                |
| I9       | Sandbox Admission                      | 新 Capability 不得绕过 Sandbox 直接进入普通生产 Runtime。                          |
| I10      | Experience Feedback                    | 运行结果必须沉淀为 Capability / Graph Experience。                                 |
| I11      | External Dependency Encapsulation      | 三方 API、SaaS、SDK、Library、AI/MCP 等必须封装为 Capability 后才能被 Graph 调用。 |
| I12      | Autonomous Evolution under Constraints | 系统可以自主发现、生成、发布和优化，但必须始终受硬安全与治理策略约束。             |

# 3. 概念与对象模型

Capability OS
必须首先建立清晰的对象边界。最重要的对象不是技术组件，而是：Capability、Graph、Map、Session、Runtime、Resource、Policy、Experience
和 Outcome。

| **对象**   | **核心问题**               | **静态/动态**   | **典型实例**                                        |
|------------|----------------------------|-----------------|-----------------------------------------------------|
| Resource   | 消耗什么生产资料？         | 池化 + 动态分配 | CPU、GPU、Memory、Disk、Bandwidth、KV Cache         |
| Runtime    | 在哪里运行？               | 动态            | Thread、Process、Container、VM、Serverless Function |
| Interface  | 如何被调用？               | 静态定义        | API、RPC、Event、Message                            |
| Capability | 能做什么？                 | 静态定义        | RiskScore、OCR、Payment、ImageAnalysis              |
| Graph      | 能力如何连接？             | 版本化结构      | Dependency、Sequence、Parallel、Fallback            |
| Map        | 如何作为统一能力对外运行？ | 定义 + 运行实例 | OrderMap、RiskMap、PaymentMap                       |
| Session    | 此次业务交互属于谁？       | 动态状态        | User Session、Tenant Session                        |
| Outcome    | 最终产生什么价值？         | 动态结果        | 订单通过率、风险降低、P99、业务收入                 |
| Experience | 这次运行对未来意味着什么？ | 持续积累        | Fitness、Adaptability、Trust、Cost                  |

## 3.1 Resource 的定义与层次

Resource
是能够被分配、占用、计量、限制和释放的有限生产资料。资源池化不限于“服务器池”，任何可统一管理的有限工作资源都可以进入
Resource Model。

Physical Resource

├── CPU / GPU / Memory / HBM / Disk / NIC

Virtual Resource

├── vCPU / vMemory / vDisk / vNIC

Runtime Resource

├── Thread / Connection / Queue / File Descriptor / Concurrency

AI Runtime Resource

├── KV Cache / Prefill Budget / Decode Budget / Context Capacity

## 3.2 Runtime、Work、Interface 与 Capability

Capability 与 Runtime 不应混淆。Capability 描述“能做什么”；Runtime
描述“在哪里执行”；Interface 描述“如何调用”。线程、进程、容器、VM 和
Serverless Function 是运行载体；API/RPC/Event 是调用接口。原先可能被称为
Work 的概念可以作为一次 Capability Execution
的运行事实，而不是能力定义本身。

## 3.3 Capability 与 API 的区别

API 是接口技术，Capability 是语义生产单元。API 主要描述如何调用，而
Capability Contract
需要说明输入、输出、前置条件、后置条件、资源需求、SLA、成本、权限、风险、状态、副作用与可观测性。只有形成这样的契约，AI/Decision
Engine 才能进行能力匹配和 Graph 规划。

# 4. Capability Ecosystem

Capability Pool 在 V1.2 中升级为 Capability
Ecosystem。它不仅保存能力定义和实现，还保存不同实现来源、Provider、Adapter、DFX、Trust、Fitness、Scenario
Experience 和历史运行证据。

## 4.1 Capability Contract

Capability

├── Identity / Version

├── Intent / Description

├── Input Contract / Output Contract

├── Preconditions / Postconditions

├── Resource Contract

├── State / Context Contract

├── Policy / Security Contract

├── SLA / QoS

├── Cost Model

├── Side Effects

├── Observability / Provenance

└── Lifecycle

## 4.2 Capability 来源

- Platform Native Capability：平台自身提供的基础能力。

- Self-developed Capability：传统研发团队实现的能力。

- Generated Capability：由 Code Agent 根据 Requirement 自动生成的能力。

- External Capability：由第三方 API、SaaS、SDK、Library、AI Model、MCP
  Tool 等封装得到的能力。

- Hybrid Capability：内部与外部能力组合形成的统一能力。

## 4.3 Capability Experience

每个 Capability 除了定义与实现，还应拥有运行经验。Experience 至少关联
Scenario、Map、Graph Generation、Runtime、Resource、DFX、Outcome
与成本，以支持下一次能力选择。

# 5. Capability Graph 与 Map

## 5.1 Graph

Graph 是 Capability Relationship
Model。它描述能力之间的依赖、顺序、并行、条件、Fallback、Retry、Aggregation、Compensation
等关系。Graph 只描述“能力如何连接”，不直接描述当前有多少实例。

A

├── requires → B

├── optional → C

├── parallel → D

├── condition → E

├── fallback → F

└── aggregate → G

## 5.2 Map

Map 是以 Graph 为结构内核、叠加外部接口、入口契约、Expansion
Policy、Resource Policy、Routing/LB Policy、Scaling Policy、Security
Policy、Lifecycle Policy 与 DFX Contract 后形成的可运行能力边界。

Map = Graph + Entry Contract + Expansion Policy + Resource Policy +

Routing Policy + Scaling Policy + Security Policy + Lifecycle Policy +
DFX Contract

## 5.3 Map 与 Graph 的关键关系

Graph 是关系结构，Map 是可运行能力边界。Graph
可以被版本化、动态加载和选择；Map Definition 是静态运行蓝图；Map
Instance 是一次业务请求产生的动态运行实体。一次 Map Instance
在正常生命周期内绑定固定 Graph Generation，避免运行中的 Graph
热切换破坏语义一致性。

## 5.4 Graph 的级联与递归

Graph 可以引用 Sub-Map，Sub-Map 自身又拥有
Graph，因此可以递归形成能力关系树。设计层应允许一般
Graph/DAG，运行时则根据本次请求形成具体 Execution Tree/DAG。

# 6. Map Runtime 与动态展开

## 6.1 按需实例化

Capability 默认 Dormant。只有 Map Runtime 收到需求、解析
Graph、满足入口条件且获得足够资源时，才实例化
Capability。实例生命周期结束后进入 Idle/Drain/Terminate，最终回收资源。

## 6.2 运行时“地图徐徐展开”

T0: Root Map

T1: Root → A1

T2: Root → A1 + B1 + C1

T3: B1 → D1/D2, C1 → E1/E2/E3

T4: 根据持续需求继续扩张实例池

T5: 需求下降 → 子能力先 Drain → Scale In → 反向收拢

完整 Graph Definition 可以静态存在，而 Runtime Graph Instance
逐层按需求展开。该机制使系统能够避免一次性实例化大量闲置能力。

## 6.3 Graph Dynamic Loading

Map Runtime 必须支持 Graph Registry、Graph
Resolver、版本选择、Generation 绑定、校验、热加载与平滑切换。Graph
变化影响未来的 Map Instance；已有 Session 原则上继续使用其绑定的
Generation。

# 7. 资源池化与弹性运行

## 7.1 Resource Requirement 与 Resource Bundle

Capability 只声明 Resource Requirement，不拥有具体资源。运行时可以根据
Graph 的粒度为一个 Capability 或一组紧耦合 Capability 分配 Resource
Bundle。

## 7.2 Demand Propagation

上游请求形成 Demand，Demand 沿 Graph 向下游传播；下游持续反馈
Capacity。系统形成 Demand Down / Capacity Up 的双向控制模型。

## 7.3 Capacity-aware LB

LB 的调度对象不再只是 Instance，而应当是 Capability
Capacity。下游能力需要报告 Load、Available
Capacity、Queue、Latency、Resource Pressure、Scale State 等信息。

## 7.4 External Capability 的 Capacity-aware LB

三方系统自身通常不在本平台 Resource Pool 中，因此平台不能直接扩容
Provider，但可以管理 Adapter 的 Connection
Pool、Concurrency、Queue、Retry Budget，并根据 Provider 的
Capacity/Quota/SLA 进行 Provider Selection、Failover 和限流。

## 7.5 Graph Capacity

对于串行路径，整体吞吐受瓶颈节点、边和资源容量限制；对于并行路径，则需要考虑分流比例与
Join 条件。Graph Scheduler 应能够识别 Bottleneck Capability
并把需求传导到对应的 Scale Controller。

# 8. Session、灰度与渐进发布

## 8.1 Session 模型

灰度的基本单位应从 Request 上升为 Session。Session 一旦被分配到 Graph
Generation，后续请求默认保持 Generation Affinity，以避免状态漂移。

## 8.2 灰度维度

- 用户：User、Tenant、Customer Segment。

- 地理：Country、Region、City、PoP、IDC、AZ。

- 终端：Mobile、Desktop、OS、Device Model。

- 网络：IP、ASN、ISP、IPv4/IPv6。

- 时间：Time Window、Weekday、Business Window。

- 业务：Product、API、Traffic Class、Risk Segment。

- 动态特征：Load、Risk、Cost、Latency 等。

## 8.3 Session-aware Progressive Delivery

Existing Session → old Graph Generation

New Session → Rollout Policy → old/new Generation by cohort

1% → 5% → 10% → 25% → 50% → 100%

100% new session → old generation drain → resource reclaim

## 8.4 自动故障隔离

异常可从 Instance、Capability Version、Graph Node、Sub-Map、Graph
Generation 逐级隔离。回滚优先影响新 Session；存量 Session
根据状态和安全性决定继续运行、受控迁移或终止。

# 9. 生产 Sandbox 与 Capability Trust

## 9.1 Sandbox 的定位

新生成或重大升级 Capability 第一次进入生产上下文时必须先在受控 Sandbox
中运行。Sandbox
不是普通测试环境，而是在真实生产数据流或真实上下文中以受限权限和资源进行验证的运行环境。

## 9.2 Sandbox 隔离边界

- Resource：CPU、Memory、GPU、Network、Disk、KV 等限额。

- Network：Default Deny，仅允许声明的下游访问。

- Data：最小数据访问，敏感数据按需脱敏或代理。

- Identity：独立 Sandbox Identity，不继承完整生产权限。

- Side Effect：高风险动作默认禁止或模拟。

- Telemetry：Sandbox 提高观测粒度，以便快速发现异常。

## 9.3 Shadow / Canary / Normal

Candidate → Sandbox → Shadow → Canary → Restricted Production → Normal
Production

## 9.4 Capability Trust

能力上线资格应通过运行证据逐步获得。Trust 可综合 Code Trust、Test
Trust、Security Trust、Runtime Trust、DFX Trust、Business Trust 和
Historical Trust。出现严重事故时 Trust 应下降并触发隔离或重新准入。

# 10. Control Plane 与 DFX

## 10.1 Control Plane

Control Plane 是判断与控制中枢，不是简单的管理后台。它维护
Capability、Graph、Map、Session、Runtime、Resource、Policy、DFX、Risk、Experience
等对象的全局状态。

## 10.2 Runtime Telemetry

- Metrics：QPS、Latency、Concurrency、Queue、Error、CPU、Memory、GPU、Network。

- Logs：Execution、Error、Policy、Resource、Scale、Lifecycle。

- Trace：跨 Map、Capability、Sub-Map 的完整执行路径。

- Security Signals：Anomaly、Privilege、Policy Violation、Attack
  Pattern。

- Provenance：Tenant、Session、Map、Graph
  Generation、Capability、Instance、Resource、Outcome。

## 10.3 State Assessment

Control Plane 将观测值融合成 Current
State、Trend、Risk、Capacity、Health、Confidence。真正的运行状态不是某一条指标，而是多源证据融合后的状态估计。

## 10.4 DFX 九维参考模型

| **领域**                | **DFX维度**                     | **主要关注**                                           |
|-------------------------|---------------------------------|--------------------------------------------------------|
| Runtime Excellence      | Performance / Scalability       | 性能、容量、弹性、冷启动、扩缩反应时间                 |
| Runtime Excellence      | Availability / Resilience       | 故障隔离、降级、恢复、冗余                             |
| Runtime Excellence      | Security                        | 身份、权限、数据、运行时与供应链安全                   |
| Evolution & Lifecycle   | Extensibility                   | 能力、Graph、Provider 的可扩展性                       |
| Evolution & Lifecycle   | Maintainability / Observability | 可维护、可观测、可解释、可追踪                         |
| Evolution & Lifecycle   | Portability / Compatibility     | Runtime 与基础设施替换、版本兼容                       |
| Engineering & Economics | Deployability                   | Sandbox、Canary、Progressive Delivery、Rollback        |
| Engineering & Economics | Testability                     | Contract、Graph、Failure、DFX 与场景测试               |
| Engineering & Economics | Cost / FinOps                   | Resource Cost、Capability Cost、Map Cost、Outcome Cost |

说明：ISO/IEC 25010 提供软件质量模型框架，但本文的 DFX
字母组合属于本平台工程参考模型，而不是对国际标准缩写体系的逐项引用。

## 10.5 Fast Control Loop / Slow Intelligence Loop

Fast Loop: Health / LB / Admission / RateLimit / Circuit / Isolation /
Resource Guard

Slow Loop: Trend / Prediction / Graph Optimization / Capability
Replacement / Cost Optimization / Rollout

AI
和复杂模型适合慢环；安全边界、资源保护和故障隔离等必须由确定性的快环执行。

# 11. Operations Plane 与运营系统

Operations Plane 面向 SRE、平台运营、能力运营、安全运营、业务运营和
FinOps。它与 Control Plane 的边界是：Control Plane
负责状态、决策和自动控制；Operations Plane
负责可视化、治理、分析、运营流程与人工干预。

| **运营域**            | **核心关注**                          | **关键视图**          |
|-----------------------|---------------------------------------|-----------------------|
| Business Operations   | 业务结果、SLA、体验、成本             | Outcome / Map / SLA   |
| Capability Operations | 能力版本、Fitness、Trust、DFX         | Capability Center     |
| Map Operations        | Graph、Generation、Session、Expansion | Map Topology          |
| Runtime Operations    | 实例、容量、健康、资源                | Runtime / Capacity    |
| Security Operations   | 风险、隔离、策略、审计                | Risk / Security       |
| Release Operations    | 灰度、晋级、回滚、Drain               | Rollout Center        |
| Incident / Problem    | 事件、根因、恢复、复盘                | Incident Center       |
| Capacity Planning     | 业务需求与未来容量                    | Forecast              |
| FinOps                | 资源成本、能力成本、Outcome 成本      | Cost / Unit Economics |

# 12. Intent-to-Capability 与业务系统构建

## 12.1 Business Intent

用户不需要先理解 Service、Container、Kubernetes
或数据库，而应首先描述业务目标、对象、事件、规则、SLA、安全和成本约束。

## 12.2 Intent → Capability Requirement

LLM/Decision Engine 将自然语言 Business Intent 转换为结构化
Requirement，包括
Functional、Performance、Security、Resource、Cost、Compliance 与
Business Outcome。

## 12.3 Capability Discovery

系统以语义匹配、Contract 过滤、Resource/DFX/Security/Cost 约束和历史
Experience 对候选能力进行排序。

## 12.4 Business Map Studio

用户侧应提供 Business Builder/Map
Studio，以业务对象、事件和业务规则为核心，自动生成 Capability Graph 与
Map。技术细节由平台吸收。

## 12.5 用户构建业务系统的五种入口

- 自然语言：直接描述业务目标。

- Business DSL：用简洁规则定义业务逻辑。

- Visual Map：通过可视化方式定义业务关系。

- API/SDK：供专业开发者程序化创建 Map。

- Agent：让业务 Agent 自动完成 Analyze → Discover → Build → Validate →
  Publish。

## 12.6 用户拥有的是 Business Map，而不是一组微服务

业务系统由一个或多个 Map 组成。用户看到的是
OrderMap、RiskMap、PaymentMap 等业务能力，而不是 Pod、VM、Service 和
HPA。

# 13. Capability Factory 与 Code Agent

当 Capability Pool 无法满足 Requirement，系统产生 Capability Gap，并进入
Capability Factory。Code Agent 不应直接修改业务系统，而应按照 Capability
Contract 生成一个新的、可独立验证的能力包。

Capability Gap

↓

Specification

↓

Architecture

↓

Code Generation

↓

Unit / Integration / Security / Performance Tests

↓

Contract / DFX Validation

↓

Sandbox

↓

Canary

↓

Capability Pool

## 13.1 Capability 生成的工程约束

- 必须先生成可验证的 Capability Contract。

- 必须完成自动化测试与安全检查。

- 必须生成可追踪的 Provenance 与 SBOM。

- 必须通过 Resource / DFX 预算检查。

- 必须先进入 Sandbox，不能直接获得普通生产权限。

- 必须能够回滚和隔离。

# 14. 第三方能力生态与外部调用

任何 Graph 对三方系统、SaaS、API、SDK、Library、AI Model、MCP Tool
的依赖，都必须通过 Capability Adapter 封装为 Capability 后进入
Capability Ecosystem。Graph 不直接依赖 Provider。

Graph

↓

Capability

↓

External Adapter

↓

Third-party API / SaaS / SDK / Library / AI / MCP

↓

Provider

## 14.1 Provider Independence

Capability Contract 是业务依赖边界，Provider 是实现来源。一个 Capability
可以存在多个 Provider，Decision/Router 可以根据
Capacity、Latency、Cost、Security、SLA 和地域做 Provider Selection。

## 14.2 External Capability 的容量与可靠性

- Timeout、Circuit Breaker、Retry Budget、Bulkhead、Rate Limit。

- Provider Health、Quota、Capacity、SLA 实时感知。

- Provider Failover 与 Fallback Capability。

- 外部调用产生完整 Trace 和 Cost Attribution。

## 14.3 第三方供应链安全

三方 Library 需要进入 SBOM、漏洞扫描、许可证检查、行为测试和 Sandbox
Admission；第三方 API
需要进行权限、数据流、网络、供应商风险和业务连续性评估。

# 15. Experience、Fitness 与自进化

## 15.1 Capability Fitness

Fitness 是场景相关的能力适配度，而不是绝对质量。建议综合 Functional
Fit、Performance Fit、Security Fit、Reliability Fit、Resource Fit、Cost
Fit 和 Context Fit。

Capability Fitness = Functional Fit × Performance Fit × Security Fit ×
Reliability Fit ×

Resource Fit × Cost Fit × Context Fit

## 15.2 Capability Adaptability

Adaptability 描述环境发生变化后 Capability
是否仍能保持有效性。例如流量增长、攻击模式变化、硬件变化、地区变化或数据分布变化时，Capability
的 DFX 是否持续可接受。

## 15.3 Graph Experience

不仅 Capability 有经验，Graph 也有经验。Graph Experience
应记录不同业务场景下的 P99、可靠性、成本、安全和业务结果，用于下一次
Graph Planning。

## 15.4 Unit Economics

系统应能够把一次业务 Intent 映射到 Capability、Runtime、Resource 与
Outcome，形成 Tenant、Map、Session、Capability、Outcome 多层成本归因。

# 16. 自治业务操作系统（ABOS）

Capability OS 的更高阶段是 Autonomous Business Operating
System（ABOS）：系统不仅执行用户已有需求，还能够通过感知外部世界、分析用户痛点与竞争态势，自主发现机会、创造能力、生成
Graph、发布 Map，并持续根据业务结果优化。

## 16.1 World Sensing Plane

- 用户行为与产品使用数据。

- 客服、工单、反馈、搜索、放弃、失败路径。

- 公开的竞品信息、产品更新、价格和能力变化。

- 行业趋势、技术演进、法规与安全变化。

- 内部业务 KPI、成本、SLA、可靠性与安全事件。

## 16.2 Demand Intelligence

系统将显性反馈转换为 Latent Intent，识别用户真实诉求，并形成结构化
Business Demand。

## 16.3 Competitive Intelligence

系统在合法、公开可获得的信息范围内分析竞品能力、产品体验、价格、公开技术与用户评价，形成
Capability Landscape。

## 16.4 Capability Gap Analysis

User Need

↓

Required Capability

↓

Current Capability

↓

Competitor Capability

↓

Capability Gap

↓

Opportunity Priority

## 16.5 Autonomous Evolution

高自治阶段中，系统可自动提出业务机会，匹配或生成 Capability，生成候选
Graph，经 Sandbox、Canary 和 DFX Gate
后逐步投入生产。运行经验进一步反哺下一轮选择。

## 16.6 自治成熟度

| **等级** | **模式**               | **系统特征**                                                                        |
|----------|------------------------|-------------------------------------------------------------------------------------|
| L0       | Manual                 | 人定义、人开发、人发布、人运维。                                                    |
| L1       | Copilot                | AI 建议，人审批。                                                                   |
| L2       | Conditional Autonomous | 低风险操作自动执行，高风险仍受人工或强策略控制。                                    |
| L3       | Autonomous Operations  | 系统自主完成运行期发现、扩缩、灰度、隔离、回滚与优化。                              |
| L4       | Autonomous Evolution   | 系统可在治理边界内自主发现痛点、形成需求、生成能力、演进 Graph/Map 并持续优化业务。 |

# 17. 安全与治理架构

自治不等于无边界。安全、资源、身份、数据、合规和不可逆操作必须存在系统级硬约束。

AI Recommendation

↓

Policy Validation

↓

Hard Boundary Check

↓

Deterministic Controller

↓

Runtime Action

## 17.1 六类边界

- Identity Boundary：谁可以触发什么能力。

- Data Boundary：能力可以访问什么数据。

- Resource Boundary：任何 Capability/Map 的资源预算上限。

- Security Boundary：风险、攻击与权限边界。

- Compliance Boundary：监管、数据驻留、审计等要求。

- Irreversible Action Boundary：支付、删除、生产配置等高风险不可逆动作。

## 17.2 AI 的职责边界

AI 可以负责理解、规划、预测、推荐与优化；确定性系统负责最终的
Admission、Quota、Authorization、Isolation 和不可突破边界。

# 18. 技术实现参考架构

Experience Plane

Business / Operator

↓

Operations Plane

SRE / FinOps / Security / Business Ops

↓

Control Plane

Intent / Decision / Graph / Policy / DFX / Rollout / Learning

↓

Runtime Plane

Map / Session / Graph Expansion / Capability Instance / LB / Scale

↓

Resource Plane

CPU / GPU / Network / Storage / KV / Runtime Capacity

## 18.1 四平面

Experience Plane

Business / Operator

↓

Operations Plane

SRE / FinOps / Security / Business Ops

↓

Control Plane

Decision / Graph / Policy / DFX / Rollout / Learning

↓

Runtime Plane

Map / Graph Expansion / Capability Instance / LB / Scale

↓

Resource Plane

CPU / GPU / Network / Storage / KV / Runtime Capacity

## 18.2 建议工程模块

- intent、decision、capability-registry、capability-discovery、capability-factory。

- graph-engine、graph-compiler、map-runtime、session-manager、capability-runtime。

- resource-scheduler、capacity-controller、load-balancer、sandbox。

- policy-engine、security、telemetry、dfx-engine、state-engine。

- rollout-controller、incident-engine、experience-engine、finops、operations-console。

# 19. 核心数据模型与接口契约

核心实体建议至少包括：Tenant、User、Session、Capability、CapabilityVersion、CapabilityExperience、Graph、GraphVersion、GraphGeneration、GraphNode、GraphEdge、Map、MapInstance、Runtime、RuntimeInstance、Resource、ResourcePool、ResourceAllocation、RolloutPolicy、Cohort、Assignment、DFXAssessment、RiskAssessment、Incident、Policy、TelemetryEvent、Trace、Log、Metric、Outcome、CostRecord。

## 19.1 推荐关键接口

Capability APIs

\- RegisterCapability

\- ResolveCapability

\- GetCapabilityFitness

\- GetCapabilityCapacity

\- PublishCapability

\- DeprecateCapability

Graph APIs

\- CreateGraph

\- ValidateGraph

\- CompileGraph

\- PublishGraph

\- ResolveGraph

\- DiffGraph

Map APIs

\- CreateMap

\- ValidateMap

\- DeployMap

\- InvokeMap

\- GetMapState

Runtime APIs

\- Instantiate

\- Scale

\- Drain

\- Isolate

\- Reclaim

Control APIs

\- AssessState

\- EvaluateDFX

\- ApplyPolicy

\- Rollback

\- PromoteRollout

## 19.2 最小 Capability Schema

| **字段组** | **关键字段**                                                   |
|------------|----------------------------------------------------------------|
| Identity   | capability_id, version, owner, source, trust_level             |
| Contract   | input_schema, output_schema, preconditions, postconditions     |
| Runtime    | runtime_profiles, interface, state_model                       |
| Resource   | resource_requirements, quotas, scaling_profile                 |
| Policy     | permissions, data_scope, network_policy, side_effects          |
| DFX        | latency_slo, availability_slo, security_score, cost_model      |
| Experience | fitness, adaptability, scenarios, historical_metrics           |
| Lifecycle  | draft, candidate, sandbox, canary, active, deprecated, retired |

# 20. 关键运行时算法与控制闭环

## 20.1 Graph Resolution

输入：Session、Intent、Cohort、Policy、Graph Registry；输出：绑定到本次
Map Instance 的 Graph Generation。流程必须包含版本兼容、Policy
校验、Contract 校验、Security/DFX 检查。

ResolveMap(Request)

→ ResolveSession

→ ExistingSession ? KeepGeneration : RolloutAssignment

→ ResolveGraphGeneration

→ ValidateGraph

→ CreateMapInstance

## 20.2 Lazy Expansion

OnDemand(Node)

→ CheckEntryCondition

→ CheckCapabilityTrust

→ ResolveImplementation/Provider

→ CheckResourceFeasibility

→ AllocateResource

→ InstantiateRuntime

→ RegisterInstance

→ RouteRequest

## 20.3 Capacity-aware Routing

Score(instance) = f(available_capacity, latency, queue, health,
resource_pressure, cost, locality)

Route only inside the resolved Capability/Generation pool.

## 20.4 Scale Decision

Demand \> Capacity + Headroom → Scale Out

Demand \< Capacity × ScaleInThreshold for Cooldown → Drain + Scale In

Sustained Failure → Isolate / Fallback / Rollback

## 20.5 Autonomous Control

慢环根据趋势、预测、DFX 与 Experience
提出策略更新；快环负责硬边界内立即执行。任何高风险 Graph/Capability
变更都必须经过对应的 Admission Gate。

# 21. 研发实施路线与 MVP

## 21.1 MVP 推荐

Phase 0 对象模型与契约

Phase 1 单 Map / 单 Graph / 单 Capability Runtime

Phase 2 Lazy Expansion + Resource Pool + LB + Elasticity

Phase 3 Session + Generation + Gray + Drain/Rollback

Phase 4 Sandbox + Trust + Third-party Adapter

Phase 5 Telemetry + DFX Control Plane + Fault Isolation

Phase 6 Experience / Fitness / Adaptability

Phase 7 Capability Factory + Code Agent

Phase 8 World Sensing + Demand/Competitive Intelligence + Autonomous
Evolution

MVP 的目标不是一次实现全部自治能力，而是打通从“Intent → Capability →
Graph → Map → Runtime → Telemetry → DFX → Experience”的第一条真实闭环。

## 21.2 首个真实业务 POC 建议

选择一个具有明确输入、输出、SLA、可观测性且存在多种实现路径的业务场景。例如风控、内容审核、智能检索、自动化运维或安全检测。先证明能力可独立执行、Graph
可按需展开、外部调用可做 Capacity-aware LB、新能力可进入
Sandbox、Session 灰度可稳定运行，再扩展到自治生成。

# 22. 非功能目标与验收标准

| **类别**      | **验收指标示例**                    | **验收重点**                           |
|---------------|-------------------------------------|----------------------------------------|
| Correctness   | Contract Success Rate ≥ 99.9%       | 输入输出契约和业务语义正确             |
| Performance   | 关键路径 P99 达到业务目标           | Capacity-aware routing、Scale reaction |
| Availability  | 按 Map/Capability SLO 定义          | 故障隔离与自动恢复                     |
| Security      | 零越权、策略违规可阻断              | Sandbox、Identity、Data Boundary       |
| Release       | 灰度可精确到 Cohort / Session       | Promotion、Rollback、Drain             |
| Elasticity    | Demand spike 后在目标时间内获得容量 | Scale-out/Scale-in                     |
| Observability | Trace 覆盖率、Provenance 完整       | 可追溯到 Session/Generation/Capability |
| Cost          | Capability/Map/Outcome 可归因       | FinOps / Unit Economics                |
| Autonomy      | 低风险动作自动闭环成功率            | 自治控制不越过硬边界                   |

# 23. 主要风险与工程边界

## 23.1 过度抽象风险

不能为了统一而抹平 GPU、DPU、HBM、KV Cache 等资源差异。应采用 Common
Resource Model + Specialized Resource Extension。

## 23.2 Graph 动态性风险

Graph 可动态更新，但已有 Session 必须绑定
Generation，防止运行中的语义漂移。

## 23.3 Capability 爆炸风险

必须有 Registry、Graph、Contract、生命周期与 Experience
治理，否则原子化可能演变为新的复杂性。

## 23.4 自治失控风险

必须建立 Policy/Safety
Plane、硬资源边界、权限边界、数据边界和不可逆操作边界。

## 23.5 第三方依赖风险

External Capability 必须通过 Adapter、Capacity、Timeout、Circuit
Breaker、Fallback 和供应链安全治理隔离。

## 23.6 组织挑战

平台组织应逐步从产品烟囱向 Resource Platform、Capability
Platform、Decision/Control Platform、Scenario/Outcome Team
演化。技术架构与 Team Topology 需要相互匹配。

# 24. 结论与战略定位

Capability OS
的核心不是把微服务做得更细，而是改变软件生产和运行的基本对象。传统系统围绕
Application、Service、Container 组织；Capability OS 围绕
Capability、Graph、Map、Runtime 和 Outcome 组织。

最终系统应实现：用户只需描述业务意图，平台自动将其转换成 Capability
Requirement，从 Capability Ecosystem 发现或创造能力，生成经过验证的
Graph/Map；Map Runtime 根据 Session、Demand 和 Capacity
按需展开能力并弹性运行；Control Plane 通过 Telemetry 和 DFX
持续评估并自动调整；Capability Experience 再反哺未来选择；更高阶段通过
World Sensing、Demand Intelligence、Competitive Intelligence 与
Capability Factory 实现业务自身的持续进化。

因此，本白皮书定义的最终范式是：

Resource Pooling

↓

Capability Atomization

↓

Graph Orchestration

↓

Map-based Runtime

↓

Elastic Execution

↓

DFX Control

↓

Experience Learning

↓

Capability Evolution

↓

Autonomous Business Evolution

一句话定义：Capability OS 是一种以 Business Intent 为入口、以 Capability
为基本生产单元、以 Graph 为关系模型、以 Map 为外部能力边界、以 Runtime
为动态执行载体、以 Resource Pool 为生产资料、以 Control Plane/DFX
为闭环控制、以 Capability Factory 为能力制造、以 Experience Pool
为长期记忆，并最终向 Autonomous Business Operating System
演进的下一代数字平台架构。

# V1.2 增量说明

V1.2 在完整保留 V1.1
体系的基础上，进一步吸收最近多轮架构演进：用户意图不再等价于能力需求，而是统一经过意图对齐与系统能力充分性评估；新增
Policy Intent 与 Policy Compiler；新增 Security/DFX 自动闭包；新增 Map
Compilation、Binary Linking、Logical Graph 与 Physical Execution
Graph；新增个性化业务系统、Software Mass Customization 与 Product
Genesis 三路径；并进一步明确从产品基础能力走向 Adaptive / Personalized /
Autonomous Product 的商业演进路径。

# 25. Intent 编译、对齐与意图边界

Business Intent
是系统最高层业务对象。用户意图可能是查询、策略配置、优化、能力需求、能力组合或系统演进，并不必然要求创建新
Capability。系统必须先理解“用户希望系统达到什么状态”，再判断当前系统是否已经具备实现它的条件。

## 25.1 Intent Taxonomy

| **类型**            | **典型诉求**                 | **主要路径**                   |
|---------------------|------------------------------|--------------------------------|
| Query Intent        | 查询、分析、诊断             | Query / Insight                |
| Policy Intent       | 阈值、规则、路由、准入、策略 | Policy Compiler                |
| Optimization Intent | 性能、成本、容量、体验优化   | Optimization Engine            |
| Capability Intent   | 需要新能力                   | Capability Discovery / Factory |
| Composition Intent  | 组合已有能力形成新业务能力   | Graph Planning / Map           |
| Evolution Intent    | 自动适应、替换、升级、演进   | Evolution Engine               |

## 25.2 Intent Dialogue 与 Intent Alignment

系统不能把用户第一次描述直接视为最终意图。应通过多轮澄清、反问、示例回显、冲突确认和结果预览，使用户与系统形成共同认可的
Intent Contract。

> User Intent
>
> ↓
>
> AI Interpretation
>
> ↓
>
> Ambiguity Detection
>
> ↓
>
> Clarification Question
>
> ↓
>
> User Answer
>
> ↓
>
> Intent Model Update
>
> ↓
>
> Residual Ambiguity
>
> ↓
>
> …
>
> ↓
>
> Intent Contract

## 25.3 信息增益驱动提问

系统不应把“尽可能多问问题”当成对齐目标，而应优先询问那些能够最大幅度缩小设计与决策空间的问题，例如风险偏好、核心业务边界、性能与成本冲突、是否允许副作用等。

## 25.4 Intent Contract

Intent Contract 是用户、AI
与平台在当前阶段对业务目标和约束形成的正式共识，可版本化、可审计，并作为后续策略、Graph、Map、Runtime
和验收的上游依据。

| **字段**            | **说明**                     |
|---------------------|------------------------------|
| Objective           | 目标与期望状态               |
| Scope               | 用户、业务、地域、时间等范围 |
| Constraints         | 性能、成本、资源、合规约束   |
| Risk Tolerance      | 风险偏好                     |
| Expected Outcome    | 可验证结果                   |
| Policy Requirement  | 业务策略                     |
| Acceptance Criteria | 验收标准                     |
| Exclusions          | 明确不允许发生的事情         |
| Version             | Intent 版本                  |

## 25.5 Intent Drift 与重新对齐

意图对齐不是一次性的。实际 Outcome
如果长期偏离预期，或用户目标发生变化，系统应检测 Intent
Drift，重新启动对齐，形成新的 Intent Contract，并推动后续计划演进。

> Intent Contract → Execute → Observe → Expectation Gap → Intent Drift →
> Re-align → New Contract

## 25.6 开放创造与受控执行

系统应允许用户在理解层面探索未知领域，但不能因此放宽执行边界。建议将“认知空间”与“执行空间”分离：前者开放创新，后者受安全、资源、合规、权限和不可逆操作边界约束。

# 26. 当前系统能力充分性与执行计划

意图对齐后，第一问题不是“需要开发什么”，而是“当前系统是否已经可以完成”。这要求管控面维护
System Capability Digital Twin，并在真实状态基础上进行 Capability
Sufficiency Assessment。

## 26.1 System Capability Digital Twin

数字孪生应至少描述当前
Capability、Version、Graph、Map、Policy、Runtime、Resource、Capacity、Security、DFX、Provider
和 Experience 状态，并支持按时间回放。

> Intent Contract + System Digital Twin → Capability Sufficiency
> Assessment

## 26.2 四类结论

| **结论**                            | **含义**                 | **动作**                         |
|-------------------------------------|--------------------------|----------------------------------|
| Fully Satisfied                     | 现有能力和策略已满足     | 直接执行/发布策略                |
| Capability Exists, Policy Missing   | 能力已有，仅需改变行为   | Policy Compiler                  |
| Capability Exists, Resource Missing | 能力已有但资源或容量不足 | Capacity / Resource Optimization |
| Capability Missing                  | 能力不足或不存在         | Discovery / Factory              |

## 26.3 Intent-derived Execution Plan

最终应生成一份执行计划，而不是只返回 Capability 列表。

> Execution Plan
>
> ├── Capability Set
>
> ├── Logical Graph
>
> ├── Policy
>
> ├── Security Policy
>
> ├── DFX Policy
>
> ├── Resource Policy
>
> ├── Runtime Policy
>
> ├── Rollout Policy
>
> └── Recovery Policy

# 27. Policy Compiler 与 Security/DFX Closure

策略意图是与 Capability Intent
同等重要的一等场景。已有能力时，优先通过策略编译满足用户目标，而不是无谓开发新
Capability。

## 27.1 Policy Compiler

Policy Compiler
将自然语言或结构化业务规则编译为版本化、可验证、可灰度发布和可回滚的策略。

> Policy Intent → Policy Synthesis → Validation → Security/DFX Closure →
> Rollout → Runtime Control

## 27.2 Policy Safety Closure

用户策略不是最终有效策略。系统应自动叠加平台基线、租户策略、业务策略、Security、DFX、Resource、Compliance、Audit
和 Recovery 约束。

> Effective Policy = User ∩ Business ∩ Platform ∩ Security ∩ Compliance

## 27.3 Mandatory Security / DFX Overlay

当 Intent 进入 Capability Discovery、Policy Configuration 或 Graph
Planning
时，系统自动识别必要的认证、授权、审计、输入校验、限流、健康检查、Trace、Capacity、Cost、恢复与安全能力，并将其作为系统
Overlay 加入执行计划。

## 27.4 Graph-level Safety

单个 Capability 合法并不代表组合合法。安全与 DFX 分析必须覆盖
Capability、Edge、Graph、Map、Runtime，防止合法能力组合后形成危险链路或违反非功能目标。

# 28. Map Compilation、Binary Linking 与物理执行图

V1.2 进一步明确 Capability
的底层实现是可执行软件资产。它可以是脚本、二进制对象或外部适配器。对于可在同一地址空间组合的
Binary Capability，Map Runtime 在 Graph Generation
确定后进行依赖解析、兼容性校验和链接，生成针对当前 Generation 的 Map
Executable Artifact。

## 28.1 Capability Artifact

| **类型**         | **示例**                                           | **执行方式**               |
|------------------|----------------------------------------------------|----------------------------|
| Script           | Python/JS/Lua/DSL                                  | 脚本 Runtime               |
| Binary           | Object/Static Library/Shared Library/Native Module | Linker → Executable        |
| External Adapter | API/RPC/SaaS/SDK/AI/MCP                            | Adapter Runtime → Provider |

## 28.2 三层组合

> Semantic Composition
>
> Graph: A → B → C
>
> Binary Composition
>
> A.o + B.o + C.o → Linker → MapExecutable
>
> Runtime Composition
>
> MapExecutable → Thread / Process / Container / VM / Serverless

## 28.3 Logical Graph 与 Physical Execution Graph

Logical Graph 描述业务关系；Physical Execution Graph 由 Map Compiler
根据 ABI、依赖、性能、隔离、安全、资源和成本等约束决定实际运行拓扑。

> Logical Graph: A → B → C → D
>
> Physical Graph:
>
> Process 1: A + B
>
> Process 2: C
>
> External: D

## 28.4 Graph Generation 与 Executable Artifact

Link 是 Graph Generation 级别的构建步骤，而不是 Request
级别的操作。生成的 Map Executable Artifact 应缓存并可被同一 Generation
的多个 Runtime Instance 复用。Session 一旦绑定
Generation，正常生命周期内继续使用其对应 Executable。

> Capability Versions → Graph Version → Graph Generation → Map
> Executable → Runtime Instances

## 28.5 Binary Compatibility 与隔离

Binary Capability 应声明 ABI、CPU 架构、Runtime
ABI、Symbol、Memory、Thread、Error 与 Security Contract。发现 ABI
或依赖冲突时，应通过 Physical Planning 拆分 Runtime，而不是强制链接。

## 28.6 三种执行模式

| **模式**          | **定位**             | **特点**                          |
|-------------------|----------------------|-----------------------------------|
| In-Process Linked | 同进程高性能执行     | 低延迟、低调用开销，但隔离要求高  |
| Embedded Runtime  | 脚本/WASM 等异构能力 | 保留逻辑单体，提供运行时边界      |
| External Adapter  | 第三方系统/服务      | 容量感知、LB、熔断、Provider 切换 |

# 29. Personalized Business System 与 Software Mass Customization

传统产品为了成本规模化而统一服务所有用户，导致大量功能闲置。Capability
OS 将标准化的 Capability、Resource、Runtime、Control 与个性化的
Intent、Graph、Map、Policy、Experience
分离，使“底层标准化、上层个性化”成为可能。

## 29.1 Product 与 Personalized Map

> Traditional: Product = Fixed Feature Set
>
> Capability OS: Product(User) = Intent + Capability Set + Graph +
> Policy + Runtime

## 29.2 渐进式个性化

推荐按 Global → Segment → Tenant → User → Session
的层级逐步个性化，而非默认每个用户完全独立部署。

## 29.3 Software Mass Customization

能力复用将“重新开发一个产品”的成本降低为“动态选择和组合能力”。系统可以为不同用户构建不同
Map，同时共享底层 Capability Ecosystem、Resource Pool 与 Control Plane。

## 29.4 Emergent Product

产品可以由大量真实用户行为和路径逐步涌现：同一类 Intent、Capability Path
和 Graph Pattern 被反复走通后，被系统识别为稳定模式，再沉淀为标准 Map 或
Product Pattern。

> User Intent → Individual Map → Repeated Pattern → Segment Map → Stable
> Bundle → Emergent Product

# 30. Product Genesis：三类系统建设路径

新版本将产品建设统一为三条路径，三者共享同一 Capability OS，但初始
Capability 来源和产品成熟度不同。

| **路径**  | **起点**           | **能力来源**                                 | **核心策略**                        | **目标**       |
|-----------|--------------------|----------------------------------------------|-------------------------------------|----------------|
| Recompose | 我方存量系统       | 自有系统能力                                 | X-Ray → 提取 → 重组 → Shadow → 迁移 | 重构存量       |
| Rebuild   | 我方没有、友商成熟 | 竞品能力基线 + 外部能力 + 自有能力           | Benchmark → 重构 → 差异化           | 快速追平并超越 |
| Emergence | 市场上全新领域     | User Intent + Capability Ecosystem + Factory | Intent → Capability → Graph → Map   | 创造新类别     |

## 30.1 Recompose：存量重构

从现有系统的业务流程、接口、代码、运行轨迹和用户行为中反向识别
Capability，建立新 Capability Pool 和 Graph，再通过 Read-only → Shadow →
Co-run → Partial Migration → Full Migration 渐进替换。

## 30.2 Rebuild：成熟对标新建

以友商成熟产品形成 Competitor Capability Landscape 和 Baseline
Capability
Set，但不复制产品菜单，而是重构能力边界、Graph、Policy、Runtime
与个性化机制。第三方产品也可通过 External Capability Adapter 成为
Provider。

## 30.3 Emergence：全新产品

不预设完整产品，而提供最小基础能力、Business Builder 和 Capability
Factory，让真实用户意图驱动 Capability、Graph 和 Map
的逐步形成，最终通过重复使用模式形成 Emergent Product。

## 30.4 Product Genesis Engine

> Existing System Baseline
>
> Competitor Capability Baseline
>
> Market / User Intent
>
> ↓
>
> Capability Ecosystem
>
> ↓
>
> Graph Planning
>
> ↓
>
> Map Generation
>
> ↓
>
> Runtime
>
> ↓
>
> DFX / Experience
>
> ↓
>
> Product Evolution

# 31. 新产品的市场进入与用户吸引

新系统在功能尚未成熟时不应要求客户立即迁移生产业务。核心策略是先证明价值，再逐步扩大运行边界。

## 31.1 从 Feature Parity 转向 Time-to-Fit

初期不与成熟友商在功能数量上竞争，而以
Time-to-Fit、Time-to-Evolution、Personalization Rate、Capability Reuse
Rate、Auto-adaptation Rate 和单位结果成本形成新竞争坐标。

## 31.2 早期价值漏斗

> Basic Product → Intent Interaction → Personalized Configuration →
> Personalized Capability → Personalized Map → Shadow/Canary →
> Production Runtime → Autonomous Evolution

## 31.3 Business System X-Ray

早期可以提供只读的 Business System X-Ray / Capability Intelligence
Platform，不改变生产系统，先发现用户、业务、能力、资源、成本、DFX
和浪费，再以 What-if Simulation 与 Shadow Map 证明新架构的价值。

## 31.4 友商能力作为 Provider

不要求用户首先放弃友商。第三方系统、SaaS、API、SDK、AI 和 MCP
工具均可先封装为 Capability Adapter，成为 Provider。平台逐渐掌握统一的
Capability Contract、路由、容量、DFX 与用户专属 Map。

## 31.5 Base Product → Autonomous Product

> Base Product → Adaptive Product → Personalized Product → Autonomous
> Product → Self-Evolving Business OS

# 32. 统一生命周期与自治闭环

Intent、Capability、Graph、Map、Runtime 和 Product Evolution
应视为相互嵌套的生命周期，而不是孤立发布流程。

> Intent Lifecycle:
>
> Capture → Understand → Clarify → Align → Specify → Execute → Observe →
> Re-align → Evolve
>
> Capability Lifecycle:
>
> Discover → Generate → Validate → Admit → Sandbox → Canary → Promote →
> Active → Retire
>
> Graph / Map Lifecycle:
>
> Draft → Validate → Publish → Resolve → Compile/Link → Sandbox → Canary
> → Active → Drain → Retire

## 32.1 三个闭环

| **闭环**       | **核心问题**                   | **机制**                                                        |
|----------------|--------------------------------|-----------------------------------------------------------------|
| Intent Loop    | 是否理解并持续满足用户真实目标 | Dialogue / Contract / Drift / Re-alignment                      |
| Execution Loop | 如何安全、可靠、经济地运行     | Graph / Map / Runtime / Resource / DFX                          |
| Evolution Loop | 如何持续变好                   | Experience / Fitness / Adaptability / Factory / Graph Evolution |

## 32.2 自治等级

| **等级**                  | **能力**                                               |
|---------------------------|--------------------------------------------------------|
| L0 Manual                 | 人定义、人开发、人部署、人运维                         |
| L1 Copilot                | AI 建议，人批准                                        |
| L2 Conditional Autonomous | 低风险自动执行，高风险需确认                           |
| L3 Autonomous Operations  | 自动发现、编排、部署、灰度、扩缩和回滚                 |
| L4 Autonomous Evolution   | 自动发现痛点、洞察需求、创造能力、演进 Graph、形成产品 |

## 32.3 Human-in-Alignment

最终不是无边界地去掉人，而是将人从逐次操作环节中退出，保留在目标、价值、风险偏好和关键边界的确认层。系统在确认的边界内自主执行。

# 33. V1.2 新增核心不变量

| **编号** | **不变量**                                                                                                       |
|----------|------------------------------------------------------------------------------------------------------------------|
| I14      | Intent Bounded Creativity：开放意图探索，但执行必须受安全、资源、合规与平台边界约束。                            |
| I15      | Intent Contract：高歧义或高风险 Intent 未完成对齐不得进入高风险执行。                                            |
| I16      | Capability Sufficiency First：先判断当前系统是否具备能力，再决定是否生成新能力。                                 |
| I17      | Policy First-class：已有能力可满足时，优先用 Policy Compiler 调整行为。                                          |
| I18      | Mandatory Security/DFX Overlay：Intent 形成执行计划时自动附加必要的安全与 DFX 控制。                             |
| I19      | Graph Safety Closure：安全评估覆盖 Capability、Edge、Graph、Map、Runtime。                                       |
| I20      | Generation Executable Binding：Graph Generation 绑定 Map Executable Artifact，Session 保持 Generation Affinity。 |
| I21      | Binary Isolation：ABI、依赖或隔离不满足时不得强制 In-Process Link。                                              |
| I22      | Product Genesis：产品可以从存量重构、成熟对标或全新意图三条路径产生。                                            |
| I23      | Experience Feedback：运行证据必须形成 Capability / Graph / Map Experience。                                      |
| I24      | Human-in-Alignment：人主要确认目标和价值边界，正常运行与低风险演进可自治。                                       |

# 34. V1.2 参考研发路线

| **阶段** | **重点**                                                | **交付价值**                             |
|----------|---------------------------------------------------------|------------------------------------------|
| P0       | Intent Dialogue + Intent Contract + System Digital Twin | 从“理解用户”开始，而不是从“调用能力”开始 |
| P1       | Capability Sufficiency + Policy Compiler + DFX Overlay  | 策略意图与已有能力优先复用               |
| P2       | Graph Engine + Map Runtime + Lazy Expansion             | 形成基本业务 Map                         |
| P3       | Map Compiler / Binary Linker + Physical Planning        | 形成可执行 Map Artifact                  |
| P4       | Session-aware Gray + Sandbox + Trust                    | 安全生产准入                             |
| P5       | External Capability Ecosystem                           | 接入三方能力与 Provider                  |
| P6       | Capability Factory + Code Agent                         | 能力缺口自动研发                         |
| P7       | Experience + Fitness + Autonomous Control               | 自适应运行闭环                           |
| P8       | Product Genesis + Personalized Business System + ABOS   | 产品按用户意图持续形成                   |

# 35. V1.2 统一架构定义

Capability Operating System 是一种以 Business Intent 为入口、以 Intent
Contract 为共识、以 Capability 为独立可执行生产单元、以 Graph
为关系和逻辑编排模型、以 Map 为唯一外部能力边界、以 Map Compiler/Linker
为逻辑到物理执行结构的转换器、以 Runtime Instance 为动态运行载体、以
Resource Pool 为生产资料、以 Control Plane 为状态/安全/DFX/策略闭环、以
Capability Factory 为能力制造系统、以 Experience Pool
为长期运行记忆，并进一步向 Autonomous Business Operating System
演进的新型数字平台架构。

> User Intent
>
> ↓
>
> Intent Dialogue / Alignment
>
> ↓
>
> Intent Contract
>
> ↓
>
> System Capability Assessment
>
> ↓
>
> Policy / Optimize / Compose / Generate
>
> ↓
>
> Capability Closure + Security/DFX Overlay
>
> ↓
>
> Logical Graph
>
> ↓
>
> Physical Planning / Binary Linking
>
> ↓
>
> Map Executable
>
> ↓
>
> Sandbox / Session-aware Canary
>
> ↓
>
> Map Runtime
>
> ↓
>
> Elastic Runtime / Resource Pool
>
> ↓
>
> Outcome
>
> ↓
>
> DFX / Experience / Learning
>
> ↺

最终产品理念也随之改变：系统不必在上线前定义完整产品，而可以从基础能力和真实用户意图开始，让用户逐步走出自己的业务路径；当同类路径反复出现时，再将其沉淀为稳定的
Product
Pattern。因此，产品可以从设计对象演变为运行过程中涌现的能力模式。

# 附录 A：推荐术语表

| **术语**                | **定义**                                                                         |
|-------------------------|----------------------------------------------------------------------------------|
| Capability              | 独立可实例化、可执行、可复用的最小能力生产单元。                                 |
| Composite Capability    | 由 Relationship Graph 在一次运行中动态组织多个 Capability 所形成的复合运行能力。 |
| Graph                   | 描述 Capability 关系、依赖与编排规则的版本化结构模型。                           |
| Map                     | 以 Graph 为核心并定义外部入口和运行规则的可调用能力边界。                        |
| Map Instance            | 某次业务请求产生的 Map 运行实例。                                                |
| Capability Instance     | Capability 在 Runtime 中的动态实例。                                             |
| Resource Pool           | 可统一分配、计量和回收的资源集合。                                               |
| Graph Generation        | Graph 版本在某一运行阶段的具体生效代际。                                         |
| Session Affinity        | Session 在生命周期内保持同一 Graph Generation 的亲和性。                         |
| Capability Fitness      | Capability 对特定场景的适配度。                                                  |
| Capability Adaptability | 能力对业务/环境变化的持续适应能力。                                              |
| Capability Trust        | 能力经过测试、Sandbox、Canary 和生产证据获得的可信度。                           |
| Experience              | Capability/Graph 的历史运行证据及其对未来选择的可用知识。                        |
| Capability Factory      | 自动生成、测试、验收、发布 Capability 的工程系统。                               |
| External Capability     | 由第三方系统、API、SaaS、SDK、Library、AI/MCP 等封装而来的 Capability。          |
| ABOS                    | Autonomous Business Operating System，自主业务操作系统。                         |

# 附录 B：V1.2 统一参考架构与研发原则

Business Intent → Capability Ecosystem → Graph → Map → Session → Runtime
→ Resource

↑ ↓

Experience / DFX ← Telemetry / Outcome

## B.1 统一对象模型

Business Intent

↓

Capability Requirement

↓

Capability / Provider

↓

Relationship Graph

↓

Map Definition

↓

Map Instance / Session

↓

Capability Instance

↓

Runtime Instance

↓

Resource Allocation

↓

Execution / Outcome

↓

Telemetry / DFX / Experience

## B.2 Capability 最小契约

Capability
必须至少描述身份、输入、输出、前后置条件、资源需求、状态、权限、副作用、SLA、成本与可观测性。

## B.3 Graph、Map 与 Runtime 三层关系

Graph 负责结构；Map 负责可调用边界和运行策略；Runtime
负责具体一次调用中的图展开、实例化、路由和生命周期。

## B.4 资源池化与运行时弹性

Resource Requirement 静态；Resource Allocation 动态；Runtime Instance
弹性。Resource Pool 不与业务产品绑定。

## B.5 Map 的按需展开与反向收拢

需求向下传播，容量向上反馈；需求增加时逐层实例化和扩容；需求长期消失时逐层
Drain、Scale In 和 Resource Reclaim。

## B.6 第三方能力统一封装

Graph/Map 只依赖 Capability Contract，不直接依赖 Provider。Provider
可动态替换。

## B.7 新能力生产准入

新 Capability 必须通过 Build/Test/Security/DFX/Sandbox/Canary/Promotion
Gate。

## B.8 Session-aware Gray Release

灰度首先决定新 Session 的 Generation；存量 Session 保持旧
Generation，旧代通过 Drain 自然退出。

## B.9 DFX Control Plane

Telemetry → State → DFX → Policy → Action → Telemetry 形成持续控制。

## B.10 用户业务系统构建

用户通过 Business Builder 描述 Intent，平台自动发现/创造能力并生成业务
Map。

## B.11 Capability Factory

Code Agent 只负责满足 Requirement 的能力生成，不直接修改生产
Graph；生产准入由 Control Plane 管理。

## B.12 Capability Experience 与学习

运行经验必须沉淀到 Capability/Graph Experience，用于下一次选择与规划。

## B.13 World Sensing 与自治业务演进

系统可在合法和治理边界内自动理解用户痛点、竞争优势、业务差距与机会。

## B.14 自治边界

自治操作必须受身份、数据、资源、安全、合规和不可逆操作边界约束。

## B.15 研发不变量

Capability is static; Runtime is dynamic.

Graph is versioned; Session is generation-affine.

Map is externally callable; Capability is internally callable.

Demand propagates downward; Capacity propagates upward.

New capability enters Sandbox before Normal Runtime.

AI may optimize; deterministic policy enforces hard boundaries.

# 附录 C：自主自治成熟度模型

| **等级**                  | **自主能力** | **关键能力**                                                     |
|---------------------------|--------------|------------------------------------------------------------------|
| L0 Manual                 | 人工驱动     | 人工需求、开发、发布、运维                                       |
| L1 Copilot                | AI 辅助      | AI 理解、推荐、人确认                                            |
| L2 Conditional Autonomous | 条件自治     | 低风险运行策略自动调整                                           |
| L3 Autonomous Operations  | 自主运营     | 自动扩缩、灰度、隔离、回滚、优化                                 |
| L4 Autonomous Evolution   | 自主进化     | 自动发现痛点、生成需求、创造能力、演进 Graph/Map、形成新业务机会 |

# 附录 D：研发检查清单

- 是否每个 Capability 都能独立执行？

- 是否不存在 Graph → 三方 Provider 的直接依赖？

- 是否所有外部调用都有 Adapter、Timeout、Circuit Breaker、Capacity
  Awareness？

- 是否支持 Session → Graph Generation 粘滞？

- 是否支持 Lazy Expansion 和 Reverse Reclamation？

- 是否支持 Capability/Graph/Map/Runtime 多级故障隔离？

- 新 Capability 是否强制进入 Sandbox？

- 灰度是否按新 Session 生效而不漂移存量 Session？

- Telemetry 是否可以追踪到 Map/Graph/Capability/Instance/Resource？

- DFX 是否能驱动自动控制，而不是只提供 Dashboard？

- Capability Experience 是否能够反哺选择？

- AI 是否始终处于硬安全/资源/合规边界之内？

- 是否能够从业务 Intent 一直追踪到 Outcome 和成本？

# 附录 E：V1.2 一句话架构定义

资源池化，让资源成为平台级公共生产资料；能力原子化，让能力成为独立可执行的生产单元；Graph
负责关系，Map 负责能力边界，Runtime 负责按需实例化与弹性执行，Control
Plane 负责基于 DFX 的闭环控制，Capability Factory
负责能力生成，Experience Pool
负责持续学习；在安全、资源和治理硬边界内，最终演进为能够自主感知、理解、构建、运行和优化业务系统的
Autonomous Business Operating System。
