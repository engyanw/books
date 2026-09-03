# 04 Student Cognitive State Schema V1.0

> 对应任务 #4（设计文档02）。定义统一学生认知状态模型的数据结构、四层状态、融合输出与可识别性约束。学生状态独立于知识图谱与题库存储。

## 1. 设计原则

原七维状态向量混合了"能力状态""统计不确定性""行为风险""错误分类"。V2.1/V2.2 将其拆为四层，避免把"迁移能力 0.41"与"置信度 0.84"当同性质指标。

## 2. 四层状态结构

```
Student Cognitive State
 ├── A 核心认知状态（Core）
 ├── B 动态状态（Dynamic）
 ├── C 诊断状态（Diagnostic）
 └── D 不确定性（Uncertainty）
```

### 2.1 A 核心认知状态

针对每个知识/任务节点维护：

| 字段 | 含义 | 范围 |
| --- | --- | --- |
| `mastery` | 知识掌握 | [0,1] |
| `application` | 常规应用 | [0,1] |
| `transfer` | 陌生情境迁移 | [0,1] |

### 2.2 B 动态状态

| 字段 | 含义 |
| --- | --- |
| `stability` | 跨证据/情境稳定性 |
| `forgetting_risk` | 长期保持/复习风险 |

### 2.3 C 诊断状态

| 字段 | 含义 |
| --- | --- |
| `error_distribution` | 错误模式分布（知识/过程/策略/执行/情境） |
| `misconception` | 主要 misconception 标签 |

### 2.4 D 不确定性

| 字段 | 含义 |
| --- | --- |
| `posterior_variance` | 后验方差 |
| `confidence` | 综合置信度 |
| `evidence_count` | 独立证据数 |
| `evidence_diversity` | 情境覆盖数 |
| `recency` | 最新证据时间衰减 |
| `effective_n` | 融合有效样本量 |

## 3. 状态对象 Schema

```yaml
StudentCognitiveState:
  student_id: S001
  node_id: K-WW-FUNC-001          # 知识/任务节点
  node_version: 1.0
  domain: classical_reading

  core:
    mastery: 0.78
    application: 0.63
    transfer: 0.41

  dynamic:
    stability: 0.72
    forgetting_risk: 0.24

  diagnostic:
    error_distribution:
      context_discrim: 0.60
      knowledge_confusion: 0.25
      execution: 0.15
    misconception: "语境辨析不足"

  uncertainty:
    posterior_variance: 0.03
    confidence: 0.84
    evidence_count: 8
    evidence_diversity: 4
    recency: 0.9
    effective_n: 6.2

  fusion:
    model_contributions:          # V2.2 §9.5 可反解约束
      dina: 0.35
      irt: 0.25
      kt: 0.20
      forgetting_prior: 0.10
      probe: 0.10
    posterior_mean: 0.63
    posterior_var: 0.03
    is_multimodal: false

  meta:
    state_version: SCS_1.0
    model_version: CDM_1.0
    qmatrix_version: QM_1.0
    standard_version: STD_1.0
    updated_at: 2026-09-02T10:00:00Z
```

## 4. 示例（文言虚词"以"）

```
能力状态：mastery=0.78 application=0.63 transfer=0.41
证据状态：evidence_count=8 diversity=4 stability=0.72 confidence=0.84
学习风险：forgetting_risk=0.24
主要错误：context_discrim=0.60 knowledge_confusion=0.25 execution=0.15
```

## 5. 可识别性与冷启动约束（V2.2 §9.6）

- 每个节点须满足**最小独立证据数与情境覆盖门槛**才可输出数值状态；未达门槛只输出 `status: "insufficient_evidence"`，不强行给值。
- 冷启动用群体先验收缩（empirical Bayes / hierarchical shrinkage），缩小方差。
- `effective_n` 低于阈值时，决策引擎优先选"高信息增益+低成本"探查动作而非贪心干预。
- 不可识别参数不得被包装成精确数字输出给前端。

## 6. 融合输出要求（V2.2 §9.5）

融合须输出**后验均值 + 方差 + 有效样本量 + 各模型贡献权重**，四者共同构成"状态+不确定性"，且可反解为"由哪些模型的哪些证据、以多大权重贡献"（满足证据可追溯）。

冲突证据不强行仲裁，以**后验多峰 / 低置信**形式保留，落入"证据不足"通道（见 `05-evidence-schema.md` §证据不足机制）。

## 7. 访问接口

| 接口 | 权限 | 说明 |
| --- | --- | --- |
| `getState(student_id, node_id)` | 只读 | Agent/Tutor 可读 |
| `updateState(evidence_batch)` | 写 | **仅 Assessment Engine 可写** |
| `getProvenance(state_id)` | 只读 | 反查证据链 |

> 写权限隔离：Agent 无写权限（V2.2 §20）。

## 8. 验收

- [ ] 四层状态字段完整，能力值与不确定性分离。
- [ ] 融合输出含后验均值/方差/有效样本量/模型贡献权重。
- [ ] 可识别性门槛生效，冷启动不输出精确数字。
- [ ] 写权限仅 Assessment Engine 持有。
- [ ] 节点状态可反查证据链。
