# 07 Cognitive Diagnosis Engine Technical Design V1.0

> 对应任务 #7（设计文档05）。定义认知诊断引擎的算法层：DINA/GDINA、IRT、层级测量模型、概率更新与状态融合范式。LLM 不在本核心链路。

## 1. 职责边界

引擎负责：设计测量 → 获取证据 → 更新状态 → 估计不确定性 → 生成评价结果。

不负责：生成学习讲义、自由生成学习路径、修改评价标准。

> LLM 位于内容编排与解释层，不位于测量核心链路（V2.2 §三）。

## 2. 模型职责划分（解耦）

| 模型 | 职责 | 输出 |
| --- | --- | --- |
| DINA/GDINA | 技能组合归因、属性掌握 | P(Mastery \| Evidence) |
| IRT | 总体/领域能力、题目参数、尺度校准 | 多领域 θ + 信息量 |
| 知识追踪(KT) | 状态随证据变化的追踪 | 转移概率 |
| 遗忘模型 | 长期保持与复习风险 | forgetting_risk |
| 探针模型 | 错误原因诊断证据 | 错误归因证据 |
| 迁移模型 | 跨情境迁移判断 | transfer 证据 |

> 各模型只产生证据，通过统一状态层融合，不直接互改内部参数（V2.2 §2.4）。

## 3. DINA / GDINA（V2.2 §13.1）

- 第一阶段：DINA/GDINA，用于知识掌握诊断、属性掌握概率、Q 矩阵诊断。
- **连续化**：经典 DINA 潜变量二元，颗粒度有限；对需"部分掌握"细粒度节点用 GDINA / p-DINA，以后验 P(Mastery | Evidence) 作为证据进入状态层。
- 不做"做对一题 → mastery+0.1"的规则加减分：

```
Evidence → Likelihood → Posterior → P(Mastery | Evidence)
```

### DINA 模型核心

```
P(X=1 | α) = g_j + (1 - s_j - g_j) * ∏_{k∈Qj} α_k
```

- `s_j`：slip（会但错）
- `g_j`：guess（不会但对）
- `α_k`：技能掌握（二元，连续化为后验概率）
- 依赖 Q 矩阵（见 `06-item-and-qmatrix-spec.md`）。

> DINA 有效性高度依赖 Q 矩阵质量。误标 → 系统性偏误。

## 4. IRT（V2.2 §13.2）

- 负责：总体能力、领域能力（θ_language / θ_reading / θ_classical）、题目参数、测试信息量、锚定。
- 动态 IRT 处理能力随时间变化。
- **适用边界**：单维 + 局部独立，主要适用客观题。主观题用 MIRT 或分层 rater model，IRT 参数不吸收评分者偏差。
- 不修改知识图谱权重，通过 Evidence Layer 融合。

### 2PL 模型示例

```
P(X=1 | θ) = c_j + (1 - c_j) / (1 + exp(-a_j(θ - b_j)))
```

## 5. 层级测量模型

```
Core Literacy Ability
        ↓
Task Ability
        ↓
Cognitive Process
        ↓
Knowledge Mastery
        ↓
Item Response
```

形成 Hierarchical Cognitive Measurement Model——未来最值得投入的算法方向。

## 6. 概率更新机制

```
New Evidence
      ↓
Likelihood
      ↓
Posterior Update
      ↓
Student State
      ↓
Uncertainty Update
```

而非规则加减分。

## 7. 状态融合范式（V2.2 §9.5）

各模型以不同似然项贡献后验：

```
统一学生认知状态（隐变量 θ_{s,k}）
        ↑（后验推断）
   ┌────┴────┬─────────┬──────────┬─────────┐
DINA 似然  IRT 似然  KT 转移  遗忘先验  探针/迁移证据
```

约定：

- 分层贝叶斯融合；经验贝叶斯群体先验收缩缓解稀疏过拟合。
- 冲突证据不强行仲裁，以后验多峰/低置信保留，落入"证据不足"通道。
- 输出后验均值 + 方差 + 有效样本量 + 各模型贡献权重（可反解）。

> 备选范式（未采纳为主）：Dempster-Shafer、学习型集成。

## 8. 可识别性与冷启动（V2.2 §9.6）

- 每模型定义最小独立证据数与情境覆盖门槛，未达只输出"暂不可归因"。
- 新题先进预测试池（calibration pool），估计参数、过拟合检验后上线。
- 冷启动期状态自带宽置信区间，决策引擎优先探查而非贪心干预。

## 9. 引擎接口

| 接口 | 说明 |
| --- | --- |
| `ingestEvidence(evidence_batch)` | 写入证据（仅 Assessment Engine 可调） |
| `updateState(student_id, node_id)` | 触发后验更新 |
| `getState(student_id, node_id)` | 读状态（Agent 可读） |
| `getProvenance(state_id)` | 反查证据链 |
| `calibrate(items, responses)` | 题目参数/Q 矩阵校准 |

## 10. 验收

- [ ] DINA/GDINA 输出 P(Mastery | Evidence)，无规则加减分。
- [ ] IRT 适用边界逐题生效，主观题不套单维 IRT。
- [ ] 层级测量模型可自顶向下解释。
- [ ] 融合输出含后验均值/方差/有效样本量/模型贡献权重，可反解。
- [ ] 可识别性门槛生效，冷启动不输出精确数字。
- [ ] 写权限仅 Assessment Engine。
