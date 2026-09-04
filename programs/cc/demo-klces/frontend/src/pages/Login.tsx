import { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const from = (loc.state as { from?: string } | null)?.from;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const u = await login(username.trim(), password);
      nav(from || homeByRole(u.role), { replace: true });
    } catch (e: any) {
      setErr(e?.response?.data?.message || "登录失败，请检查用户名与密码");
    } finally { setBusy(false); }
  }

  function homeByRole(r: string) {
    if (r === "student") return "/";
    if (r === "teacher") return "/teacher";
    if (r === "schooladmin") return "/school";
    if (r === "gradeadmin") return "/grade";
    if (r === "bizadmin") return "/admin/knowledge";
    if (r === "secadmin") return "/admin/roles";
    if (r === "audadmin") return "/admin/audit";
    return "/admin/users";
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <div className="text-3xl">📚</div>
          <h1 className="text-xl font-bold text-slate-900 mt-2">高中语文学习评价系统</h1>
          <p className="text-xs text-slate-500 mt-1">知识学习完备度评价</p>
        </div>

        <form onSubmit={submit} className="bg-white rounded-2xl shadow-sm p-6 space-y-4">
          <div>
            <label className="text-xs text-slate-500">用户名</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username"
              className="w-full mt-1 px-3 py-2.5 rounded-lg border border-slate-200 text-sm focus:border-brand-500 outline-none" placeholder="输入用户名" />
          </div>
          <div>
            <label className="text-xs text-slate-500">密码</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
              className="w-full mt-1 px-3 py-2.5 rounded-lg border border-slate-200 text-sm focus:border-brand-500 outline-none" placeholder="输入密码" />
          </div>
          {err && <div className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{err}</div>}
          <button type="submit" disabled={busy}
            className="w-full py-2.5 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 disabled:opacity-50">
            {busy ? "登录中…" : "登 录"}
          </button>
          <div className="flex justify-between text-xs text-slate-400">
            <Link to="/register" className="text-brand-600 hover:underline">没有账号？注册</Link>
            <Link to="/" className="hover:underline">先体验学生端</Link>
          </div>
        </form>

        <div className="mt-4 bg-slate-50 rounded-xl p-3 text-xs text-slate-500 space-y-1">
          <div className="font-medium text-slate-600">演示账号</div>
          <div>学生 student / 123456</div>
          <div>教师 teacher / 123456</div>
          <div>学校管理员 schooladmin / 123456</div>
          <div>年级管理员 gradeadmin / 123456</div>
          <div>业务管理员 bizadmin / admin123</div>
          <div>系统管理员 sysadmin / admin123</div>
          <div>安全管理员 secadmin / admin123</div>
          <div>审计管理员 audadmin / admin123</div>
        </div>
      </div>
    </div>
  );
}
