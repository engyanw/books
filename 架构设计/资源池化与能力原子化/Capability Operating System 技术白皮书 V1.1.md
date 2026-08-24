
# 把上述新的变化，刷新到新版本的白皮书

# 回复


已将前面多轮讨论完整汇总，并刷新为 **《Capability Operating System 技术白皮书 V2.0》**。本版重点新增并统一了：

* **Autonomous Business Operating System（ABOS）**与自主业务演进闭环
* **World Sensing / Demand Intelligence / Competitive Intelligence**
* **Capability Factory + Code Agent** 自动生成能力
* **第三方 API / SaaS / SDK / Library / AI / MCP → Capability Adapter**
* **Capability Trust / Fitness / Adaptability / Experience**
* **生产 Sandbox → Shadow → Session-aware Canary → Progressive Promotion**
* **Graph 动态加载、Generation、Lazy Expansion、Demand Propagation**
* **Capacity-aware LB + Elastic Runtime + 自动故障隔离**
* **DFX Control Plane + Fast/Slow 双控制环**
* **Business Builder：用户通过业务意图构建自己的业务系统**
* 从“能力平台”进一步演进到“**可自主发现需求、创造能力、演进 Graph、优化业务系统**”的完整自治架构

[下载《Capability Operating System 技术白皮书 V2.0》](sandbox:/mnt/data/Capability_Operating_System_白皮书_V2.0.docx)




Capability Operating System
技术白皮书 V1.1
从资源池化、能力原子化，到动态能力地图与自主业务演进

Intent → Capability → Graph → Map → Runtime → Outcome → Experience → Evolution
架构参考版本：V2.0
定位：指导平台架构、核心模块、数据模型、运行时与后续研发实施
 
版本说明
V1.1 是 V1.0 与 V2.0 的统一融合版本：保留 V1.0 的完整对象模型、Capability/Graph/Map/Runtime/Resource 分层、运行时算法、数据模型、研发路线和工程约束，同时吸收 V2.0 的自主业务演进能力。V1.1 不以“新增模块堆叠”为目标，而是将用户业务构建、第三方能力接入、能力自动生成、生产 Sandbox、Session 级灰度、DFX 闭环、Experience 学习以及 ABOS 自主进化统一为一条一致的架构主线。
•	引入 World Sensing / Demand Intelligence / Competitive Intelligence，使平台能够自动发现用户痛点、潜在需求和能力差距。
•	引入 Capability Factory，以 Code Agent 为核心，在能力缺口出现时自动完成设计、开发、测试、验收和生产 Sandbox Admission。
•	正式定义 External Capability：三方 API、SaaS、SDK、开源库、MCP/AI Service 等必须封装为 Capability Adapter 后进入 Capability Ecosystem。
•	强化 Map-only Invocation、Lazy Graph Expansion、Session-aware Gray Release、Capacity-aware LB 和 Elastic Runtime。
•	将 DFX 从“监控指标”升级为 Control Plane 的决策输入，并形成 Fast Control Loop + Slow Intelligence Loop。
•	新增 Capability Trust、Fitness、Adaptability、Experience，使能力池从“注册表”演进为能力知识与经验生态。
•	引入 Autonomous Business Evolution，使系统能够从业务反馈到能力生成、Graph 演进和运行策略调整形成闭环自治。
•	明确“人可以退出正常运行回路，但安全、合规、资源和不可逆操作边界必须由系统硬约束”的自治原则。
目录
1. 执行摘要
2. 设计目标与核心原则
3. 概念与对象模型
4. Capability Ecosystem
5. Capability Graph 与 Map
6. Map Runtime 与动态展开
7. 资源池化与弹性运行
8. Session、灰度与渐进发布
9. 生产 Sandbox 与 Capability Trust
10. Control Plane 与 DFX
11. Operations Plane 与运营系统
12. Intent-to-Capability 与业务系统构建
13. Capability Factory 与 Code Agent
14. 第三方能力生态与外部调用
15. Experience、Fitness 与自进化
16. 自治业务操作系统（ABOS）
17. 安全与治理架构
18. 技术实现参考架构
19. 核心数据模型与接口契约
20. 关键运行时算法与控制闭环
21. 研发实施路线与 MVP
22. 非功能目标与验收标准
23. 主要风险与工程边界
24. 结论与战略定位
 
1. 执行摘要
Capability Operating System（Capability OS）是一种面向 AI、Agent、云原生和动态业务场景的下一代数字平台架构。它不再以“应用/微服务/容器”为最小业务组织单元，而以 Capability 作为基本生产单元，以 Graph 描述能力关系，以 Map 作为唯一外部能力边界，以 Runtime Instance 承担按需执行，以 Resource Pool 提供公共生产资料，以 Control Plane 持续观察、评估和调整整个系统。
V2.0 进一步把该平台扩展为一个可以感知外部业务世界、自动理解用户需求、发现能力缺口、调用或生成新能力、形成 Graph 与 Map、在生产 Sandbox 中进行渐进验证，并通过 DFX 和运行经验持续优化能力选择与业务结构的自治系统。
                    AUTONOMOUS BUSINESS LOOP

External World
      ↓
World Sensing → Demand Intelligence → Capability Gap
      ↓                              ↓
Capability Pool  ← Capability Factory / Code Agent
      ↓
Graph Planning → Map → Session Assignment
      ↓
