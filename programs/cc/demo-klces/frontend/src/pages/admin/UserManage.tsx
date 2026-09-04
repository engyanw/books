import { useEffect, useState } from "react";
import { api, get, patch, del } from "../../api/client";
import { useAuth, ROLE_LABEL, STATUS_LABEL, Role, UserStatus, AuthUser } from "../../auth/AuthContext";
import { Panel, PanelHeader, Pill, DButton, Spinner, Empty } from "../../components/desktop";

interface UserRow extends AuthUser {}

export default function UserManage() {
  const { user: me } = useAuth();
  const [rows, setRows] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [kw, setKw] = useState("");
  const [role, setRole] = useState<"" | Role>("");
  const [status, setStatus] = useState<"" | UserStatus>("");
  const [detail, setDetail] = useState<UserRow | null>(null);
  const [busy, setBusy] = useState(false);

  async function reload() {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (kw) params.keyword = kw;
      if (role) params.role = role;
      if (status) params.status = status;
      const d = await get<UserRow[]>("/users", params);
      setRows(d);
    } catch { /* handled by interceptor */ }
    setLoading(false);
  }
  useEffect(() => { reload(); }, [role, status]); // eslint-disable-line

  async function setStatusOf(u: UserRow, s: UserStatus) {
    setBusy(true);
    try {
      const upd = await patch<UserRow>(`/users/${u.id}/status`, { status: s });
      setRows((r) => r.map((x) => (x.id === u.id ? upd : x)));
      setDetail(upd);
    } catch (e: any) { alert(e?.response?.data?.message || "操作失败"); }
    setBusy(false);
  }

  async function resetPw(u: UserRow) {
    if (!confirm(`确认将 ${u.name} 的密码重置为 123456？`)) return;
    setBusy(true);
    try { await patch(`/users/${u.id}/reset-password`, { password: "123456" }); alert("密码已重置为 123456"); }
    catch (e: any) { alert(e?.response?.data?.message || "重置失败"); }
    setBusy(false);
  }

  async function remove(u: UserRow) {
    if (!confirm(`确认注销并删除用户 ${u.name}（${u.username}）？此操作不可恢复。`)) return;
    setBusy(true);
    try {
      await del(`/users/${u.id}`);
      setRows((r) => r.filter((x) => x.id !== u.id));
      setDetail(null);
    } catch (e: any) { alert(e?.response?.data?.message || "删除失败"); }
    setBusy(false);
  }

  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader title="用户生命周期管理" action={<span className="text-xs text-slate-400">系统管理员</span>} />
        <div className="px-5 py-3 flex flex-wrap gap-2 items-center">
          <input value={kw} onChange={(e) => setKw(e.target.value)} placeholder="用户名/姓名"
            className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 outline-none focus:border-brand-500 w-40" />
          <select value={role} onChange={(e) => setRole(e.target.value as any)}
            className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 bg-white outline-none">
            <option value="">全部角色</option>
            {Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value as any)}
            className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 bg-white outline-none">
            <option value="">全部状态</option>
            {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <DButton size="sm" variant="outline" onClick={reload}>查询</DButton>
          <div className="ml-auto text-xs text-slate-400">共 {rows.length} 人</div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs">
              <tr>
                <th className="text-left px-5 py-2 font-medium">用户</th>
                <th className="text-left px-3 py-2 font-medium">角色</th>
                <th className="text-left px-3 py-2 font-medium">状态</th>
                <th className="text-left px-3 py-2 font-medium hidden md:table-cell">班级</th>
                <th className="text-left px-3 py-2 font-medium hidden lg:table-cell">创建时间</th>
                <th className="text-right px-5 py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6}><Spinner /></td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={6}><Empty /></td></tr>
              ) : rows.map((u) => (
                <tr key={u.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-5 py-2.5">
                    <div className="font-medium text-slate-800 flex items-center gap-1.5">
                      {u.name}
                      {u.builtin && <Pill color="amber">内置</Pill>}
                    </div>
                    <div className="text-xs text-slate-400">{u.username}</div>
                  </td>
                  <td className="px-3 py-2.5">{ROLE_LABEL[u.role]}</td>
                  <td className="px-3 py-2.5"><StatusPill s={u.status} /></td>
                  <td className="px-3 py-2.5 hidden md:table-cell text-slate-600">{u.className || u.grade || "—"}</td>
                  <td className="px-3 py-2.5 hidden lg:table-cell text-xs text-slate-400">{u.createdAt.slice(0, 10)}</td>
                  <td className="px-5 py-2.5 text-right">
                    <DButton size="sm" variant="ghost" onClick={() => setDetail(u)}>详情</DButton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {detail && (
        <Panel>
          <PanelHeader title={`账号详情 · ${detail.name}`} action={
            <DButton size="sm" variant="ghost" onClick={() => setDetail(null)}>关闭</DButton>
          } />
          <div className="px-5 py-4 space-y-3 text-sm">
            <Row k="用户名" v={detail.username} />
            <Row k="角色" v={ROLE_LABEL[detail.role]} />
            <Row k="状态" v={<StatusPill s={detail.status} />} />
            <Row k="年级/班级" v={[detail.grade, detail.className].filter(Boolean).join(" · ") || "—"} />
            <Row k="邮箱" v={detail.email || "—"} />
            <Row k="手机" v={detail.phone || "—"} />
            <Row k="创建时间" v={detail.createdAt.replace("T", " ").slice(0, 16)} />
            <Row k="最近登录" v={detail.lastLogin ? detail.lastLogin.replace("T", " ").slice(0, 16) : "—"} />

            <div className="pt-2 border-t border-slate-100 flex flex-wrap gap-2">
              {detail.status !== "active" && (
                <DButton size="sm" variant="primary" disabled={busy} onClick={() => setStatusOf(detail, "active")}>启用</DButton>
              )}
              {detail.status === "active" && (
                <DButton size="sm" variant="outline" disabled={busy} onClick={() => setStatusOf(detail, "suspended")}>停用</DButton>
              )}
              {detail.status !== "deactivated" && (
                <DButton size="sm" variant="outline" disabled={busy} onClick={() => setStatusOf(detail, "deactivated")}>注销</DButton>
              )}
              <DButton size="sm" variant="ghost" disabled={busy} onClick={() => resetPw(detail)}>重置密码</DButton>
              {!detail.builtin && (
                <DButton size="sm" variant="danger" disabled={busy} onClick={() => remove(detail)}>删除用户</DButton>
              )}
              {detail.builtin && <span className="text-xs text-slate-400 self-center">内置管理员不可删除</span>}
              {me && detail.id === me.id && <span className="text-xs text-slate-400 self-center">（当前账号，部分操作受限）</span>}
            </div>
          </div>
        </Panel>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return <div className="flex"><span className="w-24 text-slate-400">{k}</span><span className="flex-1 text-slate-700">{v}</span></div>;
}

function StatusPill({ s }: { s: UserStatus }) {
  const color = s === "active" ? "green" : s === "suspended" ? "amber" : s === "deactivated" ? "red" : "slate";
  return <Pill color={color as any}>{STATUS_LABEL[s]}</Pill>;
}
