
# 能力只在运行时才被调用者按需实例化，所有能力都被地图调用，只有地图可以接收外部调用，地图根据外部调用按需展开，展开过程中，按需并满足能力入口条件，则在第一次调用时，实例化被调用能力，之后根据上游负载需求，弹性伸缩下游的能力实例数量，并将负载需求根据LB算法分发给下游能力实例。所有的实例都是地图的实例化，能力根据上游需求逐步按需实例化，最终地图按需徐徐展开，形成完整的画卷，在上游需求长时间消失时，可按需回收下游能力资源

# 回复

对。到这里，你实际上已经把“能力原子化”的模型进一步推到了一个相当完整的 **Capability Map Runtime** 范式。

而且你最后这段描述里有一个非常重要的原则，我建议直接把它固化为整个架构的第一原则：

> **能力本身不运行，能力只被定义和注册；只有在 Map 的一次运行过程中，能力才被按需实例化。**
>
> **外部请求只进入 Map，不直接进入 Capability；Map 根据请求和关系图逐层展开，并按实际需求动态创建、扩缩和回收 Capability Instance。**

这和传统的微服务、Serverless、Kubernetes 都已经有明显区别。

---

# 一、先把“地图”和“能力”彻底分离

你现在实际上定义了两个完全不同的世界。

## 1. Capability：静态世界

Capability 是：

* 静态定义
* 独立可执行
* 不主动运行
* 不直接接受外部请求
* 不预先占用运行资源
* 可以被多个 Map 引用

例如：

```text
Capability Registry

├── Packet Parse
├── Flow Analyze
├── Feature Extract
├── Threat Detect
├── Risk Score
├── User Query
├── Retrieve
├── Reason
└── Generate
```

Capability 的本质是：

> **“我具备什么能力，以及在什么条件下我可以被实例化。”**

---

# 二、Map 才是实际运行的入口

Map 是一个静态的关系定义：

```text
Map
 ├── Capability A
 │
 ├── Capability B
 │
 ├── Capability C
 │
 └── Relationship
```

但 Map 和普通 DAG 最大的区别是：

> **Map 本身也是可以被实例化、执行和递归展开的运行对象。**

所以应该区分：

```text
Capability Definition
Map Definition
        ↓
      Runtime
        ↓
Capability Instance
Map Instance
```

---

# 三、外部世界永远只能看到 Map

这是你模型中非常重要的一条边界：

```text
External Request
       │
       ▼
┌──────────────────┐
│    Map Endpoint  │  ← 唯一外部入口
└────────┬─────────┘
         │
         ▼
    Map Runtime
         │
         ├── Capability A
         ├── Capability B
         └── Sub-Map C
```

而不是：

```text
External
 ├──→ Capability A
 ├──→ Capability B
 └──→ Capability C
```

也就是说：

> **Capability 永远不是一个外部服务，而是 Map 的内部执行对象。**

这样做有一个巨大的价值：

**所有资源调度、负载控制、权限、生命周期、可观测性，都可以集中在 Map Runtime。**

---

# 四、Map 不是简单的 Graph

这里建议进一步把术语区分清楚。

### Graph

描述：

> **能力之间有什么关系。**

### Map

描述：

> **在什么入口条件和运行规则下，如何根据请求沿 Graph 展开整个能力体系。**

因此：

```text
Capability Relationship Graph
              ↓
         Map Definition
              ↓
          Map Runtime
```

Map 是 Graph 的：

> **Executable Interpretation**

或者说：

> **Graph + Entry Contract + Expansion Policy + Resource Policy + Routing Policy + Lifecycle Policy**

共同构成 Map。

---

# 五、真正的运行过程是“地图展开”

你最后使用的“画卷徐徐展开”这个比喻非常准确。

假设一开始只有：

```text
                [Root Map]
```

来了一个请求：

```text
Request R
```

Map 首先检查 Root：

```text
Request
   ↓
Root Entry Condition
   ↓
满足
```

然后实例化第一级能力：

```text
                Root Map
                    │
          ┌─────────┼─────────┐
          ↓         ↓         ↓
        Cap A      Cap B      Cap C
```

继续运行过程中，A 发现需要 D：

```text
                    Root
                      │
          ┌───────────┼───────────┐
          ↓           ↓           ↓
        Cap A        Cap B       Cap C
          │
          ↓
        Cap D
```

D 又引用一个 Sub-Map：

```text
                    Root
                      │
                  ┌───┴───┐
                  ↓       ↓
                Cap A   Sub-Map B
                          │
                    ┌─────┼─────┐
                    ↓     ↓     ↓
                  Cap C Cap D Cap E
```

因此：

> **Map 不是一次性把整张图加载进来。**

而是：

> **随着请求的深入，逐节点、逐层、按需展开。**

---

# 六、所以 Capability 的实例化是 Lazy Materialization

你描述的实际上是一种：

> **Lazy Capability Materialization**

即：

```text
Capability Definition
        │
        │ dormant
        ▼
     No Instance
        │
        │ request arrives
        ▼
Entry Condition
        │
        │ satisfied
        ▼
Instantiate
        │
        ▼
Capability Instance
```