Lazy Expansion → Capability Instances → LB → Resource Pool
      ↓
Execution → Metrics / Logs / Traces / Security Signals
      ↓
DFX Control Plane → Scale / Isolate / Rollback / Graph Update
      ↓
Experience / Fitness / Trust / Adaptability
      └──────────────────────────────→ Capability Pool

平台最终形成从“业务意图”到“业务结果”的完整闭环：
Intent → Discover → Generate → Validate → Compose → Map → Instantiate → Execute → Observe → Assess → Adapt → Learn → Evolve
2. 设计目标与核心原则
2.1 目标
•	让用户以业务意图而非基础设施细节构建业务系统。
•	让 Capability 脱离产品、服务和 Runtime，成为平台级可组合资产。
•	让 Resource 从应用私有资源演进为平台统一调度的公共资源。
•	让 Graph 在运行时按需展开，而不是预先部署完整服务树。
•	让新能力通过 Sandbox、Session-aware Canary 和 DFX Gate 获得生产信任。
•	让运行时数据形成持续控制闭环，并反哺 Capability Pool。
•	最终支持正常业务运行不依赖人工逐次操作，形成受安全边界约束的自治演进。
2.2 十二条核心不变量
不变量	含义
I1 Capability Independence	每个 Capability 满足自身 Contract 后都可以独立实例化和执行。
I2 Map-only Invocation	外部调用只能进入 Map；Capability、Graph 和 Runtime Instance 不直接作为外部业务入口。
I3 Capability Dormancy	能力定义默认 Dormant，不主动占用运行资源。
I4 Lazy Expansion	Map 只有在需求触达并满足入口条件时才展开 Graph。
I5 Generation Affinity	Session 默认绑定一个 Graph Generation，正常生命周期内不发生版本漂移。
I6 Capacity-aware Routing	外部 Capability 调用必须基于下游 Capacity、Health、Load 和 Policy 进行路由。
I7 Fault Containment	故障优先在最小边界内隔离，并优先保证业务目标。
I8 Safety Boundary	AI 可以提出和优化决策，但不得突破硬资源、安全、合规和不可逆操作边界。
I9 Sandbox Admission	新生成或重大升级 Capability 不得直接进入普通生产 Runtime。
I10 Experience Feedback	运行结果必须沉淀为 Capability/Graph Experience。
I11 External Encapsulation	第三方系统、API、SDK、库必须封装成 Capability Adapter 后才能被 Graph/Map 使用。
I12 Autonomous Evolution with Guardrails	系统可以自主发现、生成、部署和优化能力，但关键边界必须由不可绕过的 Policy/Safety 机制保护。
3. 概念与对象模型
Capability OS 最重要的设计工作不是先选技术栈，而是先稳定对象语义。Resource、Capability、Graph、Map、Runtime、Session、Outcome、Experience 是不同层次的对象，不能混为一谈。
Resource
   ↓ consumes
Runtime Instance
   ↓ executes
Capability
   ↕ organized by
Graph
   ↓ exposed through
Map
   ↓ bound to
Session
   ↓ produces
Outcome
   ↓ becomes
Experience

对象	定义	示例
Resource	被分配、消耗、计量和回收的有限生产资料	CPU、GPU、Memory、Disk、Bandwidth、KV Cache、Concurrency
Capability	独立可实例化、可执行和可复用的最小能力单元	RiskScore、OCR、Payment、Detect
Graph	能力之间的关系结构	依赖、顺序、并行、条件、Fallback、Aggregation
Map	以 Graph 为核心并具有外部接口和运行规则的能力边界	OrderMap、RiskMap、CommerceMap
Session	一次连续业务交互及其版本/状态归属	User Session、Transaction Session
Runtime Instance	Capability 在运行时的具体承载实体	Thread、Process、Container、VM、Serverless Function、Remote Runtime
Interface	外部/内部调用方式	API、RPC、Event、Message
Outcome	可验证的业务结果	Order approved、Risk reduced、Latency SLA met
Experience	由真实运行产生的场景化经验	Fitness、Cost、Reliability、Adaptability、Trust
4. Capability Ecosystem
Capability Pool 在 V2.0 中升级为 Capability Ecosystem。它不仅存储能力代码和版本，还保存能力契约、实现来源、Provider、DFX、Trust、Fitness、历史经验以及适用场景。
Capability Ecosystem
├── Capability Definition
├── Capability Implementations
│   ├── Native
│   ├── Self-developed
│   ├── Code-Agent Generated
│   ├── External Adapter
│   └── Hybrid
├── Provider / Implementation
├── Contract
├── Resource Profile
├── Security Profile
├── DFX Profile
├── Cost Profile
├── Trust
├── Fitness
├── Adaptability
└── Experience

4.1 Capability Contract
CapabilityContract {
  identity
  input
  output
  preconditions
  postconditions
  resource_requirement
  state_contract
  policy_contract
  security_contract
  cost_model
  sla_qos
  side_effects
  observability
  version
}

能力 Contract 是平台最重要的边界契约。API 只描述“如何调用”，Capability Contract 则描述“能做什么、需要什么、产生什么、代价是什么、风险是什么以及在什么约束下可以做”。
5. Capability Graph 与 Map
5.1 Graph
Graph 是能力关系模型，不是能力本体。Graph 可以表达 requires、depends_on、parallel、condition、fallback、aggregate、compensate 等关系。Graph 可以被版本化，并在运行时由 Map 动态加载。
Graph v12
Root
├── A
│   ├── D
│   └── E
└── B
    └── F

