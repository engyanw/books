import { useEffect, useState } from "react";
import { get, patch } from "../../api/client";
import { useAuth, ROLE_LABEL, Role, AuthUser } from "../../auth/AuthContext";
import { Panel, PanelHeader, Pill, DButton, Spinner, Empty } from "../../components/desktop";

interface Policy { minPasswordLength: number; requireApproval: boolean; allowSelfRegister: boolean; }

export default function RoleManage() {
  const { user: me } = useAuth();
  const [rows, setRows] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [busy, setBusy] = useState(false);

  async function reload() {
    setLoading(true);
    try {
      const [users, p] = await Promise.all([get<AuthUser[]>("/users"), get<Policy>("/security/policy")]);
      setRows(users);
      setPolicy(p);
    } catch { /* interceptor */ }
    setLoading(false);
  }
  useEffect(() => { reload(); }, []);

  async function changeRole(u: AuthUser, role: Role) {
    if (role === u.role) return;
    if (u.builtin) { alert("内置管理员角色不可变更"); return; }
    setBusy(true);
    try {
      await patch(`/users/${u.id}/role`, { role });
      await reload();
    } catch (e: any) { alert(e?.response?.data?.message || "角色变更失败"); }
    setBusy(false);
  }

  async function savePolicy(patch_: Partial<Policy>) {
    setBusy(true);
    try { const p = await patch<Policy>("/security/policy", patch_); setPolicy(p); }
    catch (e: any) { alert(e?.response?.data?.message || "策略保存失败"); }
    setBusy(false);
  }

  const adminRoles: Role[] = ["sysadmin", "secadmin", "audadmin"];

  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader title="角色与权限分配" action={<span className="text-xs text-slate-400">安全管理员</span>} />
        <div className="px-5 py-3 text-xs text-slate-500">
          三权分立：系统管理员管生命周期 · 安全管理员管角色与策略 · 审计管理员管审计查阅，相互制约、不可越权。
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs">
              <tr>
                <th className="text-left px-5 py-2 font-medium">用户</th>
                <th className="text-left px-3 py-2 font-medium">当前角色</th>
                <th className="text-left px-3 py-2 font-medium">状态</th>
                <th className="text-left px-5 py-2 font-medium">分配/变更角色</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={4}><Spinner /></td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={4}><Empty /></td></tr>
              ) : rows.map((u) => (
                <tr key={u.id} className="border-t border-slate-100">
                  <td className="px-5 py-2.5">
                    <div className="font-medium text-slate-800 flex items-center gap-1.5">
                      {u.name}{u.builtin && <Pill color="amber">内置</Pill>}
                      {me && u.id === me.id && <Pill color="brand">自己</Pill>}
                    </div>
                    <div className="text-xs text-slate-400">{u.username}</div>
                  </td>
                  <td className="px-3 py-2.5 font-medium text-slate-700">{ROLE_LABEL[u.role]}</td>
                  <td className="px-3 py-2.5">
                    <Pill color={u.status === "active" ? "green" : "slate"}>{u.status === "active" ? "正常" : u.status}</Pill>
                  </td>
                  <td className="px-5 py-2.5">
                    <select
                      value={u.role}
                      disabled={busy || (u.builtin ?? false) || (me?.id === u.id)}
                      onChange={(e) => changeRole(u, e.target.value as Role)}
                      className="px-2 py-1 text-xs rounded-lg border border-slate-200 bg-white outline-none disabled:bg-slate-50 disabled:text-slate-400">
                      {Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </select>
                    {(u.builtin || me?.id === u.id) && <span className="text-xs text-slate-400 ml-2">不可变更</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="安全策略" />
        <div className="px-5 py-4 space-y-4 text-sm">
          {policy ? (
            <>
              <PolicyRow label="允许自助注册" desc="关闭后，学生/教师无法自助注册，需管理员创建账号"
                value={policy.allowSelfRegister} disabled={busy}
                onChange={(v) => savePolicy({ allowSelfRegister: v })} />
              <PolicyRow label="注册需审批" desc="开启后，新注册账号需系统管理员审批激活方可登录"
                value={policy.requireApproval} disabled={busy}
                onChange={(v) => savePolicy({ requireApproval: v })} />
              <div>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-slate-700">最小密码长度</div>
                    <div className="text-xs text-slate-400">注册与重置密码的最低长度要求</div>
                  </div>
                  <span className="text-lg font-bold text-brand-600">{policy.minPasswordLength}</span>
                </div>
                <input type="range" min={6} max={16} value={policy.minPasswordLength} disabled={busy}
                  onChange={(e) => setPolicy({ ...policy, minPasswordLength: +e.target.value })}
                  onMouseUp={() => policy && savePolicy({ minPasswordLength: policy.minPasswordLength })}
                  className="w-full mt-2 accent-brand-500" />
              </div>
            </>
          ) : <Spinner />}
        </div>
      </Panel>
    </div>
  );
}

function PolicyRow({ label, desc, value, onChange, disabled }: { label: string; desc: string; value: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1">
      <div>
        <div className="font-medium text-slate-700">{label}</div>
        <div className="text-xs text-slate-400">{desc}</div>
      </div>
      <button onClick={() => onChange(!value)} disabled={disabled}
        className={`relative w-11 h-6 rounded-full transition ${value ? "bg-brand-500" : "bg-slate-300"}`}>
        <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition ${value ? "left-5" : "left-0.5"}`} />
      </button>
    </div>
  );
}
