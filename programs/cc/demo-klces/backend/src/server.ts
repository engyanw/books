import express from "express";
import type { Request, Response, NextFunction } from "express";
import cors from "cors";
import {
  modules, profile, todayTask, todos, bits, assessments, stages,
  assessmentHistory, questions, plan, errors, growth, buildReport,
  getStudy, allKp, classes, teacherAssessments, students, findStudent,
  type Question, type KnowledgePoint,
} from "./data.js";
import {
  hashPassword, verifyPassword, signToken, verifyToken,
  listUsers, findUser, findUserByName, saveUser, deleteUser, nextUserId,
  addLog, listLogs, getPolicy, setPolicy, seedAdmin, publicUser,
  ROLE_LABEL, STATUS_LABEL,
  type Role, type User, type UserStatus,
} from "./auth.js";
import {
  seedSchools, listSchools, listActiveSchools, findSchool, findSchoolByName,
  saveSchool, nextSchoolId,
  listGrades, findGrade, saveGrade, deleteGrade, nextGradeId,
  listClasses, findClass, saveClass, deleteClass, nextClassId,
  type School, type Grade, type Class,
} from "./schools.js";
import {
  getScope, effectiveKps, effectiveQuestions, refreshManual,
  addExtraKp, addExtraQuestion, patchExtraKp, patchExtraQuestion,
  removeKp, removeQuestion, restoreKp, restoreQuestion,
  kpOrigin, qOrigin, type ScopeLayer,
} from "./scopes.js";

const app = express();
app.use(cors());
app.use(express.json());

// ---------- 鉴权中间件 ----------
// 解析 Bearer token（可选，不强制），req.user 可能为 undefined
function authOptional(req: Request, _res: Response, next: NextFunction) {
  const h = req.headers.authorization || "";
  const m = h.match(/^Bearer (.+)$/);
  if (m) {
    const p = verifyToken(m[1]);
    if (p) (req as any).user = p;
  }
  next();
}
// 必须登录
function requireAuth(req: Request, res: Response, next: NextFunction) {
  if (!(req as any).user) return res.status(401).json({ error: "未登录" });
  next();
}
// 必须具备指定角色（三权分立：各司其职）
function requireRole(...roles: Role[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    const u = (req as any).user;
    if (!u) return res.status(401).json({ error: "未登录" });
    if (!roles.includes(u.role)) return res.status(403).json({ error: "无权限：仅" + roles.map(r => ROLE_LABEL[r]).join("/") + "可操作" });
    next();
  };
}
app.use(authOptional);

// 启动时种子三权分立管理员 + 学校结构
seedAdmin();
seedSchools();

// 将演示 student/teacher 绑定到种子学校 sch1 / 年级 grd2 / 班级 cls1，并预置一个 schooladmin 演示账号
(function bindDemoSchool() {
  const stu = findUserByName("student");
  if (stu && !stu.schoolId) {
    stu.schoolId = "sch1"; stu.classId = "cls1"; stu.grade = "高二"; stu.className = "高二(1)班";
  }
  const tch = findUserByName("teacher");
  if (tch && !tch.schoolId) {
    tch.schoolId = "sch1"; tch.gradeIds = ["grd2"]; tch.classIds = ["cls1"]; tch.className = "高二(1)班";
  }
  if (!findUserByName("schooladmin")) {
    const { salt, hash } = hashPassword("123456");
    saveUser({
      id: nextUserId(), username: "schooladmin", name: "陈校长", role: "schooladmin",
      salt, passwordHash: hash, status: "active", schoolId: "sch1",
      idNumber: "110101199001011234",
      createdAt: new Date().toISOString(), createdBy: "system",
    });
  }
  if (!findUserByName("gradeadmin")) {
    const { salt, hash } = hashPassword("123456");
    saveUser({
      id: nextUserId(), username: "gradeadmin", name: "林年级长", role: "gradeadmin",
      salt, passwordHash: hash, status: "active", schoolId: "sch1", gradeIds: ["grd2"],
      idNumber: "110101198501015678",
      createdAt: new Date().toISOString(), createdBy: "system",
    });
  }
  // 标记种子学校的 owner
  const sch = findSchool("sch1");
  if (sch) { sch.ownerId = findUserByName("schooladmin")?.id; sch.status = "active"; }
})();

// 业务操作审计（业务管理员的知识点/题目增删改）
function bizLog(req: Request, action: string, targetId: string, targetName: string) {
  const u = (req as any).user;
  if (!u) return;
  addLog({
    actorId: u.uid, actorName: u.u, actorRole: u.role,
    action: "business", targetType: "content", targetId, targetName,
    detail: action,
  });
}

// ---------- adaptive session engine ----------
interface Session {
  id: string;
  assessmentType: string;     // a1/a2/a3
  unitId?: string;
  stageId?: string;
  pool: Question[];           // 有效题库（按学生班级继承链解析；回退系统全量）
  questionIds: string[];      // candidate pool (filtered by unit/module/all)
  currentQuestionId: string | null; // stable current question
  answers: Record<string, { answer: string; correct: boolean; marked: boolean }>;
  difficulty: number;
  totalQuestions: number;
  finished: boolean;
  reportId?: string;
}
const sessions = new Map<string, Session>();
let sessionSeq = 0;
let reportSeq = 100;

function poolFor(type: string, unitId: string | undefined, base: Question[]): Question[] {
  if (type === "a2" && unitId) return base.filter((q) => q.unitId === unitId);
  return base; // 入门诊断 / 阶段综合 — 全题库
}
function totalFor(type: string) {
  return type === "a2" ? 15 : type === "a3" ? 35 : 35;
}

function pickNext(session: Session): Question | null {
  // 自适应：根据当前难度挑选题目；答对提升难度，答错降低
  const pool = session.questionIds
    .map((id) => session.pool.find((q) => q.id === id)!)
    .filter(Boolean);
  const answered = Object.keys(session.answers);
  let candidates = pool.filter((q) => !answered.includes(q.id));
  if (candidates.length === 0) return null;
  // 按难度过滤（允许 ±1 浮动以扩大候选）
  const target = session.difficulty;
  let filtered = candidates.filter((q) => Math.abs(q.difficulty - target) <= 0);
  if (filtered.length === 0) filtered = candidates.filter((q) => Math.abs(q.difficulty - target) <= 1);
  if (filtered.length === 0) filtered = candidates;
  const pick = filtered[Math.floor(Math.random() * filtered.length)];
  return pick;
}

// ---------- routes ----------

// 首页
app.get("/api/profile", (_req, res) => res.json(profile));
app.get("/api/today-task", (_req, res) => res.json(todayTask));
app.get("/api/todos", (_req, res) => res.json(todos));
app.get("/api/bits", (_req, res) => res.json(bits));

// 测评广场
app.get("/api/assessments", (_req, res) => res.json(assessments));
app.get("/api/assessments/units", (_req, res) => {
  const units = modules.flatMap((m) => m.units.map((u) => ({ id: u.id, name: u.name, module: m.name, moduleId: m.id })));
  res.json(units);
});
app.get("/api/assessments/stages", (_req, res) => res.json(stages));
app.get("/api/assessments/history", (_req, res) => res.json(assessmentHistory));