5.2 Map
Map 是可对外调用的能力边界。它包含 External Interface、Entry Contract、Graph、Expansion Policy、Resource Policy、Routing Policy、Scaling Policy、Security Policy、Lifecycle Policy 和 DFX Contract。
Map = Graph + Entry Contract + Expansion Policy + Resource Policy
    + Routing Policy + Scaling Policy + Security Policy + Lifecycle Policy + DFX Contract

5.3 Map 与 Graph 的关键关系
•	Graph 描述“能力如何连接”，Map 描述“这组能力如何作为一个统一能力运行”。
•	Graph Definition 可以持续演进；Map Runtime 负责选择并绑定适合当前 Session 的 Graph Generation。
•	一次 Map Instance 在生命周期内使用固定的 Graph Generation，但不同 Map Instance 可以并行运行不同 Generation。
•	Graph 可以嵌套引用 Map，形成递归的 Runtime Expansion Tree/DAG。
6. Map Runtime 与动态展开
Map Runtime 是平台的核心执行引擎。其主要职责是：Session 绑定、Graph Resolution、Lazy Expansion、Capability Resolution、Resource Planning、Instance Management、LB、Scaling、Drain 和 Reclaim。
External Request
      ↓
Map Entry
      ↓
Session Resolver
      ↓
Graph Generation Resolver
      ↓
Lazy Graph Expansion
      ↓
Capability Resolution
      ↓
Resource Planning
      ↓
Runtime Instantiation
      ↓
Capacity-aware LB
      ↓
Execution

6.1 按需实例化
Capability 默认 Dormant。只有在 Map Runtime 的一次具体展开过程中，被需求触达并满足 Entry Condition 后才实例化；负载增加时扩展 Instance Pool，负载长期消失时逐步 Drain、Scale In 并释放资源。
6.2 运行时“地图徐徐展开”
T0: Root Map

T1:
Root
└── A1

T2:
Root
├── A1
│   ├── D1
│   └── E1
└── B1

T3:
Root
├── A1,A2,A3
│   ├── D1,D2
│   └── E1
└── B1,B2

Graph Definition 是完整地图；Map Instance 是一次请求正在展开的地图；Capability Instance 是被点亮的节点；Resource Allocation 是节点获得的生产资料。
7. 资源池化与弹性运行
资源池化不等于简单地把服务器放到一个资源池。任何可统一抽象、计量、分配、隔离、调度和回收的有限工作资源，都可以进入资源管理体系。
Physical Resource Pool
  CPU / GPU / Memory / HBM / Disk / NIC
        ↓
Virtual Resource Pool
  vCPU / vMemory / vDisk / vNIC
        ↓
Runtime Resource Pool
  Thread / Queue / Connection / Concurrency
        ↓
AI Runtime Pool
  GPU Compute / HBM / KV Cache / Prefill / Decode

7.1 External Capability 的 Capacity-aware LB
外部调用必须把下游服务视为 Capability Provider Pool，而非单一 Endpoint。LB 需要综合 Health、Load、Capacity、Latency、Queue、Cost、Region、Security 和 Policy。
Capability B
├── B1  Load 30%  Capacity 70%
├── B2  Load 60%  Capacity 40%
└── B3  Load 90%  Capacity 10%

LB Decision → B1 / B2 / B3 (capacity-aware)

8. Session、灰度与渐进发布
灰度的基本归属单位是 Session，而不是单个 Request。一个 Session 一旦被分配到某个 Graph Generation，正常生命周期内保持该归属，从而避免同一会话在不同版本之间漂移。
Gray Cutover
                  T0                      T1
Old Session  ────────────────→ Graph G101
New Session  ────────────────→ Gray Policy → G102

8.1 灰度维度
•	用户：User、Tenant、Customer Segment
•	地理：Country、Region、City、IDC、AZ、PoP
•	终端：Mobile、Desktop、OS、Device Model
•	网络：IP、ASN、ISP、IPv4/IPv6
•	时间：时段、工作日、业务窗口
•	业务：Product、API、Service、Traffic Class
•	动态特征：Risk、Load、Cost、Device Trust
8.2 Progressive Delivery
Prepare → Validate → Sandbox → Shadow → 1% → 5% → 10% → 25% → 50% → 100%
                              │
                              └── Failure → Isolate / Rollback / Drain

9. 生产 Sandbox 与 Capability Trust
任何新生成 Capability 或重大 Capability Upgrade 在首次进入生产环境时必须运行在 Sandbox 中。Sandbox 是生产环境中的受控运行边界，不是普通开发测试环境。
9.1 Sandbox 边界
•	Resource：CPU、Memory、GPU、Disk、Network、Concurrency
•	Identity：独立 Identity / Token Scope
•	Network：Default Deny + Allowlist
•	Data：最小数据访问范围
•	Secrets：最小凭据范围
•	Side Effects：可阻断、模拟或审批
•	Observability：Enhanced Telemetry
9.2 Trust Level
Trust 0  → Candidate
Trust 1  → Sandbox
Trust 2  → Shadow
Trust 3  → Canary
Trust 4  → Restricted Production
Trust 5  → Normal Production