没有需求：

```text
Capability
    ↓
0 Instance
```

有需求：

```text
Capability
    ↓
1 Instance
```

压力变大：

```text
Capability
    ↓
N Instances
```

压力消失：

```text
Capability
    ↓
0 Instance
```

所以：

> **Capability 的默认状态应该是 Dormant，而不是 Running。**

这个原则非常重要。

---

# 七、而且“第一次调用”才真正触发资源绑定

能力定义本身：

```text
Capability
```

不绑定：

```text
CPU
Memory
GPU
Container
VM
```

只有第一次需要它：

```text
Request
   ↓
Capability Resolution
   ↓
Entry Condition
   ↓
Resource Planning
   ↓
Resource Allocation
   ↓
Runtime Instantiation
```

例如：

```text
ThreatDetect Capability

Required:
    CPU >= 2
    Memory >= 4GB
    GPU optional
```

第一次请求时：

```text
Resource Pool
      ↓
2 CPU
4GB Memory
      ↓
Process Instance
```

于是：

> **能力定义与资源实例实现彻底解耦。**

---

# 八、后续扩容不是重新实例化“能力”，而是扩展 Capability Instance Pool

假设：

```text
Cap B
```

第一次出现：

```text
B1
```

负载增加：

```text
B1 = 85%
```

Map Runtime 发现：

```text
Demand > Capacity
```

于是：

```text
B1
 ↓
Scale Out
 ↓
B2
B3
```

成为：

```text
Capability B Instance Pool

B1
B2
B3
```

这时上游不再直接调用某个 B。

而调用：

> **Capability B Pool**

然后 LB 根据：

* 当前负载
* 剩余容量
* 延迟
* 队列
* Resource Pressure
* locality
* affinity
* cost

进行分发。

---

# 九、所以 LB 其实属于 Map Runtime

这一点很重要。

不是：

```text
Capability
  └── LB
```

而应该是：

```text
Map Runtime
    │
    └── Capability Invocation Layer
            │
            └── LB
                  │
        ┌─────────┼─────────┐
        ↓         ↓         ↓
       B1        B2        B3
```

因为：

> **Capability 是静态定义，不应该知道自己当前有哪些实例。**

实例数量、实例位置和负载状态属于：

> **Runtime State。**

---

# 十、这样就形成非常清晰的控制闭环

```text
                Upstream Demand
                       │
                       ▼
                Map Runtime
                       │
                       ▼
               Capability Pool
                       │
                 ┌─────┴─────┐
                 ↓           ↓
               Load        Capacity
               Observe      Observe
                 │           │
                 └─────┬─────┘
                       ↓
                 LB / Scheduler
                       │
             ┌─────────┼─────────┐
             ↓         ↓         ↓
            B1        B2        B3
             │         │         │
             └─────────┼─────────┘
                       ↓
                Resource Demand
                       │
                       ▼
                Resource Pool
                       │
                       ▼
               New Instances
```

这已经是一个完整的：

> **Demand → Capacity → Scaling → Routing → Execution**

闭环。

---

# 十一、最关键的是“向下游传导需求”

你提出：

> 将负载需求根据 LB 算法分发给下游能力实例。

还可以再进一步。

实际上每一级 Map 都应该把需求向下传播：

```text
Root Demand
     ↓
Capability A Demand
     ↓
Capability B Demand
     ↓
Capability C Demand
```

例如：

```text
Root = 10,000 req/s
        ↓
A = 10,000 req/s
        ↓
B = 7,000 req/s
        ↓
C = 7,000 req/s
```

但是如果存在：

```text
A
├── B 70%
└── C 30%
```

那么：

```text
10,000
 ↓
B = 7,000
C = 3,000
```

因此 Graph Runtime 实际上在做：

> **Demand Propagation**

---

# 十二、这意味着 Map 是一个“需求传播网络”

整个体系可以理解为：

```text
              External Demand
                     │
                     ▼
                  Root Map
                     │
            ┌────────┼────────┐
            ↓        ↓        ↓
           A         B        C
         Demand    Demand    Demand
            │
            ▼
         Sub-Map
            │
        ┌───┼───┐
        ↓   ↓   ↓
        D   E   F
```

需求从根向下传播。

资源则从底层向上提供 Capacity：

```text
Resource Capacity
        ↑
        │
 Runtime Capacity
        ↑
 Capability Capacity
        ↑
       Map Capacity
```

最终形成一个非常漂亮的：

> **Demand Down / Capacity Up**

双向控制模型。

---

# 十三、于是“整张地图徐徐展开”实际上有严格的技术含义

你这个比喻可以正式化为：

### Map Expansion

```text
Root
 │
 ├─ A
 │   ├─ D
 │   └─ E
 │
 └─ B
     └─ F
```

不一开始实例化所有节点，而是：

```text
T0
Root Instance

T1
Root
 ├── A1
 └── B1

T2
Root
 ├── A1
 │   ├── D1
 │   └── E1
 └── B1
      └── F1

T3
A → A1,A2,A3
D → D1,D2
F → F1,F2,F3
```

也就是说：

