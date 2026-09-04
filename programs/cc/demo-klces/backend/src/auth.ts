// 账户、鉴权、生命周期、审计与三权分立内置管理员
import { randomBytes, scryptSync, timingSafeEqual, createHmac } from "crypto";

export type Role = "student" | "teacher" | "schooladmin" | "gradeadmin" | "bizadmin" | "sysadmin" | "secadmin" | "audadmin";
export type UserStatus = "pending" | "active" | "suspended" | "deactivated";

export interface User {
  id: string;
  username: string;
  name: string;
  role: Role;
  salt: string;
  passwordHash: string;
  status: UserStatus;
  className?: string;
  grade?: string;
  email?: string;
  phone?: string;
  createdAt: string;
  createdBy: string;       // 创建者 id（self / sysadmin 等）
  builtin?: boolean;       // 内置管理员不可删除
  lastLogin?: string;
  // ---- 学校层级体系字段 ----
  idNumber?: string;        // 身份证号
  schoolId?: string;        // 所属学校
  gradeIds?: string[];      // gradeadmin / teacher 所辖年级
  classIds?: string[];      // teacher 所辖班级
  classId?: string;         // student 所属班级
  studentNo?: string;      // 学生学号
}

export interface AuditLog {
  id: string;
  time: string;
  actorId: string;
  actorName: string;
  actorRole: Role;
  action: string;          // register/approve/suspend/activate/deactivate/reset_password/role_change/policy_change/login
  targetType: string;      // user / policy
  targetId: string;
  targetName: string;
  detail: string;
}

const SECRET = "klces-secret-2026-change-in-prod";
const users = new Map<string, User>();
const logs: AuditLog[] = [];
let userSeq = 0, logSeq = 0;

// ---------- 密码 ----------
export function hashPassword(password: string): { salt: string; hash: string } {
  const salt = randomBytes(16).toString("hex");
  const hash = scryptSync(password, salt, 64).toString("hex");
  return { salt, hash };
}
export function verifyPassword(password: string, salt: string, hash: string): boolean {
  try {
    const h = scryptSync(password, salt, 64);
    return timingSafeEqual(h, Buffer.from(hash, "hex"));
  } catch { return false; }
}

// ---------- 令牌（HMAC-SHA256 签名） ----------
export function signToken(user: User): string {
  const payload = { uid: user.id, role: user.role, u: user.username };
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const sig = createHmac("sha256", SECRET).update(body).digest("base64url");
  return `${body}.${sig}`;
}
export function verifyToken(token: string): { uid: string; role: Role; u: string } | null {
  const [body, sig] = token.split(".");
  if (!body || !sig) return null;
  const expect = createHmac("sha256", SECRET).update(body).digest("base64url");
  if (sig !== expect) return null;
  try {
    const p = JSON.parse(Buffer.from(body, "base64url").toString());
    return p as { uid: string; role: Role; u: string };
  } catch { return null; }
}

// ---------- 用户存储访问 ----------
export function listUsers() { return [...users.values()]; }
export function findUser(id: string) { return users.get(id) || null; }
export function findUserByName(username: string) {
  for (const u of users.values()) if (u.username === username) return u;
  return null;
}
export function saveUser(u: User) { users.set(u.id, u); }
export function deleteUser(id: string) { users.delete(id); }
export function nextUserId() { return `u${++userSeq}`; }

// ---------- 审计 ----------
export function addLog(entry: Omit<AuditLog, "id" | "time">) {
  logs.push({ id: `log${++logSeq}`, time: new Date().toISOString(), ...entry });
}
export function listLogs() { return [...logs].reverse(); }

// ---------- 安全策略 ----------
export const securityPolicy = {
  minPasswordLength: 6,
  requireApproval: false,        // 注册是否需审批（false=自动激活）
  allowSelfRegister: true,
};
export function getPolicy() { return { ...securityPolicy }; }
export function setPolicy(patch: Partial<typeof securityPolicy>) {
  Object.assign(securityPolicy, patch);
}

// ---------- 三权分立内置管理员种子 ----------
// 默认密码：admin123（首次登录后建议修改，但原型不强制）
export function seedAdmin() {
  const seed: Array<[string, string, Role, string]> = [
    ["bizadmin", "业务管理员", "bizadmin", "业务管理员：知识图谱与题库等业务内容管理（不涉账户/角色/审计）"],
    ["sysadmin", "系统管理员", "sysadmin", "系统管理员：用户生命周期（审批/启用/停用/注销/重置密码）"],
    ["secadmin", "安全管理员", "secadmin", "安全管理员：角色与权限分配、安全策略"],
    ["audadmin", "审计管理员", "audadmin", "审计管理员：审计日志只读查阅"],
  ];
  for (const [username, name, role, _desc] of seed) {
    if (findUserByName(username)) continue;
    const { salt, hash } = hashPassword("admin123");
    const u: User = {
      id: nextUserId(), username, name, role, salt, passwordHash: hash,
      status: "active", createdAt: new Date().toISOString(), createdBy: "system",
      builtin: true, email: `${username}@klces.edu`,
    };
    saveUser(u);
  }
  // 预置一个学生与一个教师演示账号，绑定现有演示数据
  if (!findUserByName("student")) {
    const { salt, hash } = hashPassword("123456");
    saveUser({
      id: nextUserId(), username: "student", name: "李同学", role: "student", salt, passwordHash: hash,
      status: "active", grade: "高二", className: "高二(1)班", createdAt: new Date().toISOString(), createdBy: "system",
    });
  }
  if (!findUserByName("teacher")) {
    const { salt, hash } = hashPassword("123456");
    saveUser({
      id: nextUserId(), username: "teacher", name: "王老师", role: "teacher", salt, passwordHash: hash,
      status: "active", className: "高二(1)班", createdAt: new Date().toISOString(), createdBy: "system",
    });
  }
}

// ---------- 角色中文 ----------
export const ROLE_LABEL: Record<Role, string> = {
  student: "学生", teacher: "教师", schooladmin: "学校管理员", gradeadmin: "年级管理员", bizadmin: "业务管理员", sysadmin: "系统管理员", secadmin: "安全管理员", audadmin: "审计管理员",
};
export const STATUS_LABEL: Record<UserStatus, string> = {
  pending: "待审批", active: "正常", suspended: "已停用", deactivated: "已注销",
};

export function publicUser(u: User) {
  return {
    id: u.id, username: u.username, name: u.name, role: u.role, status: u.status,
    className: u.className, grade: u.grade, email: u.email, phone: u.phone,
    createdAt: u.createdAt, builtin: !!u.builtin, lastLogin: u.lastLogin,
    idNumber: u.idNumber, schoolId: u.schoolId,
    gradeIds: u.gradeIds, classIds: u.classIds, classId: u.classId, studentNo: u.studentNo,
  };
}
