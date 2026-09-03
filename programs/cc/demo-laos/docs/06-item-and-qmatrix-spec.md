# 06 Item & Q-Matrix Specification V1.0

> 对应任务 #6（设计文档04）。定义题目 Schema、Q 矩阵、题目质量模型、曝光控制与 IRT 适用边界。Q 矩阵是认知诊断链路的命门，治理优先级高于题目参数估计。

## 1. Item Schema

```yaml
Item:
  id: ITEM001
  version: V3
  source: 人教版·必修
  text: "..."                     # 文本材料
  question: "..."
  options: [A, B, C, D]
  answer: "B"
  score_rule: {type: binary}      # 或 rubric_id（主观题）

  knowledge_tags: [K-WW-FUNC-001]   # L1
  cognitive_tags: [UNDERSTAND, ANALYZE]  # L2
  capability_tags: [CA01]          # L3
  literacy_tags: [L01, L02]        # L4

  difficulty: 0.6
  discrimination: 0.4
  guessing: 0.25

  diagnostic_targets: ["语境辨析"]
  misconception_targets: ["义项混淆"]
  transfer_target: K-WW-FUNC-001

  exposure_count: 0
  leakage_risk: low

  q_matrix:
    - {knowledge: K-WW-FUNC-001, cognitive: UNDERSTAND, weight: 0.6}
    - {knowledge: K-WW-FUNC-001, cognitive: ANALYZE, weight: 0.4}

  irt_applicable: true            # V2.2 §13.2 适用边界
  item_type: objective            # objective | subjective
  audit_status: approved
```

## 2. Q-Matrix

每一道题不只标"知识点=虚词之"，而标四层 + 诊断目标 + Q 矩阵权重：

```
Item
 ↓ Knowledge（L1）
 ↓ Cognitive Process（L2）
 ↓ Task Capability（L3）
 ↓ Core Literacy（L4）
```

Q 矩阵列：知识/认知/任务/素养 + 主/次技能 + 置信度。

> 多技能题允许主技能与次技能；主观题技能归属常不唯一，Q 矩阵标注须附置信度，低置信题不作为 DINA 主证据。

## 3. 题目质量模型（12 项）

```
内容正确性 / 知识覆盖 / 认知层级 / 难度 / 区分度 / 猜测参数
干扰项质量 / 诊断信息量 / 歧义性 / 课标一致性 / 高考相关性 / 曝光风险
```

## 4. 人工标注体系（V2.2 §31.2/§31.3）

### 4.1 分层流水线

```
LLM 预标注 → 众教师标注 → 一致性筛选 → 专家抽检/复核 → 入库
```

- LLM 仅产出候选标注，不作真值。
- 一致性低 / 专家抽检未过 → 退回，不进诊断链路。
- 专家精力集中在：高分歧题 + 高价值节点 + 锚题。

### 4.2 标注内容

```
Knowledge / CognitiveProcess / Task / Literacy
Misconception / Q-matrix / Difficulty / DiagnosticTarget
```

### 4.3 一致性门槛

- 双人独立标注，专家仲裁。
- Cohen's κ / Krippendorff α **< 0.6 退回重标**。
- 标注质量（κ、抽检通过率）作为题库可上线硬门槛。

### 4.4 Q 矩阵验证

- 基于残差的 Q 矩阵验证（GDI / stepwise validation）检测误标。
- 与专家标注交叉校验。
- 题目修订时 Q 矩阵同步重标，旧诊断结果标注所用 Q 矩阵版本。

## 5. IRT 适用边界（V2.2 §13.2）

| 题型 | IRT 适用 | 说明 |
| --- | --- | --- |
| 字音字形/实词选择/文化常识 | 适用 | 单维、局部独立成立 |
| 文言文翻译（主观） | 不适用单维 IRT | 多维，用 MIRT 或分层 rater |
| 句意理解（主观） | 不适用 | 题间高相关 |

- 逐题标注 `irt_applicable`。
- 主观题用多维 IRT（MIRT）或将评分者作为随机效应的分层评分模型。
- IRT 题目参数不吸收评分者偏差。

## 6. 曝光控制

- `exposure_count` / `leakage_risk` 字段。
- Sympson-Hetter 类曝光控制，上限阈值基于真实考生流量标定。
- 曝光控制与信息量天然冲突，离线刻画"信息量—曝光上限"帕累托前沿供运营选择（V2.2 §12.2）。

## 7. 题目生命周期

```
命题 → 专家审核 → 试测 → IRT参数估计 → 认知诊断属性校准 → 上线 → 持续监控 → 异常检测 → 修订/下线
```

新题不直接进自适应链路，先在预测试池（calibration pool）通过拟合检验后上线（V2.2 §9.6）。

## 8. 验收

- [ ] Item Schema 含四层标签 + Q 矩阵 + 诊断目标 + IRT 适用标注。
- [ ] 12 项质量模型可计算。
- [ ] 双人标注 + κ 门槛生效，< 0.6 退回。
- [ ] Q 矩阵验证（GDI/stepwise）可运行。
- [ ] 曝光控制字段与阈值标定机制就绪。
- [ ] 题目生命周期含预测试池校验。