// 测评 session
app.post("/api/assessments/sessions", (req, res) => {
  const { type, unitId, stageId } = req.body || {};
  const t = type || "a1";
  // 按当前学生班级继承链解析有效题库；无 classId 则回退系统全量
  const p = (req as any).user;
  const u = p ? findUser(p.uid) : null;
  const chain = u?.classId ? chainForClass(u.classId) : null;
  const base = chain ? effectiveQuestions(chain) : questions;
  const pool = poolFor(t, unitId, base);
  const id = `s${++sessionSeq}`;
  const session: Session = {
    id, assessmentType: t, unitId, stageId,
    pool, questionIds: pool.map((q) => q.id),
    currentQuestionId: null, answers: {}, difficulty: 2,
    totalQuestions: Math.min(totalFor(t), pool.length),
    finished: false,
  };
  sessions.set(id, session);
  const first = pickNext(session)!;
  session.currentQuestionId = first.id;
  res.json({ sessionId: id, totalQuestions: session.totalQuestions, question: pubQuestion(first), index: 1 });
});

app.get("/api/sessions/:id", (req, res) => {
  const s = sessions.get(req.params.id);
  if (!s) return res.status(404).json({ error: "session not found" });
  if (s.finished) return res.json({ finished: true, reportId: s.reportId });
  const q = s.currentQuestionId ? s.pool.find((x) => x.id === s.currentQuestionId) : null;
  if (!q) return res.json({ finished: true, reportId: s.reportId });
  res.json({
    sessionId: s.id, question: pubQuestion(q), index: Object.keys(s.answers).length + 1,
    totalQuestions: s.totalQuestions, difficulty: s.difficulty,
  });
});

app.post("/api/sessions/:id/answer", (req, res) => {
  const s = sessions.get(req.params.id);
  if (!s) return res.status(404).json({ error: "session not found" });
  const { questionId, answer, marked } = req.body || {};
  const q = s.pool.find((x) => x.id === questionId);
  if (!q) return res.status(404).json({ error: "question not found" });
  const correct = q.type === "short" ? true : answer === q.answer; // 简答题不自动判分
  s.answers[questionId] = { answer, correct, marked: !!marked };
  // 自适应难度调整
  if (correct) s.difficulty = Math.min(4, s.difficulty + 1);
  else s.difficulty = Math.max(1, s.difficulty - 1);
  const answered = Object.keys(s.answers).length;
  const next = pickNext(s);
  s.currentQuestionId = next ? next.id : null;
  const done = answered >= s.totalQuestions || !next;
  res.json({
    correct, correctAnswer: q.type === "short" ? undefined : q.answer,
    analysis: q.analysis, difficulty: s.difficulty,
    next: done ? null : pubQuestion(next!),
    index: answered + 1, totalQuestions: s.totalQuestions, finished: done,
  });
});

app.post("/api/sessions/:id/submit", (req, res) => {
  const s = sessions.get(req.params.id);
  if (!s) return res.status(404).json({ error: "session not found" });
  s.finished = true;
  const reportId = `r${++reportSeq}`;
  s.reportId = reportId;
  const answered = Object.values(s.answers).filter((a) => a.correct).length;
  const total = s.totalQuestions || 1;
  const score = Math.round(60 + (answered / total) * 38); // 60-98 区间
  res.json({ reportId, score, answered, total });
});

// 报告
app.get("/api/reports/:id", (req, res) => {
  res.json(buildReport(req.params.id));
});

// 知识图谱
app.get("/api/knowledge-graph", (req, res) => {
  // 学生若有 classId，返回该班级的有效继承知识图谱；否则回退系统全量
  let kps: KnowledgePoint[];
  const p = (req as any).user;
  const u = p ? findUser(p.uid) : null;
  const chain = u?.classId ? chainForClass(u.classId) : null;
  if (chain) kps = effectiveKps(chain);
  else kps = modules.flatMap((m) => m.units.flatMap((u) => u.knowledgePoints));
  const graph = modules.map((m) => {
    const mks = kps.filter((k) => k.moduleId === m.id);
    const units = m.units.map((u) => ({
      id: u.id, name: u.name,
      knowledgePoints: kps.filter((k) => k.unitId === u.id).map((k) => ({
        id: k.id, name: k.name, mastery: k.mastery, frequency: k.frequency, errorCount: k.errorCount,
      })),
    }));
    const avg = mks.length ? Math.round(mks.reduce((s, k) => s + k.mastery, 0) / mks.length) : 0;
    return { id: m.id, name: m.name, mastery: avg, units };
  });
  res.json(graph);
});
app.get("/api/knowledge-graph/radar", (_req, res) => {
  res.json({ user: profile.radar, grade: profile.gradeRadar });
});
app.get("/api/knowledge-points/:id", (req, res) => {
  const k = allKp(req.params.id);
  if (!k) return res.status(404).json({ error: "not found" });
  res.json({
    ...k,
    moduleName: modules.find((m) => m.id === k.moduleId)?.name,
    unitName: modules.flatMap((m) => m.units).find((u) => u.id === k.unitId)?.name,
  });
});

// 知识点学习
app.get("/api/knowledge-points/:id/study", (req, res) => {
  const study = getStudy(req.params.id);
  if (!study) return res.status(404).json({ error: "not found" });
  res.json(study);
});
app.post("/api/knowledge-points/:id/train", (req, res) => {
  const { answers } = req.body || {}; // { questionId: answer }
  const k = allKp(req.params.id);
  if (!k) return res.status(404).json({ error: "not found" });
  let correct = 0, total = 0;
  for (const [qid, ans] of Object.entries(answers || {})) {
    const q = questions.find((x) => x.id === qid);
    if (!q) continue;
    total++;
    if (q.type !== "short" && ans === q.answer) correct++;
  }
  const score = total ? Math.round((correct / total) * 100) : 0;
  // 更新掌握度（简单：向 score 靠拢）
  k.mastery = Math.round(k.mastery * 0.6 + score * 0.4);
  res.json({ score, correct, total, correctRate: total ? Math.round((correct / total) * 100) : 0, mastery: k.mastery });
});

// 提升方案
app.get("/api/plan/current", (_req, res) => {
  const { id, name, goal, totalDays, completionRate, stages } = plan;
  res.json({ id, name, goal, totalDays, completionRate, stages });
});
app.get("/api/plan/tasks", (_req, res) => res.json(plan.tasks));
app.get("/api/plan/stages/:id", (req, res) => {
  const s = plan.stages.find((x) => x.id === req.params.id);
  if (!s) return res.status(404).json({ error: "not found" });
  res.json(s);
});

