# -*- coding: utf-8 -*-
"""新用户示例文档：注册时在云端根目录创建 examples 文件夹并播种下列示例，
帮助新用户快速熟悉编辑器的各项特性。

每条示例的 content 即一份可渲染的 Markdown，覆盖一种特性。
新增示例只需在 EXAMPLES 列表里追加 {title, content} 项。
"""

EXAMPLES = [
    {
        "title": "01-快速开始.md",
        "content": """# 快速开始

欢迎！这份示例集合演示编辑器的常用特性。左侧为编辑区，右侧为实时预览。

## 基本操作

- **新建文档/文件夹**：点击侧边栏「新建文件 / 新建文件夹」按钮，名称在原位输入，回车确认；名称为空或冲突则自动取消。
- **保存**：本地文档点「保存」写回原文件；云端文档自动保存并同步。
- **打开**：单击文件列表中的文件即可打开；双击文件名可直接重命名。
- **切换视图**：工具栏可切换「编辑 / 预览 / 分屏」三种视图。
- **侧边栏**：可拖动边界调整宽度，点击「切换侧边栏」可完全收起。

## 帮助提示

> 鼠标悬停在按钮上会显示工具提示；右上角可切换主题、语言与 Vim 模式。

继续浏览 `examples` 文件夹中的其他示例，逐一了解每种特性。
""",
    },
    {
        "title": "02-Markdown基础.md",
        "content": """# Markdown 基础

## 文本格式

**加粗**、*斜体*、***粗斜体***、`行内代码`、~~删除线~~。

## 标题层级

支持一到六级标题，预览会自动生成目录（TOC）。

## 列表

无序列表：

- 第一项
- 第二项
  - 嵌套子项
  - 另一个子项

有序列表：

1. 步骤一
2. 步骤二
3. 步骤三

任务列表：

- [x] 已完成项
- [ ] 待办项
- [ ] 另一个待办

## 链接与图片

[链接文本](https://example.com) 指向外部网址。

## 引用与分割线

> 这是一段引用文字。
> 可以包含多行。

---

## 表格

| 名称 | 类型 | 说明 |
|---|---|---|
| 编辑器 | 工具 | 撰写 Markdown |
| 预览 | 视图 | 实时渲染 |
| 云端 | 存储 | 多端同步 |

## 脚注

正文里出现引用[^1]，文末给出释义。

[^1]: 这是一个脚注示例。
""",
    },
    {
        "title": "03-代码与图表.md",
        "content": """# 代码与图表

## 代码块（语法高亮）

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"

print(greet("World"))
```

```javascript
const sum = (a, b) => a + b;
console.log(sum(1, 2));
```

## Mermaid 流程图

```mermaid
flowchart LR
    A[开始] --> B{条件判断}
    B -- 是 --> C[执行分支 A]
    B -- 否 --> D[执行分支 B]
    C --> E[结束]
    D --> E
```

## ECharts 图表

```echarts
{
  "title": { "text": "示例柱状图" },
  "tooltip": {},
  "xAxis": { "data": ["一月", "二月", "三月", "四月"] },
  "yAxis": {},
  "series": [{ "name": "数量", "type": "bar", "data": [5, 20, 36, 10] }]
}
```

## PlantUML 时序图

```plantuml
@startuml
Alice -> Bob: 请求同步
Bob --> Alice: 返回结果
Alice -> Bob: 确认收到
@enduml
```

## Markmap 思维导图

```markmap
# 主题
## 分支一
### 子节点 A
### 子节点 B
## 分支二
### 子节点 C
```
""",
    },
    {
        "title": "04-数学公式.md",
        "content": """# 数学公式

编辑器使用 KaTeX 渲染数学公式。鼠标悬停在公式上可查看源码。

## 行内公式

质能方程 $E = mc^2$ 出现在文字行内；求和 $\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}$。

## 块级公式

$$
\\int_{0}^{\\infty} e^{-x^2} \\, dx = \\frac{\\sqrt{\\pi}}{2}
$$

## 矩阵

$$
A = \\begin{bmatrix}
a_{11} & a_{12} \\\\
a_{21} & a_{22}
\\end{bmatrix}
$$

## 多行推导

$$
\\begin{aligned}
(a + b)^2 &= (a+b)(a+b) \\\\
&= a^2 + 2ab + b^2
\\end{aligned}
$$
""",
    },
    {
        "title": "05-版本历史与分享.md",
        "content": """# 版本历史、批注与分享

## 版本历史

每次保存会生成一个版本快照，**按文档独立记录**。

- 打开「版本历史」面板可查看本文件的历史版本。
- 支持新旧版本差异对比，可切换「上下对比 / 左右对比」两种模式。
- 可将某个历史版本回退为当前内容。

> 跨文档不会互相干扰——历史快照始终归属于当前打开的文档。

## 文档批注

批注以右侧抽屉式面板展示，同样**按文档隔离**。

- 点击批注可快速定位到文档对应行。
- 双击批注可原地编辑。
- 添加批注时不弹框，直接在侧边栏生成一条可编辑记录，确认后保存。
- 批注按行号排序显示。

## 分享

- 点击「分享」生成分享码，可将只读链接发给他人访问。
- 支持设置访问密码、过期时间、最大访问次数、阅后即焚。
- 访客无需登录即可通过分享链接查看文档内容。

## 回收站

删除的文档进入回收站，可在回收站中恢复或彻底清除。
""",
    },
    {
        "title": "06-模板-RFC.md",
        "content": """# RFC: {{ title }}

- 作者：{{ author }}
- 日期：{{ date }}
- 状态：{{ status }}

## 摘要

{{ summary }}

## 动机

{{ motivation }}

## 设计方案

{{ design }}

## 风险与权衡

{{ risks }}

---

> 这是 RFC 场景模板的实例骨架。后端 `GET /api/templates/builtin` 提供同名模板，
> 可通过 `POST /api/templates/builtin/rfc/instantiate` 传入变量生成正式文档。
> `{{ 变量名 }}` 占位符由 Jinja2 渲染。
""",
    },
    {
        "title": "07-模板-设计文档.md",
        "content": """# 设计文档：{{ title }}

- 作者：{{ author }}
- 日期：{{ date }}
- 状态：{{ status }}

## 背景

{{ background }}

## 目标与非目标

### 目标
{{ goals }}

### 非目标
{{ non_goals }}

## 架构概述

{{ architecture }}

## 接口设计

{{ api }}

## 数据模型

{{ data_model }}

## 迁移与回滚

{{ migration }}
""",
    },
    {
        "title": "08-模板-运维手册.md",
        "content": """# Runbook：{{ title }}

- 负责人：{{ owner }}
- 严重级别：{{ severity }}

## 触发条件

{{ trigger }}

## 影响

{{ impact }}

## 诊断步骤

1. {{ step1 }}
2. {{ step2 }}
3. {{ step3 }}

## 恢复操作

{{ recovery }}

## 升级路径

{{ escalation }}

## 事后复盘

{{ postmortem }}
""",
    },
    {
        "title": "09-模板-ADR.md",
        "content": """# ADR-{{ number }}：{{ title }}

- 状态：{{ status }}
- 日期：{{ date }}
- 决策者：{{ deciders }}

## 背景

{{ context }}

## 决策

{{ decision }}

## 理由

{{ rationale }}

## 后果

### 正面影响
{{ consequences_positive }}

### 负面影响
{{ consequences_negative }}

## 备选方案

{{ alternatives }}
""",
    },
]
