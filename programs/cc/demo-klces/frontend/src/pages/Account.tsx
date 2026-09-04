import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, ROLE_LABEL } from "../auth/AuthContext";
import { Panel, PanelHeader } from "../components/desktop";

export default function Account() {
  const { user, changePassword, logout } = useAuth();
  const nav = useNavigate();
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg("");
    if (newPw.length < 6) { setMsg("新密码至少 6 位"); return; }
    if (newPw !== confirm) { setMsg("两次新密码不一致"); return; }
    setBusy(true);
    try { await changePassword(oldPw, newPw); setOldPw(""); setNewPw(""); setConfirm(""); setMsg("密码修改成功"); }
    catch (e: any) { setMsg(e?.response?.data?.message || "修改失败，请检查原密码"); }
    setBusy(false);
  }

  return (
    <div className="max-w-lg mx-auto space-y-4">
      <Panel>
        <PanelHeader title="账号信息" />
        <div className="px-5 py-4 space-y-2 text-sm">
          <Row k="姓名" v={user?.name} />
          <Row k="用户名" v={user?.username} />
          <Row k="角色" v={user ? ROLE_LABEL[user.role] : ""} />
          <Row k="年级/班级" v={[user?.grade, user?.className].filter(Boolean).join(" · ") || "—"} />
          <Row k="邮箱" v={user?.email || "—"} />
          <Row k="最近登录" v={user?.lastLogin ? user.lastLogin.replace("T", " ").slice(0, 16) : "—"} />
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="修改密码" />
        <form onSubmit={submit} className="px-5 py-4 space-y-3 text-sm">
          <div>
            <label className="text-xs text-slate-500">原密码</label>
            <input type="password" value={oldPw} onChange={(e) => setOldPw(e.target.value)}
              className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-brand-500 outline-none" />
          </div>
          <div>
            <label className="text-xs text-slate-500">新密码（≥6位）</label>
            <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)}
              className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-brand-500 outline-none" />
          </div>
          <div>
            <label className="text-xs text-slate-500">确认新密码</label>
            <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
              className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-brand-500 outline-none" />
          </div>
          {msg && <div className="text-xs text-brand-600 bg-brand-50 rounded-lg px-3 py-2">{msg}</div>}
          <button type="submit" disabled={busy}
            className="px-3.5 py-1.5 text-sm font-medium rounded-lg bg-brand-500 text-white hover:bg-brand-600 disabled:opacity-40">
            {busy ? "提交中…" : "修改密码"}
          </button>
        </form>
      </Panel>

      <div className="flex justify-between">
        <button onClick={() => nav(-1)} className="text-sm text-slate-500 hover:text-slate-700">← 返回</button>
        <button onClick={logout} className="text-sm text-red-500 hover:text-red-600">退出登录</button>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v?: React.ReactNode }) {
  return <div className="flex"><span className="w-24 text-slate-400">{k}</span><span className="flex-1 text-slate-700">{v}</span></div>;
}