// 错题本
app.get("/api/errors", (_req, res) => {
  res.json(errors.map((e) => ({ id: e.id, kpId: e.kpId, moduleId: e.moduleId, difficulty: e.difficulty, errorType: e.errorType, stem: e.stem, date: e.date, rework: !!e.rework, collected: !!e.collected })));
});
app.get("/api/errors/:id", (req, res) => {
  const e = errors.find((x) => x.id === req.params.id);
  if (!e) return res.status(404).json({ error: "not found" });
  const kp = allKp(e.kpId);
  res.json({
    ...e,
    kpName: kp?.name,
    moduleName: modules.find((m) => m.id === e.moduleId)?.name,
  });
});
app.post("/api/errors/:id/rework", (req, res) => {
  const e = errors.find((x) => x.id === req.params.id);
  if (!e) return res.status(404).json({ error: "not found" });
  e.rework = true;
  res.json({ ok: true, rework: true });
});
app.get("/api/errors/:id/variants", (req, res) => {
  const e = errors.find((x) => x.id === req.params.id);
  if (!e) return res.status(404).json({ error: "not found" });
  const variants = questions.filter((q) => q.kpId === e.kpId && q.id !== req.params.id).slice(0, 3);
  res.json(variants.map(pubQuestion));
});

// 成长中心
app.get("/api/growth", (req, res) => {
  const range = (req.query.range as string) || "week";
  const series = (growth as any)[range] || growth.week;
  res.json({ series, stats: growth.stats, goal: growth.goal });
});
app.post("/api/growth/goal", (req, res) => {
  const { content, targetScore, targetMastery } = req.body || {};
  if (content) growth.goal.content = content;
  if (targetScore) growth.goal.targetScore = targetScore;
  if (targetMastery) growth.goal.targetMastery = targetMastery;
  res.json({ ok: true, goal: growth.goal });
});

// ============================================================
// 教师端路由
// ============================================================
app.get("/api/teacher/classes", (_req, res) => {
  res.json(classes.map((c) => ({ id: c.id, name: c.name, studentCount: c.studentCount, avgScore: c.avgScore })));
});
app.get("/api/teacher/classes/:id", (req, res) => {
  const c = classes.find((x) => x.id === req.params.id);
  if (!c) return res.status(404).json({ error: "not found" });
  res.json(c);
});

app.get("/api/teacher/assessments", (req, res) => {
  const status = req.query.status as string | undefined;
  let list = teacherAssessments;
  if (status === "ongoing") list = list.filter((a) => a.status === "ongoing");
  if (status === "done") list = list.filter((a) => a.status === "done");
  res.json(list);
});
app.post("/api/teacher/assessments", (req, res) => {
  const { name, type, className, deadline } = req.body || {};
  if (!name || !className) return res.status(400).json({ error: "缺少必要参数" });
  const a = {
    id: `ta${teacherAssessments.length + 1}`, name, type: type || "阶段综合",
    className, status: "ongoing" as const, deadline: deadline || "",
    submission: 0, total: 42,
  };
  teacherAssessments.unshift(a);
  res.json(a);
});
app.get("/api/teacher/assessments/:id", (req, res) => {
  const a = teacherAssessments.find((x) => x.id === req.params.id);
  if (!a) return res.status(404).json({ error: "not found" });
  res.json(a);
});

app.get("/api/teacher/students/:id", (req, res) => {
  const s = findStudent(req.params.id);
  if (!s) return res.status(404).json({ error: "not found" });
  res.json(s);
});
app.post("/api/teacher/students/:id/note", (req, res) => {
  const s = findStudent(req.params.id);
  if (!s) return res.status(404).json({ error: "not found" });
  s.note = req.body?.note ?? "";
  res.json({ ok: true, note: s.note });
});

// ============================================================
// 管理后台路由（知识图谱 CRUD + 题库 CRUD）
// ============================================================
let kpSeq = 1000, qSeq = 1000;
function findKpMutable(kpId: string): KnowledgePoint | null {
  return allKp(kpId);
}
function findKpLocation(kpId: string) {
  for (const m of modules) for (const u of m.units) {
    const k = u.knowledgePoints.find((x) => x.id === kpId);
    if (k) return { unit: u, kp: k };
  }
  return null;
}

// 知识目录树（业务管理员）
app.get("/api/admin/knowledge-tree", requireAuth, requireRole("bizadmin"), (_req, res) => {
  res.json(modules.map((m) => ({
    id: m.id, name: m.name,
    units: m.units.map((u) => ({
      id: u.id, name: u.name,
      knowledgePoints: u.knowledgePoints.map((k) => ({ id: k.id, name: k.name, mastery: k.mastery, frequency: k.frequency })),
    })),
  })));
});
// 新增知识点
app.post("/api/admin/knowledge-points", requireAuth, requireRole("bizadmin"), (req, res) => {
  const { unitId, name, mastery, frequency } = req.body || {};
  const unit = modules.flatMap((m) => m.units).find((u) => u.id === unitId);
  if (!unit) return res.status(404).json({ error: "单元不存在" });
  const kp: KnowledgePoint = {
    id: `k${++kpSeq}`, name: name || "新知识点", unitId, moduleId: unit.moduleId,
    mastery: mastery ?? 50, frequency: frequency ?? 5, errorCount: 0,
  };
  unit.knowledgePoints.push(kp);
  bizLog(req, "新增知识点", kp.id, kp.name);
  res.json(kp);
});
// 更新知识点
app.put("/api/admin/knowledge-points/:id", requireAuth, requireRole("bizadmin"), (req, res) => {
  const loc = findKpLocation(req.params.id);
  if (!loc) return res.status(404).json({ error: "知识点不存在" });
  const { name, mastery, frequency } = req.body || {};
  if (name !== undefined) loc.kp.name = name;
  if (mastery !== undefined) loc.kp.mastery = mastery;
  if (frequency !== undefined) loc.kp.frequency = frequency;
  bizLog(req, "编辑知识点", loc.kp.id, loc.kp.name);
  res.json(loc.kp);
});
// 删除知识点
app.delete("/api/admin/knowledge-points/:id", requireAuth, requireRole("bizadmin"), (req, res) => {
  const loc = findKpLocation(req.params.id);
  if (!loc) return res.status(404).json({ error: "知识点不存在" });
  bizLog(req, "删除知识点", loc.kp.id, loc.kp.name);
  loc.unit.knowledgePoints = loc.unit.knowledgePoints.filter((k) => k.id !== req.params.id);
  res.json({ ok: true });
});

