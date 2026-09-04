import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { post, get } from "../api/client";

export type Role = "student" | "teacher" | "schooladmin" | "gradeadmin" | "bizadmin" | "sysadmin" | "secadmin" | "audadmin";
export type UserStatus = "pending" | "active" | "suspended" | "deactivated";

export interface AuthUser {
  id: string;
  username: string;
  name: string;
  role: Role;
  status: UserStatus;
  className?: string;
  grade?: string;
  email?: string;
  phone?: string;
  createdAt: string;
  builtin?: boolean;
  lastLogin?: string;
  // 学校层级体系字段
  idNumber?: string;
  schoolId?: string;
  gradeIds?: string[];
  classIds?: string[];
  classId?: string;
  studentNo?: string;
}

interface AuthCtx {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<AuthUser>;
  register: (body: RegisterBody) => Promise<AuthUser>;
  logout: () => void;
  refresh: () => Promise<void>;
  changePassword: (oldPw: string, newPw: string) => Promise<void>;
}

export interface RegisterBody {
  username: string;
  password: string;
  name: string;
  role: "student" | "teacher" | "schooladmin" | "gradeadmin";
  // 学校层级
  schoolName?: string;       // schooladmin 新建学校
  schoolId?: string;          // gradeadmin/teacher/student 选择
  gradeId?: string;           // student 选择
  classId?: string;           // student 选择
  studentNo?: string;         // student
  idNumber?: string;          // 学校体系均填
  // 旧字段兼容
  grade?: string;
  className?: string;
  email?: string;
  phone?: string;
}

const Ctx = createContext<AuthCtx>(null as any);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // 启动时若有 token，恢复用户
  useEffect(() => {
    const tok = localStorage.getItem("klces_token");
    if (!tok) { setLoading(false); return; }
    get<{ user: AuthUser }>("/auth/me")
      .then((r) => setUser(r.user))
      .catch(() => { localStorage.removeItem("klces_token"); localStorage.removeItem("klces_user"); })
      .finally(() => setLoading(false));
  }, []);

  async function login(username: string, password: string) {
    const r = await post<{ token: string; user: AuthUser }>("/auth/login", { username, password });
    localStorage.setItem("klces_token", r.token);
    localStorage.setItem("klces_user", JSON.stringify(r.user));
    setUser(r.user);
    return r.user;
  }

  async function register(body: RegisterBody) {
    // 学校体系注册一律返回 pending（无 token），需相应管理员授权后方可登录
    const r = await post<{ ok: boolean; user: AuthUser; message?: string }>("/auth/register", body);
    return r.user;
  }

  function logout() {
    localStorage.removeItem("klces_token");
    localStorage.removeItem("klces_user");
    setUser(null);
    location.href = "/login";
  }

  async function refresh() {
    const r = await get<{ user: AuthUser }>("/auth/me");
    setUser(r.user);
  }

  async function changePassword(oldPw: string, newPw: string) {
    await post("/auth/change-password", { oldPassword: oldPw, newPassword: newPw });
  }

  return (
    <Ctx.Provider value={{ user, loading, login, register, logout, refresh, changePassword }}>
      {children}
    </Ctx.Provider>
  );
}

export const ROLE_LABEL: Record<Role, string> = {
  student: "学生", teacher: "教师", schooladmin: "学校管理员", gradeadmin: "年级管理员", bizadmin: "业务管理员", sysadmin: "系统管理员", secadmin: "安全管理员", audadmin: "审计管理员",
};

export const STATUS_LABEL: Record<UserStatus, string> = {
  pending: "待审批", active: "正常", suspended: "已停用", deactivated: "已注销",
};