Trust 由 Code Trust、Test Trust、Security Trust、Runtime Trust、DFX Trust、Business Trust 和 Historical Trust 共同形成。
10. Control Plane 与 DFX
Control Plane 是整个系统的决策与控制中枢，不只是监控中心。它实时接收 Metrics、Logs、Traces、Security Signals、Resource Signals 和 Business Signals，并将其转化为 State、Risk、Capacity、Health 和 DFX Assessment。
Runtime
  ↓
Telemetry Stream
  ↓
State Assessment
  ↓
DFX Assessment
  ↓
Risk / Capacity / Health
  ↓
Policy Decision
  ↓
Scale / Route / Isolate / Rollback / Graph Update
  ↓
Runtime

10.1 DFX 九维参考模型
DFX 维度	评价重点
Performance / Scalability	延迟、吞吐、容量、弹性、扩缩容响应时间
Availability / Resilience	故障隔离、降级、恢复、冗余、Blast Radius
Security	身份、权限、数据隔离、攻击、策略违规、风险
Extensibility	新增能力/Graph 是否无需修改 Runtime Core
Maintainability / Observability	日志、Trace、Provenance、可解释性、定位效率
Portability / Compatibility	Capability 与 Runtime Provider 的解耦程度
Deployability	灰度、Canary、Rollback、Drain、零停机演进
Testability	Contract、Functional、Performance、Security、Failure Test
Cost / FinOps	资源利用率、Capability 成本、Session 成本、Outcome 成本
10.2 双闭环
Fast Safety / Runtime Loop
μs ~ seconds
→ LB / Admission / Rate Limit / Circuit Break / Isolation / Resource Guard

Slow Intelligence / Evolution Loop
seconds ~ hours
→ Trend / Prediction / Graph Optimization / Capability Replacement / Cost Optimization

11. Operations Plane 与运营系统
Operations Plane 面向平台运营者、SRE、Capability Operator、安全运营人员和业务运营人员。它消费 Control Plane 的状态与决策，并将业务、Map、Capability、Runtime、Resource 和 Outcome 统一呈现。
Business View
  ↓
Map View
  ↓
Graph / Capability View
  ↓
Runtime View
  ↓
Resource View
  ↓
Security / DFX View

•	Business Operations
•	Map Operations
•	Capability Operations
•	Runtime/SRE Operations
•	Security Operations
•	Release/Gray Operations
•	Incident/Problem Management
•	Capacity Planning
•	FinOps
•	Experience Operations
12. Intent-to-Capability 与业务系统构建
用户不应直接配置容器、Pod、VM、LB 等基础设施，而应通过 Business Builder 描述业务意图、业务对象、规则、SLA、安全与成本约束。平台负责自动完成 Capability Requirement、Capability Discovery、Graph Planning 和 Map Generation。
User Business Intent
      ↓
Business Model (Object / Event / State / Rule / Outcome)
      ↓
Intent Understanding
      ↓
Capability Requirements
      ↓
Capability Discovery / Generation
      ↓
Graph Planning
      ↓
Graph Validation
      ↓
Map Definition
      ↓
Map Runtime

12.1 用户构建业务系统的五种入口
•	自然语言：直接描述业务目标。
•	Business DSL：用业务规则表达事件、条件与动作。
•	Visual Map：拖拽方式定义业务关系。
•	API/SDK：为开发者提供程序化构建能力。
•	Agent：授权一个业务 Agent 自动完成分析、设计、发布和运维。
13. Capability Factory 与 Code Agent
Capability Factory 是平台自动制造能力的工程系统。当 Capability Pool 无法满足业务需求时，Code Agent 接收结构化 Capability Requirement，在安全边界内完成工程实现。
Capability Gap
   ↓
Specification
   ↓
Architecture
   ↓
Code Generation
   ↓
Unit / Integration / Security / Performance / DFX Tests
   ↓
Sandbox Admission
   ↓
Canary
   ↓
Promotion
   ↓
Capability Ecosystem

Code Agent 的目标不是直接修改线上业务系统，而是生产一个具有 Contract、Test Evidence、Security Evidence 和 DFX Evidence 的 Capability Artifact。
14. 第三方能力生态与外部调用
任何三方 API、SaaS、SDK、开源库、AI Service、MCP Tool 或远程系统都必须经过 Capability Adapter 封装后才进入 Capability Ecosystem。Graph/Map 不得直接依赖第三方 Endpoint。
Graph
  ↓
Capability
  ↓
External Capability Adapter
  ├── API/SaaS
  ├── SDK/Library
  ├── AI Service / Model
  └── MCP / Remote Tool

14.1 Provider Independence
业务 Graph 依赖的是 Capability Contract，而不是具体 Provider。相同 Capability 可以存在多个 Provider，平台可以根据 Capacity、Latency、Cost、Security、Region、SLA 和 Policy 动态选择。
14.2 供应链安全
•	SBOM / Dependency Analysis
•	Vulnerability Scan
•	License Compliance
•	Behavior Test
•	Network/Data Policy
•	Sandbox Admission
•	Runtime Telemetry
15. Experience、Fitness 与自进化
Capability Pool 最终不应只是“代码和版本”的索引，而应成为能力知识与经验池。每次真实运行都会产生场景化证据，并用于未来能力选择、Graph 选择与能力演进。
Capability Experience
├── Scenario
├── Observed Performance
├── Reliability
├── Security
├── Cost
├── Fitness
├── Adaptability
├── Trust
├── Outcome
└── Provenance