// 题库管理（业务管理员）
app.get("/api/admin/questions", requireAuth, requireRole("bizadmin"), (req, res) => {
  const { kpId, moduleId, type, difficulty } = req.query;
  let list = questions.map((q) => ({ ...q }));
  if (kpId) list = list.filter((q) => q.kpId === kpId);
  if (moduleId) list = list.filter((q) => q.moduleId === moduleId);
  if (type) list = list.filter((q) => q.type === type);
  if (difficulty) list = list.filter((q) => String(q.difficulty) === String(difficulty));
  res.json(list);
});
app.post("/api/admin/questions", requireAuth, requireRole("bizadmin"), (req, res) => {
  const b = req.body || {};
  const q: Question = {
    id: `q${++qSeq}`, moduleId: b.moduleId, unitId: b.unitId, kpId: b.kpId,
    type: b.type || "choice", difficulty: b.difficulty || 2,
    material: b.material, stem: b.stem || "新题目", options: b.options,
    answer: b.answer || "", analysis: b.analysis || "", errorType: b.errorType,
  };
  questions.push(q);
  bizLog(req, "新增题目", q.id, q.stem);
  res.json(q);
});
app.put("/api/admin/questions/:id", requireAuth, requireRole("bizadmin"), (req, res) => {
  const q = questions.find((x) => x.id === req.params.id);
  if (!q) return res.status(404).json({ error: "题目不存在" });
  const b = req.body || {};
  for (const key of ["stem", "material", "answer", "analysis", "type", "difficulty", "errorType", "options", "kpId", "moduleId", "unitId"]) {
    if (b[key] !== undefined) (q as any)[key] = b[key];
  }
  bizLog(req, "编辑题目", q.id, q.stem);
  res.json(q);
});
app.delete("/api/admin/questions/:id", requireAuth, requireRole("bizadmin"), (req, res) => {
  const i = questions.findIndex((x) => x.id === req.params.id);
  if (i < 0) return res.status(404).json({ error: "题目不存在" });
  bizLog(req, "删除题目", questions[i].id, questions[i].stem);
  questions.splice(i, 1);
  res.json({ ok: true });
});

function pubQuestion(q: Question) {
  return {
    id: q.id, type: q.type, difficulty: q.difficulty, material: q.material,
    stem: q.stem, options: q.options, moduleId: q.moduleId, unitId: q.unitId, kpId: q.kpId,
  };
}

// ============================================================
// 账号注册 / 登录 / 生命周期 / 三权分立
// ============================================================

// 注册（学生 / 教师 / 学校管理员 / 年级管理员）
// 学校层级（schooladmin/gradeadmin/teacher/student）一律 pending，需逐级授权方可登录
app.post("/api/auth/register", (req, res) => {
  const b = req.body || {};
  const { username, password, name, role } = b;
  if (!username || !password || !name) return res.status(400).json({ error: "缺少用户名/密码/姓名" });
  const allowed: Role[] = ["student", "teacher", "schooladmin", "gradeadmin"];
  const r: Role = (allowed as string[]).includes(role) ? (role as Role) : "student";
  if (findUserByName(username)) return res.status(409).json({ error: "用户名已存在" });
  if (password.length < getPolicy().minPasswordLength) return res.status(400).json({ error: `密码至少 ${getPolicy().minPasswordLength} 位` });

  // 学校层级字段校验
  let schoolId: string | undefined;
  let schoolName: string | undefined;
  if (r === "schooladmin") {
    if (!b.schoolName) return res.status(400).json({ error: "学校管理员需填写学校名称" });
    if (findSchoolByName(b.schoolName)) return res.status(409).json({ error: "该学校名称已存在" });
    schoolName = b.schoolName;
  } else {
    // gradeadmin/teacher/student 必须选择已存在且已激活的学校
    if (!b.schoolId) return res.status(400).json({ error: "请选择所属学校" });
    const sch = findSchool(b.schoolId);
    if (!sch || sch.status !== "active") return res.status(400).json({ error: "学校不存在或未授权" });
    schoolId = b.schoolId;
  }
  if (!b.idNumber) return res.status(400).json({ error: "请填写身份证号" });

  // schooladmin 注册时创建 pending 学校
  if (r === "schooladmin") {
    const sch: School = { id: nextSchoolId(), name: schoolName!, createdAt: new Date().toISOString(), createdBy: "self", status: "pending" };
    saveSchool(sch);
    schoolId = sch.id;
  }

  const { salt, hash } = hashPassword(password);
  const u: User = {
    id: nextUserId(), username, name, role: r, salt, passwordHash: hash,
    status: "pending",            // 学校层级一律待授权
    email: b.email, phone: b.phone,
    idNumber: b.idNumber,
    schoolId,
    // student 选了班级
    classId: r === "student" ? b.classId : undefined,
    studentNo: r === "student" ? b.studentNo : undefined,
    createdAt: new Date().toISOString(), createdBy: "self",
  };
  // 兼容旧演示字段（student 的 grade/className 字符串）
  if (r === "student") { const c = b.classId ? findClass(b.classId) : undefined; if (c) { u.className = c.name; const g = findGrade(c.gradeId); if (g) u.grade = g.name; } }

  saveUser(u);
  addLog({ actorId: u.id, actorName: u.name, actorRole: u.role, action: "register", targetType: "user", targetId: u.id, targetName: u.name, detail: `注册${ROLE_LABEL[u.role]}账号，待授权` });
  res.json({ ok: true, user: publicUser(u), message: "注册成功，待相应管理员授权后方可登录" });
});

// 登录
app.post("/api/auth/login", (req, res) => {
  const { username, password } = req.body || {};
  const u = findUserByName(username || "");
  if (!u || !verifyPassword(password || "", u.salt, u.passwordHash)) return res.status(401).json({ error: "用户名或密码错误" });
  if (u.status !== "active") return res.status(403).json({ error: `账号状态：${STATUS_LABEL[u.status]}，无法登录` });
  u.lastLogin = new Date().toISOString();
  addLog({ actorId: u.id, actorName: u.name, actorRole: u.role, action: "login", targetType: "user", targetId: u.id, targetName: u.name, detail: "登录系统" });
  res.json({ token: signToken(u), user: publicUser(u) });
});

// 当前用户
app.get("/api/auth/me", requireAuth, (req, res) => {
  const u = findUser((req as any).user.uid);
  if (!u) return res.status(404).json({ error: "用户不存在" });
  res.json(publicUser(u));
});

// 修改自己的密码
app.post("/api/auth/change-password", requireAuth, (req, res) => {
  const u = findUser((req as any).user.uid)!;
  const { oldPassword, newPassword } = req.body || {};
  if (!verifyPassword(oldPassword || "", u.salt, u.passwordHash)) return res.status(400).json({ error: "原密码错误" });
  if ((newPassword || "").length < getPolicy().minPasswordLength) return res.status(400).json({ error: "新密码过短" });
  const { salt, hash } = hashPassword(newPassword);
  u.salt = salt; u.passwordHash = hash;
  addLog({ actorId: u.id, actorName: u.name, actorRole: u.role, action: "change_password", targetType: "user", targetId: u.id, targetName: u.name, detail: "修改自身密码" });
  res.json({ ok: true });
});

// ---------- 用户生命周期（系统管理员） ----------
app.get("/api/users", requireAuth, requireRole("sysadmin", "audadmin"), (req, res) => {
  const { role, status, keyword } = req.query;
  let list = listUsers().map(publicUser);
  if (role) list = list.filter((u) => u.role === role);
  if (status) list = list.filter((u) => u.status === status);
  if (keyword) list = list.filter((u) => (u.username + u.name).includes(String(keyword)));
  res.json(list);
});

