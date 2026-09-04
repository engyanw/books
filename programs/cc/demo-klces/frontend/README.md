# 高中语文知识学习在线评价系统（学生端）   Knowledge learning completeness evaluation system 知识学习完备度评价系统


基于 `frontend-design.md` 设计文档实现的移动端 H5 应用，打通「诊断—画像—处方—训练—复测」核心闭环，含学生端 9 个核心页面 + Node/Express 后端 API。

## 技术栈

- **前端**：React 18 + Vite + TypeScript + Tailwind CSS + React Router + Recharts + Axios
- **后端**：Node + Express + TypeScript（`tsx` 运行），JSON 内存态 mock 数据 + 简化自适应出题引擎

## 目录结构

```
klces/
├── backend/            Express REST API
│   ├── src/
│   │   ├── data.ts      种子数据 + 数据模型 + 报告/学习内容生成
│   │   ├── schools.ts   学校/年级/班级 实体 + 种子
│   │   ├── scopes.ts    四层继承知识图谱/题库引擎（系统→学校→年级→班级）
│   │   ├── auth.ts      用户/角色/鉴权
│   │   └── server.ts    路由 + 自适应 session 引擎
│   └── package.json
├── frontend/           React SPA
│   ├── src/
│   │   ├── api/         axios 客户端 + useGet/usePost hooks
│   │   ├── components/  Layout/TopNav/BottomTab/Card/Sheet/Confirm 等通用组件
│   │   ├── pages/       学生端 + 教师端 + 学校/年级/管理后台页面
│   │   ├── lib/         掌握度颜色/标签工具
│   │   └── App.tsx      路由表
│   └── package.json
└── frontend-design.md
```

## 启动

需要两个终端：