15.1 Fitness
Fitness 是 Capability 对当前业务上下文的适合程度，可综合 Functional Fit、Performance Fit、Security Fit、Reliability Fit、Resource Fit、Cost Fit 和 Context Fit。
15.2 Adaptability
Adaptability 描述业务、流量、环境、资源条件变化后，Capability 是否仍能保持目标能力。
16. 自治业务操作系统（ABOS）
当系统能够感知用户、市场、竞争对手、技术趋势、运行状态和业务结果，并能自动把这些信号转换成新的 Business Intent、Capability Gap、Graph Change 和 Map Change 时，Capability OS 开始演进为 Autonomous Business Operating System（ABOS）。
External World
   ↓
World Sensing
   ↓
Demand Intelligence
   ↓
User Pain / Latent Intent
   ↓
Competitive Intelligence
   ↓
Capability Gap
   ↓
Reuse or Capability Factory
   ↓
Graph / Map Evolution
   ↓
Runtime
   ↓
DFX / Experience
   ↓
Self Optimization
   └──────────────────────→ External World

16.1 World Sensing Plane
•	用户反馈：工单、客服、评论、问卷、行为路径。
•	业务行为：失败率、放弃点、人工绕行、功能使用强度。
•	市场信息：公开竞品功能、发布节奏、定价、技术资料。
•	环境信息：法规、技术演进、威胁情报、基础设施成本。
16.2 Demand Intelligence
系统不只识别显性需求，还应从行为、反馈和上下文中推断潜在业务诉求，并形成结构化 Business Intent。
16.3 Competitive Intelligence
系统对合法可获得的公开信息进行能力地图对比，形成 Capability Gap、Priority 和 Opportunity。
16.4 Autonomous Evolution
系统可以自动完成“发现问题 → 形成需求 → 选择/生成能力 → 编排 Graph → Sandbox → Canary → Production → DFX → 学习”的连续闭环。
17. 安全与治理架构
自治系统的核心不是取消约束，而是在定义好的边界内扩大自动化范围。安全、资源、数据、合规和不可逆操作边界必须通过确定性机制固化。
AI / Decision
      ↓
Policy Validation
      ↓
Hard Safety Boundary
├── Resource Boundary
├── Security Boundary
├── Data Boundary
├── Compliance Boundary
└── Irreversible Action Boundary
      ↓
Deterministic Runtime Control

18. 技术实现参考架构
                     EXPERIENCE PLANE
             Business / User / Operator / Agent
                            │
                            ▼
                     OPERATIONS PLANE
     O&M / SRE / Security / FinOps / Release / Business Ops
                            │
                            ▼
                      CONTROL PLANE
 Intent / Decision / Registry / Graph / Policy / DFX / Rollout
 Capacity / Fault / Experience / Learning / Governance
                            │
                            ▼
                      RUNTIME PLANE
      Map Runtime / Session / Graph Expansion / LB
      Capability Instance / Runtime Lifecycle / Sandbox
                            │
                            ▼
                     RESOURCE PLANE
 CPU / GPU / Memory / Network / Storage / KV / Runtime Pools

18.1 建议工程模块
intent/
decision/
capability-registry/
capability-discovery/
capability-factory/
external-adapter/
graph-engine/
graph-compiler/
map-runtime/
session-manager/
rollout-controller/
sandbox/
load-balancer/
capacity-controller/
resource-scheduler/
policy-engine/
security/
telemetry/
dfx-engine/
state-engine/
incident-engine/
experience-engine/
finops/
operations-console/
api-gateway/
19. 核心数据模型与接口契约
建议以这些实体作为领域模型核心，并进一步通过 Event Sourcing/State Projection 或等价机制维护运行状态。
领域	核心实体
Business	Tenant, User, Session, Outcome
Capability	Capability, Version, Contract, Provider, Adapter, Experience
Graph/Map	Graph, GraphVersion, Generation, Node, Edge, Map, MapInstance
Runtime	RuntimeInstance, Allocation, HealthState
Control	Policy, Rollout, Cohort, Assignment, DFXAssessment, RiskAssessment
Observability	TelemetryEvent, Metric, Log, Trace
Economics	CostRecord, Budget, Metering
19.1 推荐关键接口
POST   /maps/{mapId}/invoke
POST   /sessions/{sessionId}/assign
GET    /capabilities/search
POST   /capabilities/admit
POST   /graphs/validate
POST   /graphs/publish
POST   /rollouts
POST   /runtime/scale
POST   /runtime/isolate
POST   /runtime/rollback
GET    /dfx/{resourceId}
POST   /experience/ingest
POST   /capability-factory/jobs

20. 关键运行时算法与控制闭环
20.1 Graph Resolution
1.	解析 Session → Graph Generation 绑定。
2.	加载 Graph Version 并校验其生命周期状态。
3.	检查 Entry Condition、Policy 和 Resource Feasibility。
4.	按需求展开当前可执行节点，不提前实例化未来不需要的节点。
5.	对 External Call 节点解析 Provider / Capability Instance Pool。
20.2 Capacity-aware Routing
Score(instance) =
  w1 * CapacityHeadroom
+ w2 * LatencyScore
+ w3 * ReliabilityScore
+ w4 * SecurityTrust
+ w5 * Locality
- w6 * Cost