// 用户生命周期状态变更（系统管理员）
app.patch("/api/users/:id/status", requireAuth, requireRole("sysadmin"), (req, res) => {
  const actor = findUser((req as any).user.uid)!;
  const target = findUser(req.params.id);
  if (!target) return res.status(404).json({ error: "用户不存在" });
  const status = req.body?.status as UserStatus;
  if (!["pending", "active", "suspended", "deactivated"].includes(status)) return res.status(400).json({ error: "非法状态" });
  // 互斥约束：内置管理员不可注销/停用（避免单点瘫痪）
  if (target.builtin && (status === "deactivated" || status === "suspended")) {
    return res.status(403).json({ error: "内置管理员账号不可停用/注销" });
  }
  // 系统管理员不能操作自己的状态（防自残导致无管理员）
  if (target.id === actor.id) return res.status(403).json({ error: "不能操作自身账号状态" });
  const prev = target.status;
  target.status = status;
  addLog({ actorId: actor.id, actorName: actor.name, actorRole: actor.role, action: "lifecycle", targetType: "user", targetId: target.id, targetName: target.username, detail: `${STATUS_LABEL[prev]} → ${STATUS_LABEL[status]}` });
  res.json(publicUser(target));
});

// 重置密码（系统管理员）
app.post("/api/users/:id/reset-password", requireAuth, requireRole("sysadmin"), (req, res) => {
  const actor = findUser((req as any).user.uid)!;
  const target = findUser(req.params.id);
  if (!target) return res.status(404).json({ error: "用户不存在" });
  if (target.builtin && target.id !== actor.id) {
    // 内置管理员密码只能本人或经安全管理员策略重置——此处允许系统管理员重置非自身内置管理员为默认密码
  }
  const newPwd = req.body?.password || "123456";
  const { salt, hash } = hashPassword(newPwd);
  target.salt = salt; target.passwordHash = hash;
  addLog({ actorId: actor.id, actorName: actor.name, actorRole: actor.role, action: "reset_password", targetType: "user", targetId: target.id, targetName: target.username, detail: "重置密码" });
  res.json({ ok: true, message: `密码已重置为 ${newPwd}` });
});

// 删除用户（系统管理员，内置不可删）
app.delete("/api/users/:id", requireAuth, requireRole("sysadmin"), (req, res) => {
  const actor = findUser((req as any).user.uid)!;
  const target = findUser(req.params.id);
  if (!target) return res.status(404).json({ error: "用户不存在" });
  if (target.builtin) return res.status(403).json({ error: "内置管理员账号不可删除" });
  if (target.id === actor.id) return res.status(403).json({ error: "不能删除自身账号" });
  deleteUser(target.id);
  addLog({ actorId: actor.id, actorName: actor.name, actorRole: actor.role, action: "delete_user", targetType: "user", targetId: target.id, targetName: target.username, detail: "删除账号" });
  res.json({ ok: true });
});

// ---------- 角色与权限（安全管理员） ----------
app.patch("/api/users/:id/role", requireAuth, requireRole("secadmin"), (req, res) => {
  const actor = findUser((req as any).user.uid)!;
  const target = findUser(req.params.id);
  if (!target) return res.status(404).json({ error: "用户不存在" });
  const role = req.body?.role as Role;
  if (!["student", "teacher", "sysadmin", "secadmin", "audadmin"].includes(role)) return res.status(400).json({ error: "非法角色" });
  if (target.id === actor.id) return res.status(403).json({ error: "不能修改自身角色" });
  // 安全管理员不能直接提升为内置三管理员之外的其它内置管理员？允许角色调整，但内置标记不变
  const prev = target.role;
  target.role = role;
  addLog({ actorId: actor.id, actorName: actor.name, actorRole: actor.role, action: "role_change", targetType: "user", targetId: target.id, targetName: target.username, detail: `${ROLE_LABEL[prev]} → ${ROLE_LABEL[role]}` });
  res.json(publicUser(target));
});

// 安全策略（安全管理员）
app.get("/api/security/policy", requireAuth, requireRole("secadmin"), (_req, res) => res.json(getPolicy()));
app.patch("/api/security/policy", requireAuth, requireRole("secadmin"), (req, res) => {
  const actor = findUser((req as any).user.uid)!;
  const before = getPolicy();
  setPolicy(req.body || {});
  addLog({ actorId: actor.id, actorName: actor.name, actorRole: actor.role, action: "policy_change", targetType: "policy", targetId: "-", targetName: "安全策略", detail: `修改前 ${JSON.stringify(before)}` });
  res.json(getPolicy());
});

// ---------- 审计日志（审计管理员只读，系统管理员只读本人操作） ----------
app.get("/api/audit-logs", requireAuth, requireRole("audadmin", "sysadmin"), (req, res) => {
  const actor = findUser((req as any).user.uid)!;
  let list = listLogs();
  // 系统管理员仅可见自身操作记录（审计独立）；审计管理员全量只读
  if (actor.role === "sysadmin") list = list.filter((l) => l.actorId === actor.id);
  res.json(list);
});

// ============================================================
// 学校层级体系（学校 / 年级 / 班级 + 逐级授权 + 继承式内容）
// ============================================================

function currentUser(req: Request): User | null {
  const p = (req as any).user;
  return p ? findUser(p.uid) : null;
}

// 学校管理员：须为 schooladmin 且操作对象在其本校
function requireSchoolAdmin(req: Request, res: Response, next: NextFunction) {
  const u = currentUser(req);
  if (!u) return res.status(401).json({ error: "未登录" });
  if (u.role !== "schooladmin") return res.status(403).json({ error: "仅学校管理员可操作" });
  next();
}
// 年级管理员
function requireGradeAdmin(req: Request, res: Response, next: NextFunction) {
  const u = currentUser(req);
  if (!u) return res.status(401).json({ error: "未登录" });
  if (u.role !== "gradeadmin") return res.status(403).json({ error: "仅年级管理员可操作" });
  next();
}

// 构造继承链：给定 classId → ["school:sch","grade:grd","class:cls"]
function chainForClass(classId: string): string[] | null {
  const c = findClass(classId); if (!c) return null;
  const g = findGrade(c.gradeId); if (!g) return null;
  return [`school:${g.schoolId}`, `grade:${c.gradeId}`, `class:${classId}`];
}
function chainForGrade(gradeId: string): string[] | null {
  const g = findGrade(gradeId); if (!g) return null;
  return [`school:${g.schoolId}`, `grade:${gradeId}`];
}
function chainForSchool(schoolId: string): string[] {
  return [`school:${schoolId}`];
}
// 当前用户的"管理链"：schooladmin→school, gradeadmin→其年级（取第一个）, teacher→其班级, student→其班级
function manageChain(u: User): string[] | null {
  if (u.role === "schooladmin" && u.schoolId) return chainForSchool(u.schoolId);
  if (u.role === "gradeadmin" && u.gradeIds?.length) return chainForGrade(u.gradeIds[0]);
  if (u.role === "teacher" && u.classIds?.length) return chainForClass(u.classIds[0]);
  if (u.role === "student" && u.classId) return chainForClass(u.classId);
  return null;
}

