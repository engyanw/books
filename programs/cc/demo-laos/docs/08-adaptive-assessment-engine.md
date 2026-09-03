# 08 Adaptive Assessment Engine Technical Design V1.0

> 对应任务 #8（设计文档06）。定义自适应测评引擎：信息增益选题、多约束优化、终止规则、诊断探针与曝光权衡。第一阶段做确定性 Adaptive Engine，不做复杂 Agent。

## 1. 测评目标

不是"尽量少做题"，而是：

> 在满足测量精度的前提下，用尽可能少的有效证据降低关键状态的不确定性。

优化目标：

```
max  Expected Information Gain / Measurement Cost
```

## 2. 确定性 Adaptive Engine 流程

```
当前状态
 ↓
候选题集合
 ↓
过滤（约束）
 ↓
计算 Information Gain
 ↓
选择下一题
 ↓
获得 Evidence
 ↓
更新状态
 ↓
继续 / 终止
```

## 3. Information Gain

核心：下一道题应最大程度减少当前认知状态的不确定性。

```
EIG(item) = H(State) - E[H(State | Response)]
```

- `H(State)`：当前状态熵（不确定性）。
- `E[H(State | Response)]`：预期作答后剩余熵。

选 EIG/成本 最大者。

## 4. 多约束优化

```
Maximize: Information Gain

Subject To:
├─ 内容覆盖
├─ 难度约束
├─ 题型约束
├─ 曝光约束
├─ 测试长度
├─ 学生疲劳
├─ Q-matrix 可识别性
└─ 高考蓝图约束
```

### 4.1 算法（V2.2 §12.2）

- 带约束的贪心 + 事后平衡（Weighted Deviation Balancing / 旋转约束法），或内容平衡的 Shadow-test，保证实时性。
- 曝光控制：Sympson-Hetter 类，上限阈值基于真实考生流量标定。
- 曝光 vs 信息量冲突，离线刻画"信息量—曝光上限"帕累托前沿供运营选择。

### 4.2 状态快照

- 单次测评内用 **t-1 冻结状态**选题与估计，t 时刻批量写入新证据后更新状态，避免同流污染（V2.2 §12.2）。

## 5. 终止规则

满足任一即停：

- 关键状态不确定性低于阈值（后验方差 < τ）。
- 信息增益边际递减（ΔEIG < ε）。
- 测量安全上限（最大题量 / 最大时长）。
- 内容覆盖达成。

> 阈值属待校准参数（V2.2 §5.1），非理论常数。

## 6. 诊断探针（V2.2 §14）

```
Recall Probe      → 是否知道
 ↓
Discrimination Probe → 相似情境能否区分
 ↓
Explanation Probe  → 是否理解规则/原因
```

区分：

```
不知道 → 知道但不会用 → 会用但不稳定 → 常规情境会用 → 陌生情境能迁移
```

- Probe 属诊断证据，不混入正式考试分数，不直接用于最终等级判定，用于解释"为什么错"。
- 探针自身须有信效度。

## 7. 引擎接口

| 接口 | 说明 |
| --- | --- |
| `startSession(student_id, goal)` | 初始化测评 |
| `selectNextItem(state, constraints)` | 选题 |
| `submitResponse(item_id, response)` | 提交作答 |
| `shouldStop(session)` | 终止判定 |
| `getProbe(student_id, node_id, level)` | 触发探针 |

## 8. 与诊断引擎协作

- 选题读取 `getState`（只读）。
- 作答写入 Evidence → 触发 `updateState`（Assessment Engine）。
- 探针结果进 Evidence（level D）。

## 9. 验收

- [ ] EIG 计算正确，选题优先高信息增益。
- [ ] 多约束生效，含曝光/Q 矩阵可识别性/高考蓝图。
- [ ] 终止规则多因素触发。
- [ ] 单次测评状态快照隔离生效。
- [ ] 三级探针可触发且与正式分数隔离。
- [ ] 实时性满足（单题选题延迟有上界）。
