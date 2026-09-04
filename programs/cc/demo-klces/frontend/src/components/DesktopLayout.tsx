import { useMemo, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth, ROLE_LABEL } from "../auth/AuthContext";

interface NavItem { to: string; label: string; icon: string; }
const NAV: { section: string; items: NavItem[] }[] = [
  { section: "教师端", items: [
    { to: "/teacher", label: "班级学情总览", icon: "📊", role: "teacher" } as any,
    { to: "/teacher/assessments", label: "班级测评管理", icon: "📝", role: "teacher" } as any,
    { to: "/teacher/knowledge", label: "班级知识/题库", icon: "📚", role: "teacher" } as any,
  ]},
  { section: "学校管理", items: [
    { to: "/school", label: "学校概览", icon: "🏫", role: "schooladmin" } as any,
    { to: "/school/users", label: "用户与授权", icon: "👥", role: "schooladmin" } as any,
    { to: "/school/structure", label: "年级/班级", icon: "🗂️", role: "schooladmin" } as any,
    { to: "/school/knowledge", label: "学校知识图谱", icon: "🧠", role: "schooladmin" } as any,
    { to: "/school/questions", label: "学校题库", icon: "📦", role: "schooladmin" } as any,
  ]},
  { section: "年级管理", items: [
    { to: "/grade", label: "年级概览", icon: "📐", role: "gradeadmin" } as any,
    { to: "/grade/knowledge", label: "年级知识图谱", icon: "🧠", role: "gradeadmin" } as any,
    { to: "/grade/questions", label: "年级题库", icon: "📦", role: "gradeadmin" } as any,
  ]},
  { section: "管理后台", items: [
    { to: "/admin/school-approvals", label: "学校管理员审批", icon: "✅", role: "bizadmin" } as any,
    { to: "/admin/users", label: "用户生命周期", icon: "👥", role: "sysadmin" } as any,
    { to: "/admin/roles", label: "角色与权限", icon: "🔐", role: "secadmin" } as any,
    { to: "/admin/audit", label: "审计日志", icon: "📜", role: "audadmin" } as any,
    { to: "/admin/knowledge", label: "知识图谱管理", icon: "🗂️", role: "bizadmin" } as any,
    { to: "/admin/questions", label: "题库管理", icon: "📚", role: "bizadmin" } as any,
  ]},
];

export default function DesktopLayout() {
  const { pathname } = useLocation();
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(false);

  // 按角色过滤可见导航
  const navView = useMemo(() => NAV.map((g) => ({
    ...g,
    items: g.items.filter((it: any) => !it.role || it.role === user?.role),
  })).filter((g) => g.items.length > 0), [user?.role]);

  return (
    <div className="min-h-screen flex bg-slate-100 text-slate-800">
      {open && <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setOpen(false)} />}

      <aside className={`fixed md:static z-40 w-60 h-full md:h-auto md:min-h-screen bg-slate-900 text-slate-300 flex flex-col flex-shrink-0 transition-transform duration-200 ${open ? "translate-x-0" : "-translate-x-full md:translate-x-0"}`}>
        <div className="px-5 py-4 border-b border-slate-700/50 flex items-center justify-between">
          <div>
            <div className="text-white font-bold text-base">语文学习评价</div>
            <div className="text-xs text-slate-500 mt-0.5">{user ? ROLE_LABEL[user.role] : "工作台"}</div>
          </div>
          <button className="md:hidden text-slate-400 text-xl" onClick={() => setOpen(false)}>×</button>
        </div>
        <nav className="flex-1 overflow-y-auto py-3">
          {navView.map((g) => (
            <div key={g.section} className="mb-4">
              <div className="px-5 text-xs text-slate-500 uppercase tracking-wide mb-1">{g.section}</div>
              {g.items.map((it) => {
                const active = pathname === it.to || pathname.startsWith(it.to + "/");
                return (
                  <Link key={it.to} to={it.to} onClick={() => setOpen(false)}
                    className={`flex items-center gap-2 px-5 py-2 text-sm ${active ? "bg-brand-600 text-white border-l-2 border-brand-400" : "hover:bg-slate-800"}`}>
                    <span>{it.icon}</span>{it.label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="px-5 py-3 border-t border-slate-700/50 text-xs text-slate-500">
          <Link to="/" className="hover:text-slate-300">← 返回学生端</Link>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 bg-white border-b border-slate-200 flex items-center px-4 md:px-6 shadow-sm sticky top-0 z-20">
          <button className="md:hidden mr-3 text-slate-600 text-xl" onClick={() => setOpen(true)}>☰</button>
          <h1 className="font-medium text-slate-900 truncate">{currentTitle(pathname)}</h1>
          <div className="ml-auto flex items-center gap-3">
            {/* 账户菜单 */}
            <div className="relative">
              <button onClick={() => setMenu((v) => !v)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-slate-100 text-sm text-slate-600">
                <span className="w-7 h-7 rounded-full bg-brand-500 text-white grid place-items-center text-xs font-bold">
                  {user?.name?.slice(0, 1) || "?"}
                </span>
                <span className="hidden sm:block">{user?.name}</span>
                <span className="text-xs text-slate-400">▾</span>
              </button>
              {menu && (
                <>
                  <div className="fixed inset-0 z-30" onClick={() => setMenu(false)} />
                  <div className="absolute right-0 top-full mt-1 w-48 bg-white rounded-lg shadow-lg border border-slate-200 py-1 z-40 text-sm">
                    <div className="px-3 py-2 border-b border-slate-100">
                      <div className="font-medium text-slate-800">{user?.name}</div>
                      <div className="text-xs text-slate-400">{user ? ROLE_LABEL[user.role] : ""} · {user?.username}</div>
                    </div>
                    <button onClick={() => { setMenu(false); nav("/account"); }}
                      className="w-full text-left px-3 py-2 hover:bg-slate-50 text-slate-600">账号设置</button>
                    <button onClick={logout}
                      className="w-full text-left px-3 py-2 hover:bg-red-50 text-red-600">退出登录</button>
                  </div>
                </>
              )}
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function currentTitle(p: string) {
  if (p.startsWith("/teacher/assessments")) return "班级测评管理";
  if (p.startsWith("/teacher/knowledge")) return "班级知识/题库";
  if (p.startsWith("/teacher/student")) return "学生个人学情";
  if (p.startsWith("/teacher")) return "班级学情总览";
  if (p.startsWith("/school/users")) return "用户与授权";
  if (p.startsWith("/school/structure")) return "年级/班级管理";
  if (p.startsWith("/school/knowledge")) return "学校知识图谱";
  if (p.startsWith("/school/questions")) return "学校题库";
  if (p.startsWith("/school")) return "学校概览";
  if (p.startsWith("/grade/knowledge")) return "年级知识图谱";
  if (p.startsWith("/grade/questions")) return "年级题库";
  if (p.startsWith("/grade")) return "年级概览";
  if (p.startsWith("/admin/school-approvals")) return "学校管理员审批";
  if (p.startsWith("/admin/users")) return "用户生命周期管理";
  if (p.startsWith("/admin/roles")) return "角色与权限分配";
  if (p.startsWith("/admin/audit")) return "审计日志";
  if (p.startsWith("/admin/knowledge")) return "知识图谱管理";
  if (p.startsWith("/admin/questions")) return "题库管理";
  if (p.startsWith("/account")) return "账号设置";
  return "工作台";
}