// ---------- 公共：学校 / 年级 / 班级 下拉 ----------
app.get("/api/schools", (_req, res) => res.json(listActiveSchools().map((s) => ({ id: s.id, name: s.name }))));
app.get("/api/schools/:id/grades", (req, res) => {
  const sch = findSchool(req.params.id);
  if (!sch) return res.status(404).json({ error: "学校不存在" });
  res.json(listGrades(sch.id).map((g) => ({ id: g.id, name: g.name })));
});
app.get("/api/schools/:id/grades/:gid/classes", (req, res) => {
  res.json(listClasses(req.params.id, req.params.gid).map((c) => ({ id: c.id, name: c.name })));
});

// ---------- bizadmin：审批 schooladmin ----------
app.get("/api/biz/pending-school-admins", requireAuth, requireRole("bizadmin"), (_req, res) => {
  const list = listUsers().filter((u) => u.role === "schooladmin" && u.status === "pending");
  res.json(list.map((u) => ({ ...publicUser(u), schoolName: u.schoolId ? findSchool(u.schoolId)?.name : "" })));
});
app.patch("/api/biz/school-admins/:id/approve", requireAuth, requireRole("bizadmin"), (req, res) => {
  const target = findUser(req.params.id);
  if (!target || target.role !== "schooladmin") return res.status(404).json({ error: "学校管理员不存在" });
  if (target.status === "active") return res.json(publicUser(target));
  target.status = "active";
  if (target.schoolId) { const sch = findSchool(target.schoolId); if (sch) { sch.status = "active"; sch.ownerId = target.id; saveSchool(sch); } }
  addLog({ actorId: (req as any).user.uid, actorName: (req as any).user.u, actorRole: "bizadmin", action: "school_approve", targetType: "user", targetId: target.id, targetName: target.name, detail: "授权学校管理员" });
  res.json(publicUser(target));
});

// ---------- schooladmin：本校结构（年级 / 班级） ----------
app.get("/api/school/grades", requireAuth, requireSchoolAdmin, (req, res) => {
  const u = currentUser(req)!;
  res.json(listGrades(u.schoolId).map((g) => ({ ...g, classCount: listClasses(u.schoolId, g.id).length })));
});
app.post("/api/school/grades", requireAuth, requireSchoolAdmin, (req, res) => {
  const u = currentUser(req)!;
  const { name } = req.body || {};
  if (!name) return res.status(400).json({ error: "年级名称必填" });
  const g: Grade = { id: nextGradeId(), schoolId: u.schoolId!, name };
  saveGrade(g);
  res.json(g);
});
app.patch("/api/school/grades/:id", requireAuth, requireSchoolAdmin, (req, res) => {
  const g = findGrade(req.params.id);
  if (!g || g.schoolId !== currentUser(req)!.schoolId) return res.status(404).json({ error: "年级不存在" });
  if (req.body?.name) g.name = req.body.name;
  res.json(g);
});
app.delete("/api/school/grades/:id", requireAuth, requireSchoolAdmin, (req, res) => {
  const g = findGrade(req.params.id);
  if (!g || g.schoolId !== currentUser(req)!.schoolId) return res.status(404).json({ error: "年级不存在" });
  deleteGrade(g.id);
  res.json({ ok: true });
});
app.get("/api/school/classes", requireAuth, requireSchoolAdmin, (req, res) => {
  const u = currentUser(req)!;
  res.json(listClasses(u.schoolId).map((c) => ({ ...c, gradeName: findGrade(c.gradeId)?.name })));
});
app.post("/api/school/classes", requireAuth, requireSchoolAdmin, (req, res) => {
  const u = currentUser(req)!;
  const { name, gradeId } = req.body || {};
  const g = findGrade(gradeId);
  if (!g || g.schoolId !== u.schoolId) return res.status(400).json({ error: "年级不存在或不属于本校" });
  if (!name) return res.status(400).json({ error: "班级名称必填" });
  const c: Class = { id: nextClassId(), schoolId: u.schoolId!, gradeId, name };
  saveClass(c);
  res.json(c);
});
app.patch("/api/school/classes/:id", requireAuth, requireSchoolAdmin, (req, res) => {
  const c = findClass(req.params.id);
  if (!c || c.schoolId !== currentUser(req)!.schoolId) return res.status(404).json({ error: "班级不存在" });
  if (req.body?.name) c.name = req.body.name;
  res.json(c);
});
app.delete("/api/school/classes/:id", requireAuth, requireSchoolAdmin, (req, res) => {
  const c = findClass(req.params.id);
  if (!c || c.schoolId !== currentUser(req)!.schoolId) return res.status(404).json({ error: "班级不存在" });
  deleteClass(c.id);
  res.json({ ok: true });
});

// ---------- schooladmin：本校用户生命周期与授权分配 ----------
app.get("/api/school/users", requireAuth, requireSchoolAdmin, (req, res) => {
  const u = currentUser(req)!;
  let list = listUsers().filter((x) => x.schoolId === u.schoolId && x.role !== "schooladmin");
  const { role, status, kw } = req.query;
  if (role) list = list.filter((x) => x.role === role);
  if (status) list = list.filter((x) => x.status === status);
  if (kw) list = list.filter((x) => (x.name + x.username + (x.idNumber || "")).includes(String(kw)));
  res.json(list.map((x) => ({
    ...publicUser(x),
    gradeName: x.gradeIds?.length ? x.gradeIds.map((id) => findGrade(id)?.name).filter(Boolean).join("/") : "",
    className: x.classIds?.length ? x.classIds.map((id) => findClass(id)?.name).filter(Boolean).join("/") : x.className,
    schoolName: findSchool(x.schoolId!)?.name,
  })));
});
app.get("/api/school/pending", requireAuth, requireSchoolAdmin, (req, res) => {
  const u = currentUser(req)!;
  res.json(listUsers().filter((x) => x.schoolId === u.schoolId && x.status === "pending").map((x) => ({
    ...publicUser(x), schoolName: findSchool(x.schoolId!)?.name,
  })));
});
// 授权 + 分配 scope（gradeIds / classIds / classId+studentNo 按角色）
app.patch("/api/school/users/:id/approve", requireAuth, requireSchoolAdmin, (req, res) => {
  const me = currentUser(req)!;
  const t = findUser(req.params.id);
  if (!t || t.schoolId !== me.schoolId) return res.status(404).json({ error: "用户不存在或不在本校" });
  const b = req.body || {};
  if (t.role === "gradeadmin" || t.role === "teacher") {
    if (Array.isArray(b.gradeIds)) t.gradeIds = b.gradeIds.filter((id: string) => findGrade(id)?.schoolId === me.schoolId);
    if (Array.isArray(b.classIds)) t.classIds = b.classIds.filter((id: string) => findClass(id)?.schoolId === me.schoolId);
  }
  if (t.role === "student") {
    if (b.classId) { const c = findClass(b.classId); if (c && c.schoolId === me.schoolId) { t.classId = b.classId; t.className = c.name; const g = findGrade(c.gradeId); if (g) t.grade = g.name; } }
    if (b.studentNo) t.studentNo = b.studentNo;
  }
  t.status = "active";
  addLog({ actorId: me.id, actorName: me.name, actorRole: me.role, action: "school_authorize", targetType: "user", targetId: t.id, targetName: t.name, detail: `授权${ROLE_LABEL[t.role]}并分配范围` });
  res.json(publicUser(t));
});
app.patch("/api/school/users/:id/status", requireAuth, requireSchoolAdmin, (req, res) => {
  const me = currentUser(req)!;
  const t = findUser(req.params.id);
  if (!t || t.schoolId !== me.schoolId) return res.status(404).json({ error: "用户不存在或不在本校" });
  if (t.id === me.id) return res.status(400).json({ error: "不可操作自身" });
  const prev = t.status;
  t.status = req.body?.status;
  addLog({ actorId: me.id, actorName: me.name, actorRole: me.role, action: "lifecycle", targetType: "user", targetId: t.id, targetName: t.username, detail: `${STATUS_LABEL[prev as UserStatus]} → ${STATUS_LABEL[t.status as UserStatus]}` });
  res.json(publicUser(t));
});
app.post("/api/school/users/:id/reset-password", requireAuth, requireSchoolAdmin, (req, res) => {
  const me = currentUser(req)!;
  const t = findUser(req.params.id);
  if (!t || t.schoolId !== me.schoolId) return res.status(404).json({ error: "用户不存在或不在本校" });
  const pw = req.body?.password || "123456";
  const { salt, hash } = hashPassword(pw);
  t.salt = salt; t.passwordHash = hash;
  addLog({ actorId: me.id, actorName: me.name, actorRole: me.role, action: "reset_password", targetType: "user", targetId: t.id, targetName: t.username, detail: "重置密码" });
  res.json({ ok: true });
});
app.delete("/api/school/users/:id", requireAuth, requireSchoolAdmin, (req, res) => {
  const me = currentUser(req)!;
  const t = findUser(req.params.id);
  if (!t || t.schoolId !== me.schoolId) return res.status(404).json({ error: "用户不存在或不在本校" });
  if (t.id === me.id) return res.status(400).json({ error: "不可删除自身" });
  deleteUser(t.id);
  addLog({ actorId: me.id, actorName: me.name, actorRole: me.role, action: "delete_user", targetType: "user", targetId: t.id, targetName: t.username, detail: "删除本校账号" });
  res.json({ ok: true });
});

