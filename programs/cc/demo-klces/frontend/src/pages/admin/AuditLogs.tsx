import { useEffect, useState } from "react";
import { get } from "../../api/client";
import { useAuth, ROLE_LABEL, Role } from "../../auth/AuthContext";
import { Panel, PanelHeader, Pill, Spinner, Empty } from "../../components/desktop";

interface Log {
  id: string; time: string; actorId: string; actorName: string; actorRole: Role;
  action: string; targetType: string; targetId: string; targetName: string; detail: string;
}

export default function AuditLogs() {
  const { user: me } = useAuth();
  const [rows, setRows] = useState<Log[]>([]);
  const [loading, setLoading] = useState(true);
  const [kw, setKw] = useState("");
  const [action, setAction] = useState("");
  const [all, setAll] = useState<Log[]>([]);

  useEffect(() => {
    get<Log[]>("/audit-logs").then((d) => { setAll(d); setRows(d); }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const actions = Array.from(new Set(all.map((l) => l.action)));

  useEffect(() => {
    let r = all;
    if (kw) r = r.filter((l) => l.actorName.includes(kw) || l.targetName.includes(kw) || l.detail.includes(kw));
    if (action) r = r.filter((l) => l.action === action);
    setRows(r);
  }, [kw, action, all]);

  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader title="审计日志" action={<span className="text-xs text-slate-400">审计管理员 · 只读</span>} />
        <div className="px-5 py-3 flex flex-wrap gap-2 items-center">
          <input value={kw} onChange={(e) => setKw(e.target.value)} placeholder="操作人/对象/详情"
            className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 outline-none focus:border-brand-500 w-44" />
          <select value={action} onChange={(e) => setAction(e.target.value)}
            className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 bg-white outline-none">
            <option value="">全部操作</option>
            {actions.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
          <div className="ml-auto text-xs text-slate-400">{rows.length} 条</div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs">
              <tr>
                <th className="text-left px-5 py-2 font-medium">时间</th>
                <th className="text-left px-3 py-2 font-medium">操作人</th>
                <th className="text-left px-3 py-2 font-medium">操作</th>
                <th className="text-left px-3 py-2 font-medium">对象</th>
                <th className="text-left px-5 py-2 font-medium">详情</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={5}><Spinner /></td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={5}><Empty text="无匹配日志" /></td></tr>
              ) : rows.map((l) => (
                <tr key={l.id} className="border-t border-slate-100 align-top">
                  <td className="px-5 py-2.5 text-xs text-slate-500 whitespace-nowrap">{l.time.replace("T", " ").slice(0, 19)}</td>
                  <td className="px-3 py-2.5">
                    <div className="text-slate-800">{l.actorName}</div>
                    <div className="text-xs text-slate-400">{ROLE_LABEL[l.actorRole]}</div>
                  </td>
                  <td className="px-3 py-2.5"><Pill color="brand">{l.action}</Pill></td>
                  <td className="px-3 py-2.5 text-slate-600">{l.targetName}<div className="text-xs text-slate-400">{l.targetType}</div></td>
                  <td className="px-5 py-2.5 text-slate-600 max-w-xs">{l.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="text-xs text-slate-400 px-1">
        {me?.role === "sysadmin"
          ? "提示：作为系统管理员，您仅能查阅与本账号相关的审计记录。"
          : "审计日志为只读，确保操作可追溯、不可篡改。"}
      </div>
    </div>
  );
}
