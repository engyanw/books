# 09 Learning Decision & AI Tutor Technical Design V1.0

> 对应任务 #9（设计文档07）。定义学习决策引擎、学习动作效用模型与 AI Tutor 权限边界。LLM 负责解释与编排，不负责核心评价与决策。

## 1. 学习决策引擎

输入：

```
Student State + Learning Goal + Available Time + Item Pool + Content Resources
```

输出：

```
Next Learning Action
```

示例：

```
优先修复：虚词"以"的语境辨析
原因：Mastery=0.72 Application=0.48 Transfer=0.31 Uncertainty=0.18
预计收益：High
建议：解释 → 对比例题 → 迁移题
```

## 2. 候选学习动作

```
知识讲解 / 例题学习 / 基础训练 / 应用训练 / 迁移训练
错题重做 / 间隔复习 / 综合训练
```

## 3. 学习动作效用模型（V2.2 §19）

```
Utility(a | s) =
  (ExpectedGain(a|s) × Priority(a) × TransferValue(a))
  / LearningCost(a)
```

- `s`：学生当前状态
- `a`：候选学习动作
- ExpectedGain：预计状态增益（由历史干预效果模型预测）
- Priority：课程/考试目标优先级
- TransferValue：对迁移能力的贡献
- LearningCost：预计时间与认知成本

### 3.1 探索项（V2.2 §19 补充）

乘积式为纯贪心 exploitation，与"局部最优"风险冲突。实际选择用多臂老虎机框架：

- 动作得分取后效用的置信上界（UCB）或 Thompson sampling 后验上界。
- 使"低置信度但潜在高增益"动作以一定概率被探索，而非永远选当前最高效用。
- ExpectedGain 须给估计方法与方差，不可空置。
- 各因子标准化或对数线性化，避免量纲不一导致某极端项主导。

## 4. 学习路径生成

路径是动态策略，非固定树：

```
虚词知识掌握不足
 → 基础概念 → 典型语境 → 对比辨析 → 常规应用 → 陌生文本 → 迁移验证
```

- 已稳定掌握则跳过重复训练。
- 陌生文本持续失败 → 迁移训练 → 诊断原因 → 判断是否基础问题 → 必要时返回基础层。

## 5. 熔断机制（V2.2 §23）

多因素触发降维，非机械"失败 2 次降级"：

```
状态低置信度 + 多个独立证据失败 + 错误模式高度一致 + 连续干预增益不足
```

三级干预：

- 一级：降低任务复杂度
- 二级：更换教学策略
- 三级：教师人工介入

## 6. AI Tutor 职责

Agent 负责：

```
知识检索 / 内容组织 / 解释 / 举例 / 反例
生成练习 / 生成微课 / 对话 / 学习提醒
```

不负责：

```
修改 Mastery / 修改 Threshold / 决定最终成绩 / 修改标准 / 决定学生是否达标
```

## 7. 技术隔离（权限边界）

不只靠 Prompt 约束，建 Agent API：

```
Agent API
    ↓
Read Student State（只读）
    ↓
Read Knowledge（只读）
    ↓
Generate Learning Action
    ↓
Submit Action
```

写权限属 Assessment Engine：

```
Update Student State / Update Assessment Standard / Update Threshold → 仅 Assessment Engine
```

> Agent 没有写权限（V2.2 §20）。

## 8. LLM 内容治理（V2.2 §21）

```
检索 → 证据筛选 → 内容生成 → 主张检查 → 规则验证 → 输出
```

- 知识性内容绑定来源/教材章节/知识节点/适用范围。
- Claim Verification 落地为具体模型（NLI / 事实核验），含冲突处置与"放弃生成"选项。
- 讲解内容与知识节点双向绑定，讲解错误可追溯到节点版本。
- LLM 离线质量门：事实性抽检通过率未达阈值的版本不进学习闭环。
- 承认 LLM 间接影响测量，不因"不在核心链路"放松质量门。

## 9. 接口

| 接口 | 权限 | 说明 |
| --- | --- | --- |
| `readState(student_id)` | 只读 | Agent 可读 |
| `readKnowledge(node_id)` | 只读 | Agent 可读 |
| `generateAction(state, goal)` | — | 决策引擎产出动作 |
| `submitAction(action)` | — | 提交学习动作 |
| `updateState(...)` | 写 | **仅 Assessment Engine** |

## 10. 验收

- [ ] 效用模型含探索项（UCB/Thompson），非纯贪心。
- [ ] 路径动态生成，非固定树。
- [ ] 熔断多因素触发，含三级干预。
- [ ] Agent 无写权限，写权限隔离生效。
- [ ] LLM 内容治理含 Claim Verification 与离线质量门。