20.3 Scale Decision
Desired Capacity = Demand Forecast × Safety Factor
Scale Out when:
  Demand / Capacity > HighWatermark
Scale In when:
  Demand / Capacity < LowWatermark
  AND IdleTime > Cooldown

20.4 Autonomous Control
Control Plane 的动作应带有 Policy、Confidence、Blast Radius 和 Reversibility 属性。高风险、低可逆性动作需要更高信任门槛；可快速回滚的低风险动作可以自动化程度更高。
21. 研发实施路线与 MVP
阶段	目标	核心交付
Phase 0	对象模型	Capability / Graph / Map / Session / Runtime / Resource / Telemetry
Phase 1	Single Map MVP	Map → Graph → Capability → Runtime
Phase 2	Lazy Runtime	Instance Pool / LB / Scale / Resource Allocation
Phase 3	Session + Gray	Generation / Cohort / Sticky Assignment / Rollout / Drain
Phase 4	Sandbox	Production Sandbox / Shadow / Canary / Trust
Phase 5	Control Plane	Telemetry / State / DFX / Isolation / Auto Action
Phase 6	Experience	Fitness / Adaptability / Trust / Scenario Experience
Phase 7	Capability Factory	Code Agent / Build / Test / Admit / Promote
Phase 8	External Ecosystem	API / SaaS / SDK / Library / AI / MCP Adapters
Phase 9	Autonomous Evolution	Demand Intelligence / Competitive Intelligence / Self-Optimization / ABOS
21.1 MVP 推荐
第一阶段不建议直接实现“全自治”。建议先打通一个真实业务闭环：
Intent
 → Capability Registry
 → Graph
 → Map
 → Session
 → Lazy Instance
 → Capacity-aware LB
 → Elastic Scaling
 → Telemetry
 → DFX
 → Session Gray
 → Rollback

22. 非功能目标与验收标准
维度	验收标准
正确性	Graph Contract Validation 通过率 100%；关键业务路径零不可解释漂移
可用性	核心 Map 支持多级故障隔离、降级和自动恢复
弹性	Capability Instance 能根据 Demand 自动扩缩；Scale-out 延迟有明确 SLO
安全	新 Capability 必须经过 Sandbox；第三方依赖必须经过 Adapter Admission
灰度	Session 级 Sticky Assignment；不同 Generation 逻辑隔离
可观测	Map → Graph → Capability → Instance → Resource Trace 可闭环关联
可回滚	Graph Generation、Capability Version、Rollout 均具备可回滚能力
可演进	新增 Capability 不应要求修改 Runtime Core
成本	支持 Tenant / Map / Capability / Session / Outcome 级计量
自治	自动动作必须记录 Policy、Reason、Evidence、Confidence 和 Rollback Point
23. 主要风险与工程边界
•	过度抽象风险：Capability Contract 不能抹平 GPU、DPU、HBM、Network 等真实硬件差异。
•	动态决策延迟：实时场景必须采用 Fast Loop，不应等待复杂模型。
•	Graph 爆炸：需要 Registry、Version、Template、Policy 和 Graph Validation 抑制组合复杂度。
•	版本共存复杂度：Graph Generation、Capability Version、Session State 必须具备清晰的兼容模型。
•	自治风险：AI 不能绕过硬资源、安全、数据和合规边界。
•	第三方不确定性：Provider SLA、价格和接口变化必须由 Adapter 和 Provider Layer 隔离。
•	能力质量漂移：必须持续做 Fitness、Adaptability 和 Trust 评估，避免历史好能力长期垄断选择。
•	组织与 Conway Law：团队边界需要逐步向 Resource、Capability、Graph/Runtime、Outcome 等平台边界靠拢。
24. 结论与战略定位
Capability Operating System V2.0 已从单纯的“资源池化 + 能力原子化”架构演进为一个完整的、可持续自我优化的业务系统运行与演进平台。
传统软件生产
Product → Service → Runtime → Resource

Capability OS
Intent → Capability → Graph → Map → Runtime → Resource → Outcome

Autonomous Business OS
World → Demand → Intent → Capability → Graph → Map
      → Runtime → Outcome → Experience → Evolution → World

