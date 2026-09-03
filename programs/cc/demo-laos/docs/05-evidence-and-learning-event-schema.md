# 05 Evidence & Learning Event Schema V1.0

> 对应任务 #5（设计文档03）。系统核心对象是 Evidence（非成绩）。定义证据对象、四层分层、Provenance 反查、证据不足机制与采集管道。

## 1. 设计原则

- 核心对象不是"成绩"，而是 **Evidence**。
- 任何认知状态结论必须能追溯到具体证据（V2.2 §2.2）。
- 证据分层，不同层级效力不同（V2.2 §15）。
- 证据不足时允许输出"证据不足 / 暂不可归因"，不强行生成结论。

## 2. Evidence 对象 Schema

```yaml
Evidence:
  id: E-000001
  student_id: S001
  item_id: ITEM001
  item_version: V3
  assessment_id: A001
  response: "B"
  score: 1
  response_time: 18.2
  hint_used: false
  attempt: 1
  rubric_version: R2
  model_version: CDM_1.0
  qmatrix_version: QM_1.0
  timestamp: 2026-09-02T10:00:00Z
  source: formal_assessment   # 来源类型，见 §4
  evidence_level: C           # 证据层级，见 §3
  provenance:                 # 反查链
    linked_state: SCS-S001-K-WW-FUNC-001
    weight: 0.18
```

## 3. 四层证据分层（V2.2 §15 证据等级）

| 层级 | 类型 | 作用 | source 值 |
| --- | --- | --- | --- |
| A | 标准化外部测试 | 能力锚定 | `external_anchor` |
| B | 独立新题 | 状态验证 | `independent_new` |
| C | 常规训练题 | 状态更新 | `formal_assessment` |
| D | 探针 | 原因诊断 | `probe` |
| E | 行为数据 | 辅助判断 | `behavior` |

> 连续做对同一道题不能等同于能力提升（曝光风险）。同题重复证据须降权。

## 4. 证据来源类型

```
direct_answer     直接答案
scored            评分
essay_text         作文文本
behavior          行为（答题时间/修改/跳过/提示/重复错误）
probe             探针（recall/discrimination/explanation）
transfer          迁移表现
external_anchor   外部锚题（标准化考试/学校考试/教师评价/人工评分）
teacher           教师证据
```

## 5. Evidence Provenance

每个认知状态须能回答："为什么系统认为这个学生掌握了这个知识？"

```
知识：之-宾前标志
Mastery = 0.81
证据：
 ├─ Item 102 正确  (level C, w=0.12)
 ├─ Item 109 正确  (level C, w=0.10)
 ├─ Item 115 错误  (level C, w=0.14)
 ├─ Probe 07 正确  (level D, w=0.20)
 ├─ Transfer 03 正确 (level B, w=0.25)
 └─ Anchor Test 02 正确 (level A, w=0.19)
```

`getProvenance(state_id)` 返回上述链，含证据层级与贡献权重。

## 6. 证据不足机制（V2.2 §17）

当系统无法区分"知识缺失 vs 方法错误"时，不强行二选一，输出：

```
主要假设：语境辨析能力不足（0.58）
备选假设：知识义项混淆（0.31）
证据不足：0.11
建议：增加 2~3 个独立情境证据
```

判定条件：`posterior_variance > threshold` 或 `effective_n < threshold` 或后验多峰。

## 7. 采集管道

```
作答事件 → 标准化 → 附元数据(版本号) → 证据层分级 → 入 Evidence Store → 触发后验更新
```

- 证据写入即附 `item_version / rubric_version / model_version / qmatrix_version`，保证可追溯。
- 行为证据需清洗（异常时间、复制粘贴等）。
- 探针证据与正式考试分数隔离，不进等级判定。

## 8. 存储与隐私（V2.2 §35 风险8）

- Evidence 默认去标识化，原始作答文本默认不长期留存。
- 每条证据含时间戳与来源，支持审计。
- 可删除权：学生退出/撤回同意时，关联证据按规约删除或脱敏。

## 9. 验收

- [ ] Evidence 对象含全部版本字段，可追溯。
- [ ] 四层分层生效，同题重复证据降权。
- [ ] Provenance 可反查任一状态的证据链与权重。
- [ ] 证据不足机制有判定与输出。
- [ ] 探针证据与正式分数隔离。
- [ ] 隐私合规（去标识化、可删除权）落实。