// ---------- schooladmin：仪表盘 ----------
app.get("/api/school/dashboard", requireAuth, requireSchoolAdmin, (req, res) => {
  const u = currentUser(req)!;
  const schoolUsers = listUsers().filter((x) => x.schoolId === u.schoolId);
  res.json({
    school: { id: u.schoolId, name: findSchool(u.schoolId!)?.name },
    gradeCount: listGrades(u.schoolId).length,
    classCount: listClasses(u.schoolId).length,
    teacherCount: schoolUsers.filter((x) => x.role === "teacher").length,
    gradeAdminCount: schoolUsers.filter((x) => x.role === "gradeadmin").length,
    studentCount: schoolUsers.filter((x) => x.role === "student").length,
    pendingCount: schoolUsers.filter((x) => x.status === "pending").length,
  });
});

// ---------- 通用 scope 内容：knowledge-tree + CRUD + sync ----------
// 任何 scope 层都通过同一组端点操作，路径含 scope 与 id
function scopeParam(req: Request): { scope: ScopeLayer; id: string } | null {
  const s = req.params.scope as ScopeLayer;
  if (s !== "school" && s !== "grade" && s !== "class") return null;
  return { scope: s, id: req.params.id };
}
// 校验当前用户是否有权管理该 scope
function canManageScope(u: User, scope: ScopeLayer, id: string): boolean {
  if (scope === "school") return u.role === "schooladmin" && u.schoolId === id;
  if (scope === "grade") return u.role === "gradeadmin" && (u.gradeIds || []).includes(id) || (u.role === "schooladmin" && findGrade(id)?.schoolId === u.schoolId);
  if (scope === "class") {
    if (u.role === "teacher" && (u.classIds || []).includes(id)) return true;
    const c = findClass(id);
    return u.role === "schooladmin" && !!c && c.schoolId === u.schoolId;
  }
  return false;
}
function scopeChain(scope: ScopeLayer, id: string): string[] | null {
  if (scope === "school") return chainForSchool(id);
  if (scope === "grade") return chainForGrade(id);
  if (scope === "class") return chainForClass(id);
  return null;
}
function requireScopeManager(req: Request, res: Response, next: NextFunction) {
  const u = currentUser(req)!;
  if (!u) return res.status(401).json({ error: "未登录" });
  const sp = scopeParam(req);
  if (!sp) return res.status(400).json({ error: "scope 非法" });
  if (!canManageScope(u, sp.scope, sp.id)) return res.status(403).json({ error: "无权管理该范围" });
  next();
}

// 有效知识树（标注来源层）
app.get("/api/scope/:scope/:id/knowledge-tree", requireAuth, requireScopeManager, (req, res) => {
  const sp = scopeParam(req)!;
  const chain = scopeChain(sp.scope, sp.id)!;
  const eff = effectiveKps(chain);
  // 按模块/单元聚合
  const tree = modules.map((m) => ({
    id: m.id, name: m.name,
    units: m.units.map((u) => ({
      id: u.id, name: u.name,
      knowledgePoints: eff.filter((k) => k.moduleId === m.id && k.unitId === u.id).map((k) => ({ ...k, origin: kpOrigin(k.id, chain) })),
    })),
  }));
  res.json({ tree, scope: getScope(sp.scope, sp.id), extras: getScope(sp.scope, sp.id).extraKps });
});
app.post("/api/scope/:scope/:id/knowledge-points", requireAuth, requireScopeManager, (req, res) => {
  const sp = scopeParam(req)!;
  const { unitId, name, mastery, frequency } = req.body || {};
  const unit = modules.flatMap((m) => m.units).find((u) => u.id === unitId);
  if (!unit) return res.status(404).json({ error: "单元不存在" });
  const kp = addExtraKp(sp.scope, sp.id, { name: name || "新知识点", unitId, moduleId: unit.moduleId, mastery: mastery ?? 50, frequency: frequency ?? 5, errorCount: 0 });
  scopeLog(req, "新增知识点", kp.id, kp.name);
  res.json(kp);
});
app.put("/api/scope/:scope/:id/knowledge-points/:kpId", requireAuth, requireScopeManager, (req, res) => {
  const sp = scopeParam(req)!;
  const upd = patchExtraKp(sp.scope, sp.id, req.params.kpId, req.body || {});
  scopeLog(req, "编辑知识点", req.params.kpId, upd.name || req.params.kpId);
  res.json(upd);
});
app.delete("/api/scope/:scope/:id/knowledge-points/:kpId", requireAuth, requireScopeManager, (req, res) => {
  const sp = scopeParam(req)!;
  removeKp(sp.scope, sp.id, req.params.kpId);
  scopeLog(req, "删除/隐藏知识点", req.params.kpId, req.params.kpId);
  res.json({ ok: true });
});
app.patch("/api/scope/:scope/:id/knowledge-points/:kpId/restore", requireAuth, requireScopeManager, (req, res) => {
  const sp = scopeParam(req)!;
  restoreKp(sp.scope, sp.id, req.params.kpId);
  res.json({ ok: true });
});

