import { ReactNode, useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth, Role } from "./AuthContext";

// 需登录
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <div className="min-h-screen grid place-items-center text-slate-400 text-sm">加载中…</div>;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  return <>{children}</>;
}

// 需特定角色（三权分立：不同角色进入不同后台）
export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <div className="min-h-screen grid place-items-center text-slate-400 text-sm">加载中…</div>;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  if (!roles.includes(user.role)) {
    // 角色不匹配 → 跳到该用户默认首页
    return <Navigate to={homeOf(user.role)} replace />;
  }
  return <>{children}</>;
}

export function homeOf(role: Role): string {
  switch (role) {
    case "student": return "/";
    case "teacher": return "/teacher";
    case "schooladmin": return "/school";
    case "gradeadmin": return "/grade";
    case "bizadmin": return "/admin/knowledge";
    case "sysadmin": return "/admin/users";
    case "secadmin": return "/admin/roles";
    case "audadmin": return "/admin/audit";
  }
}