```bash
# 1) 启动后端（:3001）
cd backend
npm install
npm run dev

# 2) 启动前端（:5173，代理 /api → :3001）
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 即可体验。

## 9 个核心页面

| # | 页面 | 路由 | 底部Tab |
|---|------|------|---------|
| 1 | 首页（学习总门户） | `/` | 首页 |
| 2 | 测评中心-测评分类广场 | `/assess` | 测评 |
| 3 | 测评中心-答题页 | `/assess/answer/:sid` | — |
| 4 | 测评中心-测评报告页 | `/report/:id` | — |
| 5 | 知识画像-知识图谱热力图 | `/knowledge` | — |
| 6 | 学习中心-我的提升方案 | `/plan` | 学习 |
| 7 | 学习中心-知识点学习页 | `/study/:kpId` | — |
| 8 | 错题本-错题详情页 | `/errors/:id` | — |
| 9 | 成长中心-成长概览页 | `/growth` | 我的 |

错题本列表页路由 `/errors`（错题 Tab）。

## 教师端（3 页，桌面布局）

| 页面 | 路由 |
|------|------|
| 班级学情总览页 | `/teacher` |
| 班级测评管理页 | `/teacher/assessments` |
| 学生个人学情页 | `/teacher/student/:id` |

教师端为桌面端布局（左侧目录 + 主内容区），含班级切换、水平分布、共性短板榜、学生列表、发布测评、成绩分布与正确率分析、学生知识图谱/成长曲线/错题记录、教师备注（保存后同步至学生端）。

## 管理后台（2 页，桌面布局）

| 页面 | 路由 |
|------|------|
| 知识图谱管理页 | `/admin/knowledge` |
| 题库管理页 | `/admin/questions` |

- 知识图谱管理：左侧知识目录树（模块→单元→知识点，支持新增/删除），右侧编辑属性（名称、掌握度、考频、前置知识点），支持批量导入，修改实时同步至前端。
- 题库管理：顶部多维度筛选（模块/题型/难度）+ 试题列表 + 右侧单题编辑（题干、选项、答案、解析、知识点标签、难度标签），支持批量导入、上下架。

## 学校 / 年级管理员 与 继承式知识图谱题库

在「三权分立」管理员与学生/教师之上，新增**学校管理员 (schooladmin)** 与**年级管理员 (gradeadmin)** 两个可页面注册的角色，建立**逐级授权链**与**四层继承式知识图谱/题库**。

### 授权链

```
bizadmin 授权 → schooladmin 可登录
schooladmin 授权并分配年级/班级 → gradeadmin / teacher / student 可登录
```

学校体系内角色注册后一律 `pending`，必须由上一级授权（置 active + 分配范围）后方可登录。schooladmin 注册时录入新学校名（学校也 pending，随授权一起激活）；gradeadmin/teacher/student 注册时**选择**（而非录入）已存在学校，学生还需级联选择年级→班级。

### 四层继承模型

`系统 → 学校 → 年级 → 班级`，每层（除系统层外）持有 `ScopeContent`：

- `extraKps` / `extraQuestions`：本层新增项
- `kpOverrides` / `qOverrides`：对继承项的属性覆盖
- `hiddenKpIds` / `hiddenQIds`：本层隐藏的继承项（可恢复）
- `syncMode`：`auto`（实时继承上游变化）| `manual`（冻结于上次同步快照，点「立即刷新」拉取最新）

有效集 = 上游有效集 → 应用覆盖 → 过滤隐藏 → 追加本层新增。学生端 `/api/knowledge-graph` 与出题引擎自动使用其所属班级的有效链，让继承真正可见。bizadmin 维护系统层（即既有 `/api/admin/*` 端点，不变）。

### 演示账号（默认密码 `123456`）

- 学校管理员 `schooladmin`（种子：示范中学）
- 年级管理员 `gradeadmin`（种子：高二）
- 学生 `student` / 教师 `teacher`（已绑定示范中学高二班级）

### 学校管理端（桌面布局，需 `schooladmin`）

| 页面 | 路由 |
|------|------|
| 学校概览 | `/school` |
| 用户与授权 | `/school/users` |
| 年级/班级管理 | `/school/structure` |
| 学校知识图谱 | `/school/knowledge` |
| 学校题库 | `/school/questions` |

### 年级管理端（需 `gradeadmin`）

| 页面 | 路由 |
|------|------|
| 年级概览 | `/grade` |
| 年级知识图谱 | `/grade/knowledge` |
| 年级题库 | `/grade/questions` |

### 学校 / 年级 / 班级 API

- 公开下拉：`GET /api/schools`、`/schools/:id/grades`、`/schools/:id/grades/:gid/classes`
- bizadmin 审 schooladmin：`GET /api/biz/pending-school-admins`、`PATCH /api/biz/school-admins/:id/approve`
- schooladmin 本校：`GET/POST/PATCH/DELETE /api/school/grades[/:id]`、`/school/classes[/:id]`、`GET /school/users`、`/school/pending`、`PATCH /school/users/:id/approve`（body 按角色携 `gradeIds`/`classIds`/`classId`+`studentNo`）、`/school/users/:id/status`、`/school/users/:id/reset-password`、`DELETE /school/users/:id`、`GET /school/dashboard`
- gradeadmin：`GET /api/grade/overview`、`/grade/classes`、`/grade/users`
- 通用 scope 内容（`scope` ∈ school/grade/class）：`GET /api/scope/:scope/:id/knowledge-tree`、`POST/PUT/DELETE /scope/:scope/:id/knowledge-points[/:id]`、`PATCH /scope/:scope/:id/knowledge-points/:id/restore`、`GET/POST/PUT/DELETE /scope/:scope/:id/questions[/:id]`、`GET/PATCH /scope/:scope/:id/sync`、`POST /scope/:scope/:id/refresh`
- teacher 班级内容入口 `/teacher/knowledge`（选班级 → 班级层 scope）

所有写操作记入审计（`scope_content` / `school_approve` / `school_authorize` / `lifecycle` 等）。跨范围访问返回 403（如 gradeadmin 访问 school scope）。

## 主要 API

- `GET /api/profile` `/today-task` `/todos` `/bits` —— 首页
- `GET /api/assessments` `/assessments/units` `/assessments/stages` `/assessments/history`
- `POST /api/assessments/sessions`、`GET/POST /api/sessions/:id`、`POST /api/sessions/:id/submit` —— 自适应答题
- `GET /api/reports/:id` —— 报告 4 Tab 数据
- `GET /api/knowledge-graph` `/knowledge-graph/radar`、`/knowledge-points/:id`、`/knowledge-points/:id/study`、`POST /knowledge-points/:id/train`
- `GET /api/plan/current` `/plan/tasks` `/plan/stages/:id`
- `GET /api/errors` `/errors/:id`、`POST /errors/:id/rework`、`GET /errors/:id/variants`
- `GET /api/growth?range=week|month|semester`、`POST /api/growth/goal`

### 教师端 / 管理后台 API
- `GET /api/teacher/classes`、`/teacher/classes/:id`、`POST /teacher/assessments`、`GET /teacher/assessments[?status=ongoing|done]`、`/teacher/assessments/:id`
- `GET /api/teacher/students/:id`、`POST /teacher/students/:id/note`
- `GET /api/admin/knowledge-tree`、`POST /api/admin/knowledge-points`、`PUT/DELETE /api/admin/knowledge-points/:id`
- `GET /api/admin/questions[?moduleId=&type=&difficulty=]`、`POST /api/admin/questions`、`PUT/DELETE /api/admin/questions/:id`

## 账号与鉴权系统

支持学生 / 教师自主注册与登录，账号生命周期管理，以及「三权分立」内置管理员体系。

### 内置管理员（默认密码 `admin123`）

| 账号 | 角色 | 职责 |
|------|------|------|
| `bizadmin` | 业务管理员 | 知识图谱与题库等业务内容管理（不涉账户/角色/审计） |
| `sysadmin` | 系统管理员 | 用户生命周期：审批/启用/停用/注销/重置密码 |
| `secadmin` | 安全管理员 | 角色与权限分配、安全策略（注册审批、密码长度等） |
| `audadmin` | 审计管理员 | 审计日志只读查阅 |

业务管理由业务管理员专职负责，系统/安全/审计管理员不再处理业务内容，各司其职、相互制约：系统管理员不可越权改角色与策略，安全管理员不可越权管生命周期与业务，业务管理员不可越权管账户/角色/审计，审计管理员只读；内置管理员不可删除、角色不可变更；任何管理员不可对自身执行停用/删除。系统管理员的审计查阅仅限与本账号相关记录，保证审计独立性。

### 演示账号（默认密码 `123456`）

- 学生 `student` / 教师 `teacher`

### 鉴权 API

- `POST /api/auth/register` 学生/教师/学校管理员/年级管理员自助注册（学校体系内角色一律返回 pending，需逐级授权）
- `POST /api/auth/login` 登录（校验状态、签发 Bearer token）
- `GET /api/auth/me` 当前用户（token 恢复）
- `POST /api/auth/change-password` 修改密码
- `GET /api/users` 用户列表（sysadmin/audadmin）
- `PATCH /api/users/:id/status` 启用/停用/注销（sysadmin）
- `POST /api/users/:id/reset-password` 重置密码（sysadmin）
- `DELETE /api/users/:id` 删除用户（sysadmin，内置不可删）
- `PATCH /api/users/:id/role` 角色变更（secadmin）
- `GET/PATCH /api/security/policy` 安全策略（secadmin）
- `GET /api/audit-logs` 审计日志（audadmin 全量 / sysadmin 仅自身）

业务内容管理 API（均需 `bizadmin`）：

- `GET /api/admin/knowledge-tree`、`POST/PUT/DELETE /api/admin/knowledge-points[/:id]`
- `GET/POST/PUT/DELETE /api/admin/questions[/:id]`（增删改记入审计 `business`）

### 前端路由

- `/login` 登录、`/register` 注册、`/account` 账号设置（改密）— 全角色通用
- 学生端页面需登录（`RequireAuth`）
- 教师端 `/teacher/*` 需 `teacher` 角色（含 `/teacher/knowledge` 班级内容层）
- `/school/*` 需 `schooladmin`、`/grade/*` 需 `gradeadmin`、`/admin/school-approvals` 需 `bizadmin`
- `/admin/users` 需 `sysadmin`、`/admin/roles` 需 `secadmin`、`/admin/audit` 需 `audadmin`、`/admin/knowledge` 与 `/admin/questions` 需 `bizadmin`（`RequireRole` 路由守卫）
- 桌面布局侧边栏按当前用户角色过滤可见导航，并提供账户菜单与退出登录

## 说明

- 数据为 mock 种子数据，后端重启即复位；不依赖任何数据库。账号同样为内存态，重启复位至种子账号。
- 自适应逻辑简化版：答对升难度、答错降难度并追溯，达题量上限结束。
- 图表统一使用 Recharts；学生端知识图谱为自定义交互式 SVG（缩放/拖拽/展开）。
- 学生端为移动端布局（max-w-md），教师端/管理后台为桌面端布局（左侧目录 + 主内容区），按路由自动切换。

## WSL 注意事项

在 WSL 下若 `/mnt/d`（Windows 挂载盘）安装依赖后运行报错 `esbuild ... installed for another platform (win32-x64, needs linux-x64)`，需补装 Linux 平台二进制：

```bash
cd backend && npm install @esbuild/linux-x64 --no-save
```

另：若默认 npm 镜像（`mirrors.tools.huawei.com`）出现 504 超时，改用 npmmirror：`npm install --registry=https://registry.npmmirror.com`。