// 有效题目
app.get("/api/scope/:scope/:id/questions", requireAuth, requireScopeManager, (req, res) => {
  const sp = scopeParam(req)!;
  const chain = scopeChain(sp.scope, sp.id)!;
  const eff = effectiveQuestions(chain);
  const { moduleId, type, difficulty } = req.query;
  let list = eff;
  if (moduleId) list = list.filter((q) => q.moduleId === moduleId);
  if (type) list = list.filter((q) => q.type === type);
  if (difficulty) list = list.filter((q) => String(q.difficulty) === String(difficulty));
  res.json(list.map((q) => ({ ...q, origin: qOrigin(q.id, chain) })));
});
app.post("/api/scope/:scope/:id/questions", requireAuth, requireScopeManager, (req, res) => {
  const sp = scopeParam(req)!;
  const b = req.body || {};
  const q = addExtraQuestion(sp.scope, sp.id, {
    moduleId: b.moduleId, unitId: b.unitId, kpId: b.kpId,
    type: b.type || "choice", difficulty: b.difficulty || 2,
    material: b.material, stem: b.stem || "新题目", options: b.options,
    answer: b.answer || "", analysis: b.analysis || "", errorType: b.errorType,
  });
  scopeLog(req, "新增题目", q.id, q.stem);
  res.json(q);
});
app.put("/api/scope/:scope/:id/questions/:qId", requireAuth, requireScopeManager, (req, res) => {
  const sp = scopeParam(req)!;
  const upd = patchExtraQuestion(sp.scope, sp.id, req.params.qId, req.body || {});
  scopeLog(req, "编辑题目", req.params.qId, upd.stem || req.params.qId);
  res.json(upd);
});
app.delete("/api/scope/:scope/:id/questions/:qId", requireAuth, requireScopeManager, (req, res) => {
  const sp = scopeParam(req)!;
  removeQuestion(sp.scope, sp.id, req.params.qId);
  scopeLog(req, "删除/隐藏题目", req.params.qId, req.params.qId);
  res.json({ ok: true });
});
app.patch("/api/scope/:scope/:id/questions/:qId/restore", requireAuth, requireScopeManager, (req, res) => {
  const sp = scopeParam(req)!;
  restoreQuestion(sp.scope, sp.id, req.params.qId);
  res.json({ ok: true });
});

// 同步模式 + 手动刷新
app.get("/api/scope/:scope/:id/sync", requireAuth, requireScopeManager, (req, res) => {
  const sp = scopeParam(req)!;
  res.json(getScope(sp.scope, sp.id));
});
app.patch("/api/scope/:scope/:id/sync", requireAuth, requireScopeManager, (req, res) => {
  const sp = scopeParam(req)!;
  const me = getScope(sp.scope, sp.id);
  if (req.body?.syncMode) me.syncMode = req.body.syncMode;
  // 切回 auto 清空快照；切到 manual 自动快照一次
  if (me.syncMode === "auto") me.manualBase = undefined;
  else if (me.syncMode === "manual" && !me.manualBase) {
    const parent = scopeChain(sp.scope, sp.id)!.slice(0, -1);
    refreshManual(sp.scope, sp.id, parent);
  }
  scopeLog(req, "同步设置", sp.id, `${me.syncMode}`);
  res.json(me);
});
app.post("/api/scope/:scope/:id/refresh", requireAuth, requireScopeManager, (req, res) => {
  const sp = scopeParam(req)!;
  const parent = scopeChain(sp.scope, sp.id)!.slice(0, -1);
  refreshManual(sp.scope, sp.id, parent);
  scopeLog(req, "手动刷新同步", sp.id, new Date().toISOString());
  res.json(getScope(sp.scope, sp.id));
});

function scopeLog(req: Request, action: string, targetId: string, targetName: string) {
  const u = (req as any).user;
  if (!u) return;
  addLog({ actorId: u.uid, actorName: u.u, actorRole: u.role, action: "scope_content", targetType: "content", targetId, targetName, detail: action });
}

// ---------- gradeadmin：概览 ----------
app.get("/api/grade/overview", requireAuth, requireGradeAdmin, (req, res) => {
  const u = currentUser(req)!;
  const myGrades = (u.gradeIds || []).map((gid) => {
    const g = findGrade(gid);
    const cls = listClasses(g?.schoolId, gid);
    const schoolUsers = listUsers().filter((x) => x.schoolId === g?.schoolId);
    return {
      id: gid, name: g?.name,
      classCount: cls.length,
      classes: cls.map((c) => ({ id: c.id, name: c.name, studentCount: schoolUsers.filter((s) => s.role === "student" && s.classId === c.id).length })),
      teacherCount: schoolUsers.filter((t) => t.role === "teacher" && (t.gradeIds || []).includes(gid)).length,
      studentCount: cls.reduce((n, c) => n + schoolUsers.filter((s) => s.role === "student" && s.classId === c.id).length, 0),
    };
  });
  res.json({ grades: myGrades });
});
app.get("/api/grade/classes", requireAuth, requireGradeAdmin, (req, res) => {
  const u = currentUser(req)!;
  const list = (u.gradeIds || []).flatMap((gid) => listClasses(findGrade(gid)?.schoolId, gid));
  res.json(list.map((c) => ({ ...c, gradeName: findGrade(c.gradeId)?.name })));
});
app.get("/api/grade/users", requireAuth, requireGradeAdmin, (req, res) => {
  const u = currentUser(req)!;
  const role = req.query.role as string | undefined;
  const schoolUsers = listUsers().filter((x) => x.schoolId === u.schoolId);
  let list = schoolUsers.filter((x) =>
    (x.role === "teacher" && (x.gradeIds || []).some((g) => (u.gradeIds || []).includes(g))) ||
    (x.role === "student" && x.classId && listClasses(u.schoolId).some((c) => c.id === x.classId && (u.gradeIds || []).includes(c.gradeId)))
  );
  if (role) list = list.filter((x) => x.role === role);
  res.json(list.map((x) => ({ ...publicUser(x), className: x.classId ? findClass(x.classId)?.name : x.className })));
});

// ---------- teacher：班级内容入口（复用通用 scope，仅需 teacher 持有 classIds） ----------
// 现有 /api/teacher/* 保留；新增"我的班级"列表便于选择
app.get("/api/teacher/my-classes", requireAuth, requireRole("teacher"), (req, res) => {
  const u = currentUser(req)!;
  const list = (u.classIds || []).map((cid) => {
    const c = findClass(cid);
    return c ? { ...c, gradeName: findGrade(c.gradeId)?.name, studentCount: listUsers().filter((s) => s.role === "student" && s.classId === cid).length } : null;
  }).filter(Boolean);
  res.json(list);
});

// ---------- 学生侧：继承内容接线 ----------
// 见下方既有 /api/knowledge-graph 等路由（已改为按学生 classId 返回有效集）

const PORT = 3001;
app.listen(PORT, () => console.log(`[klces-backend] http://localhost:${PORT}`));