最终平台的核心价值不是拥有更多服务，也不是部署更多 Agent，而是形成一种新的软件生产范式：
“理解业务需要什么，找到或创造需要的能力，把能力组织成地图，在真实环境中按需展开，以最小风险和最合理成本完成目标，并从每次运行结果中学习下一次应该如何做得更好。”
长期目标是形成 Autonomous Business Operating System（ABOS）：正常业务运行不再依赖人工逐次操作；系统能够持续感知用户痛点、市场变化和竞品优势，自动完成需求洞察、能力发现/生成、Graph 演进、灰度发布、资源调度、故障隔离与经验沉淀。与此同时，安全、合规、资源和不可逆动作边界保持确定性、可审计、可回滚。
附录 A：推荐术语表
附录 B：V1.1 统一参考架构与研发原则
附录 C：自主自治成熟度模型
术语	定义
Capability	独立可执行的最小能力单元
Composite Capability	通过 Graph 在运行时形成的复合能力
Graph	能力关系模型
Map	以 Graph 为核心的可调用能力边界
Map Instance	一次请求产生的运行态地图实例
Runtime Instance	Capability 的运行时承载实体
Resource Bundle	一次运行分配的复合资源
Graph Generation	一组运行实例绑定的 Graph 代际标识
Session Assignment	Session 与 Generation 的粘滞绑定
Capability Adapter	将外部系统/库封装成 Capability 的适配层
Capability Factory	自动生成、验证和发布 Capability 的工程系统
Capability Experience	能力在特定场景中的运行经验
Fitness	能力在当前上下文中的适合程度
Adaptability	环境变化下保持能力效果的能力
Trust	能力获得生产权限的可信等级
DFX	面向非功能属性的工程设计与持续评价体系
ABOS	Autonomous Business Operating System
附录 B：V1.1 统一参考架构与研发原则
本附录用于将 V1.0 的基础架构模型与 V2.0 的自主演进模型压缩为一套可直接指导系统设计、API 设计、研发拆分和验收的统一参考架构。
B.1 统一对象模型
系统必须严格区分 Resource、Runtime、Capability、Interface、Graph、Map、Session、Execution、Outcome 和 Experience。
Resource → Runtime Instance → Capability Execution
Capability ↔ Relationship Graph → Map → Session → Outcome → Experience
Resource 是被消耗的生产资料；Runtime 是承载执行的环境；Capability 是独立可执行的静态能力定义；Interface 是调用方式；Graph 是能力关系模型；Map 是唯一外部能力边界；Session 是一次连续业务交互的版本归属载体；Execution 是运行过程；Outcome 是业务结果；Experience 是运行证据沉淀。
B.2 Capability 的最小契约
CapabilityContract {
  identity; version; input; output;
  preconditions; postconditions;
  resource_requirement; state_contract;
  policy_contract; security_contract;
  cost_model; sla_qos; side_effects;
  observability; lifecycle; provenance;
}
Capability 必须独立可实例化和执行；不得要求必须依赖其他 Capability 才能成立。复合能力不是静态打包，而是运行时依据 Relationship Graph 动态展开产生的执行结构。
B.3 Graph、Map 与 Runtime 三层关系
Graph Definition
      ↓
Map Definition = Graph + Entry + Runtime Policies
      ↓
Map Instance + Graph Generation
      ↓
Lazy Expansion
      ↓
Capability Instances / Runtime DAG
Graph 是关系结构，Map 是可调用能力边界，Map Runtime 是执行与生命周期控制器。Graph 可以版本化、动态加载和级联引用 Map；同一 Map 可以并行运行多个 Graph Generation，但单个 Session 在正常生命周期内必须绑定固定 Generation，避免版本漂移。
B.4 资源池化与运行时弹性
资源池化不仅包括 Server、VM、Container 等基础资源，也包括 CPU 时间片、内存、磁盘空间、IOPS、网络带宽、连接、队列、并发度、GPU、HBM、KV Cache 等可被统一管理的工作资源。
Capability Requirement → Resource Planning → Resource Allocation → Runtime Instance
Demand Down → Capacity Up → Capacity-aware LB → Elastic Scaling
能力保持静态，资源动态分配，Runtime Instance 动态创建/销毁。External Capability 必须具备下游负载、容量、健康状态和 SLA 感知能力，LB 以 Capacity-aware Routing 为核心。
B.5 Map 的按需展开与反向收拢
Map 不预先实例化整张能力树。外部请求进入 Map 后，Map Runtime 解析 Session、Graph Generation 和 Entry Condition，仅对当前需求触达且满足条件的节点进行实例化。随着上游需求增加，需求沿 Graph 向下传播；当需求长期消失，Map 沿依赖关系反向 Drain、Scale In 和 Reclaim。
External Request
  ↓ Map Entry
  ↓ Session / Generation
  ↓ Graph Resolve
  ↓ Lazy Expand
  ↓ Instantiate
  ↓ LB / Scale
  ↓ Execute
  ↓ Drain / Reclaim
B.6 第三方能力统一封装
任何第三方 API、SaaS、SDK、开源库、AI Service、MCP Tool 或远程系统都必须经过 External Capability Adapter 封装后进入 Capability Ecosystem。Graph 和 Map 不得直接依赖第三方 Endpoint。
Graph → Capability Contract → External Adapter → Provider / SaaS / SDK / AI / MCP
Provider 可以有多个实现，平台可根据 Capacity、Latency、Cost、Security、Region、SLA 和 Policy 动态选择。外部依赖必须具备 Timeout、Circuit Break、Retry Budget、Rate Limit、Bulkhead、Fallback 和供应链安全控制。
B.7 新能力的生产准入
新生成 Capability 或重大升级必须经过生产 Sandbox 才能进入普通 Runtime。Sandbox 是生产环境中的受控安全域，不是普通开发测试环境。
Generate → Static Validate → Production Sandbox → Shadow → Session Canary → Progressive Promotion → Normal Runtime
Capability Trust 随 Code、Test、Security、Runtime、DFX、Business 和 Historical Evidence 逐步提高。任何异常优先在最小 Fault Domain 内隔离，并自动停止晋级、回滚或 Drain。
B.8 Session-aware Gray Release
灰度的基本归属单位是 Session，而不是单个 Request。新灰度策略仅作用于新 Session；存量 Session 继续使用其原 Graph Generation，直到自然结束或执行受控迁移。
New Session → Rollout Policy → Graph Generation
Existing Session → Keep Assigned Generation
Generation → Capability Version → Instance Pool → Capacity-aware LB
B.9 DFX Control Plane
DFX 是设计、运行、发布、演进和经济性的统一评价体系，不仅是监控指标。V1.1 采用九维 DFX Reference Model：Performance/Scalability、Availability/Resilience、Security、Extensibility、Maintainability/Observability、Portability/Compatibility、Deployability、Testability、Cost/FinOps。
Telemetry → State Assessment → DFX Assessment → Risk / Capacity / Health → Policy Decision → Control → Telemetry
Fast Control Loop 负责确定性、低延迟的 LB、Admission、Rate Limit、Circuit Break、Isolation 和 Resource Guard；Slow Intelligence Loop 负责趋势预测、Graph 优化、Capability 替换、成本优化、灰度晋级和架构演进。
B.10 用户业务系统构建
用户不直接配置 Pod、VM、Container、LB 或 HPA，而通过 Business Builder 表达业务意图、业务对象、事件、规则、SLA、安全和成本约束。系统将其转换为 Capability Requirement，自动发现/生成能力，形成 Graph 并发布为 Map。
Business Intent
  ↓ Business Model
  ↓ Capability Requirements
  ↓ Capability Discover / Generate
  ↓ Graph Planning / Validation
  ↓ Map Definition
  ↓ Sandbox / Canary
  ↓ Map Runtime
