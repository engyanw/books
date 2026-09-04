import { useEffect, useState } from "react";
import { get, patch } from "../../api/client";
import { Panel, PanelHeader, Pill, DButton, Spinner, Empty } from "../../components/desktop";

interface PendingAdmin {
  id: string; username: string; name: string; status: string; createdAt: string;
  schoolName?: string; idNumber?: string; phone?: string; email?: string;
}

export default function SchoolApprovals() {
  const [rows, setRows] = useState<PendingAdmin[] | null>(null);
  const [busy, setBusy] = useState(false);

  async function reload() { setRows(await get<PendingAdmin[]>("/biz/pending-school-admins")); }
  useEffect(() => { reload(); }, []); // eslint-disable-line

  async function approve(u: PendingAdmin) {
    if (!confirm(`确认授权学校管理员 ${u.name}（学校：${u.schoolName || "—"}）？授权后该管理员可登录并管理本校。`)) return;
    setBusy(true);
    try { await patch(`/biz/school-admins/${u.id}/approve`); reload(); }
    catch (e: any) { alert(e?.response?.data?.error || "授权失败"); }
    setBusy(false);
  }

  return (
    <Panel>
      <PanelHeader title="学校管理员审批" action={<span className="text-xs text-slate-400">业务管理员</span>} />
      {!rows ? <Spinner /> : rows.length === 0 ? <Empty text="暂无待授权的学校管理员" /> : (
        <div className="divide-y divide-slate-100">
          {rows.map((u) => (
            <div key={u.id} className="px-5 py-3 flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-brand-100 text-brand-600 grid place-items-center text-sm font-bold">{u.name.slice(0, 1)}</div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-slate-800 flex items-center gap-2">{u.name} <Pill color="amber">待授权</Pill></div>
                <div className="text-xs text-slate-400">{u.username} · 身份证 {u.idNumber || "—"} · 申请学校 <b className="text-slate-600">{u.schoolName || "—"}</b></div>
              </div>
              <DButton size="sm" variant="primary" disabled={busy} onClick={() => approve(u)}>授权</DButton>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