> **Graph Definition 永远完整存在，而 Runtime Graph Instance 是逐渐展开的。**

这句话应该成为架构中的核心定义。

---

# 十四、然后是你提出的“需求消失后回收”

这实际上对应：

> **Reverse Unfolding**

展开：

```text
Dormant
 ↓
A
 ↓
A + B
 ↓
A + B + C
 ↓
A + B + C + D
```

回收：

```text
A + B + C + D
 ↓
A + B + C
 ↓
A + B
 ↓
A
 ↓
Dormant
```

而且回收也应该沿反向依赖传播。

例如：

```text
Root
 └── A
      └── B
           └── C
```

如果 C 长时间无需求：

```text
C → Scale to Zero
```

如果 B 因 C 释放而没有其他需求：

```text
B → Scale to Zero
```

最终：

```text
A → Scale to Zero
```

形成：

> **Demand-driven Lifecycle Propagation**

---

# 十五、这里必须加入“生命周期滞后”，否则会抖动

实际工程中不能：

```text
有一个请求 → 创建
请求结束 → 销毁
有一个请求 → 创建
请求结束 → 销毁
```

否则会产生：

> Thrashing。

所以 Capability Instance 应有生命周期状态：

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

并设置：

* Scale-out threshold
* Scale-in threshold
* Warm time
* Idle timeout
* Cooldown
* Minimum warm instances
* Maximum instances

这样才能真正实现：

> **按需，但不是抖动式按需。**

---

# 十六、现在整个架构可以正式定义为

# Capability Map Runtime

```text
                        EXTERNAL REQUEST
                               │
                               ▼
                     ┌──────────────────┐
                     │   MAP INSTANCE   │
                     │  External Entry  │
                     └────────┬─────────┘
                              │
                              ▼
                    Graph Expansion Engine
                              │
                 ┌────────────┼────────────┐
                 ↓            ↓            ↓
            Capability A   Capability B  Sub-Map C
                 │            │            │
                 └────────────┼────────────┘
                              │
                     Demand Propagation
                              │
                              ▼
                     Capacity-aware LB
                              │
                              ▼
                  Capability Instance Pool
                              │
                  ┌───────────┼───────────┐
                  ↓           ↓           ↓
                 I1          I2          I3
                  │           │           │
                  └───────────┼───────────┘
                              │
                        Resource Demand
                              │
                              ▼
                       Resource Scheduler
                              │
                              ▼
                         Resource Pool
```

旁边再有一个控制闭环：

```text
Load / Capacity
      ↓
Scale Controller
      ↓
Instance Lifecycle
      ↓
Runtime Pool
      ↓
Load / Capacity
```

---

# 十七、我认为你现在的模型可以提炼成七条“不变量”

### 不变量 1：Capability Dormancy

> **Capability 默认不运行、不占用运行资源。**

### 不变量 2：Independent Execution

> **任何 Capability 都具备独立实例化和执行能力。**

### 不变量 3：Map-only Invocation

> **外部调用只能进入 Map，Capability 不直接暴露为外部服务。**

### 不变量 4：Lazy Expansion

> **Map 仅在需求触达并满足入口条件时，按需向下展开。**

### 不变量 5：Demand-driven Scaling

> **Capability Instance 数量由上游实际需求驱动。**

### 不变量 6：Capacity-aware Routing

> **负载分发必须基于下游实例实际 Capacity，而不是简单轮询。**

### 不变量 7：Reverse Reclamation

> **长期无需求时，Map 沿依赖关系反向收缩并回收 Runtime 与 Resource。**

这七个不变量已经足以形成一个独立的平台架构思想。

---

# 十八、最后，“地图”和“画卷”这个比喻其实非常好

我甚至建议保留。

可以定义：

> **Capability Map 是完整的能力地图。**

> **Map Definition 是完整但静态的地图。**

> **Map Instance 是一次业务请求正在展开的地图。**

> **Capability Instance 是地图中被点亮的节点。**

> **Resource Allocation 是节点获得的生产资料。**

> **Execution 是地图正在发生的动作。**

> **Scale-out 是地图向下展开。**

> **Scale-in 是地图向上收拢。**

于是整个系统可以用一句非常形象、同时又符合工程实现的话描述：

> **地图本身完整存在，但不会一次性展开；请求从地图入口进入，沿关系图按需触发能力，能力在第一次被触达时才实例化，并依据持续的上游需求动态扩缩容；需求继续向下游传播，地图便不断向下展开，逐渐形成完整的运行时画卷；当需求消失，地图再沿依赖关系逐层收拢，最终释放不再需要的能力实例与资源。**

我认为到这里，原来的“**资源池化，能力原子化**”已经自然演进成了一个更完整的理论：

> **资源池化，能力原子化；地图化组织，按需实例化；需求向下传播，容量向上反馈；运行时动态展开，需求消失反向收拢。**

这比传统的 **Service Mesh / Microservice / Serverless / Kubernetes** 更进一步：它把**“是否运行、在哪里运行、运行多少份、如何组合、何时释放”**都从预先部署阶段推迟到了 **Runtime Demand** 阶段。