用户入口可包括自然语言、Business DSL、Visual Map、API/SDK 和授权 Agent。Map 是用户真正拥有和运营的业务系统边界，底层资源和 Runtime 对用户透明。
B.11 Capability Factory 与 Code Agent
Capability Factory 将能力缺口转化为结构化工程任务。Code Agent 不直接修改线上业务系统，而是生成带 Contract、Tests、Security Evidence、DFX Evidence 和 Provenance 的 Capability Artifact，并由平台统一 Admission、Sandbox、灰度和发布。
B.12 Capability Experience 与学习
每次运行都应产生场景化 Experience Record，记录 Performance、Reliability、Security、Cost、Fitness、Adaptability、Trust、Outcome 和 Provenance。Experience 进入 Capability Ecosystem，用于后续 Capability Ranking、Graph Selection、Provider Selection 和能力演进。
B.13 World Sensing 与自治业务演进
在 V1.1 中，平台从“运行自治”进一步演进到“业务自治”。World Sensing Plane 负责收集用户反馈、业务行为、合法公开的市场与竞品信息、技术和法规变化，并通过 Demand Intelligence 形成 Latent Intent 与 Capability Gap。
World → Demand → Intent → Capability Gap → Reuse / Generate → Graph → Map → Runtime → Outcome → Experience → Evolution → World
系统可以自动发现用户痛点、分析竞争差距、提出业务机会、生成或选择 Capability、更新 Graph、进行 Sandbox/Canary、验证 Outcome，并将经验反馈给 Capability Ecosystem。
B.14 自治边界
自治系统允许人在正常业务运行链路之外，但不能允许 AI 绕过硬约束。Resource、Security、Data、Compliance 和 Irreversible Action Boundaries 必须由确定性机制强制执行。AI 可以提出和执行受控优化，但所有动作必须具备 Policy、Confidence、Blast Radius、Reversibility 等属性。
B.15 研发不变量
• Capability Independence：任一 Capability 在满足自身 Contract 和 Resource Requirement 时都可以独立执行。
• Map-only Invocation：外部调用只能进入 Map。
• Capability Dormancy：未被需求触达的 Capability 不占用 Runtime。
• Lazy Expansion：Map 只按需求逐层展开。
• Generation Affinity：Session 正常生命周期内保持 Graph Generation 亲和。
• Capacity-aware Routing：LB 必须感知容量而非只有健康状态。
• Fault Containment：故障优先隔离在最小可控 Fault Domain。
• Sandbox Admission：新能力不得绕过生产 Sandbox。
• External Encapsulation：第三方依赖必须 Capability 化后接入。
• Experience Feedback：运行证据必须沉淀到 Capability Ecosystem。
• Safety Boundary：AI/Agent 不得突破硬资源、安全、数据和合规边界。
• Human-out-of-loop ≠ Human-out-of-control：正常运行可自治，但边界治理必须可审计、可回滚。
附录 C：自主自治成熟度模型
L0 Manual
人定义、人开发、人发布、人运维。
L1 Copilot
AI 提供需求分析、能力推荐、Graph 推荐和运维建议，人负责批准。
L2 Conditional Autonomous
低风险变更自动执行，高风险动作需要批准。
L3 Autonomous Operations
系统可自动执行能力发布、灰度、扩缩、路由、隔离、回滚和运行优化。
L4 Autonomous Evolution
系统可自动发现用户痛点、洞察潜在需求、分析能力差距、生成 Capability、演进 Graph/Map，并持续优化业务结果。
附录 D：V1.1 一句话架构定义
Capability Operating System 是一种以 Business Intent 为入口、以 Capability 为基本生产单元、以 Graph 为关系与编排模型、以 Map 为唯一外部能力边界、以 Runtime Instance 为动态执行载体、以 Resource Pool 为公共生产资料、以 DFX Control Plane 为实时闭环控制系统、以 Capability Factory 为能力制造系统、以 Experience Pool 为长期学习记忆，并最终向 Autonomous Business Operating System 演进的下一代数字平台架构。
核心范式：Intent → Capability → Graph → Map → Runtime → Resource → Outcome → Experience → Evolution。
