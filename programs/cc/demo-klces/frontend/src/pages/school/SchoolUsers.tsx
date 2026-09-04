import { useEffect, useState } from "react";
import { get, patch, post, del } from "../../api/client";
import { useAuth, ROLE_LABEL, STATUS_LABEL, Role, UserStatus, AuthUser } from "../../auth/AuthContext";
import { Panel, PanelHeader, Pill, DButton, Spinner, Empty } from "../../components/desktop";

interface SchoolUser extends AuthUser { gradeName?: string; className?: string; schoolName?: string; }
interface GradeOpt { id: string; name: string; classCount?: number }
interface ClassOpt { id: string; name: string; gradeName?: string; gradeId?: string }

export default function SchoolUsers() {
  const { user: me } = useAuth();
  const [rows, setRows] = useState<SchoolUser[] | null>(null);
  const [role, setRole] = useState<"" | Role>("");
  const [status, setStatus] = useState<"" | UserStatus>("");
  const [tab, setTab] = useState<"all" | "pending">("all");
  const [detail, setDetail] = useState<SchoolUser | null>(null);
  const [busy, setBusy] = useState(false);

  async function reload() {
    const params: Record<string, string> = {};
    if (role) params.role = role;
    if (status) params.status = status;
    const url = tab === "pending" ? "/school/pending" : "/school/users";
    setRows(await get<SchoolUser[]>(url, params));
  }
  useEffect(() => { reload(); }, [role, status, tab]); // eslint-disable-line

  async function setStatusOf(u: SchoolUser, s: UserStatus) {
    setBusy(true);
    try { const upd = await patch<SchoolUser>(`/school/users/${u.id}/status`, { status: s }); setRows((r) => r?.map((x) => (x.id === u.id ? upd : x)) || null); setDetail(upd); }
    catch (e: any) { alert(e?.response?.data?.error || "操作失败"); }
    setBusy(false);
  }
  async function resetPw(u: SchoolUser) {
    if (!confirm(`重置 ${u.name} 密码为 123456？`)) return;
    setBusy(true);
    try { await post(`/school/users/${u.id}/reset-password`); alert("已重置为 123456"); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }
  async function remove(u: SchoolUser) {
    if (!confirm(`删除用户 ${u.name}（${u.username}）？不可恢复。`)) return;
    setBusy(true);
    try { await del(`/school/users/${u.id}`); setRows((r) => r?.filter((x) => x.id !== u.id) || null); setDetail(null); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }

  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader title="用户与授权" action={
          <div className="flex gap-1 text-xs">
            <button onClick={() => setTab("all")} className={`px-2.5 py-1 rounded ${tab === "all" ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-500"}`}>全部</button>
            <button onClick={() => setTab("pending")} className={`px-2.5 py-1 rounded ${tab === "pending" ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-500"}`}>待授权</button>
          </div>
        } />
        <div className="px-5 py-3 flex flex-wrap gap-2 items-center">
          <select value={role} onChange={(e) => setRole(e.target.value as any)} className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 bg-white outline-none">
            <option value="">全部角色</option>
            {(["gradeadmin", "teacher", "student"] as const).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
          </select>
          {tab === "all" && (
            <select value={status} onChange={(e) => setStatus(e.target.value as any)} className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 bg-white outline-none">
              <option value="">全部状态</option>
              {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          )}
          <DButton size="sm" variant="outline" onClick={reload}>刷新</DButton>
          <div className="ml-auto text-xs text-slate-400">共 {rows?.length || 0} 人</div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs">
              <tr>
                <th className="text-left px-5 py-2 font-medium">用户</th>
                <th className="text-left px-3 py-2 font-medium">角色</th>
                <th className="text-left px-3 py-2 font-medium">状态</th>
                <th className="text-left px-3 py-2 font-medium hidden md:table-cell">范围</th>
                <th className="text-right px-5 py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {!rows ? <tr><td colSpan={5}><Spinner /></td></tr>
              : rows.length === 0 ? <tr><td colSpan={5}><Empty text="无用户" /></td></tr>
              : rows.map((u) => (
                <tr key={u.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-5 py-2.5">
                    <div className="font-medium text-slate-800">{u.name}</div>
                    <div className="text-xs text-slate-400">{u.username} · {u.idNumber || "—"}</div>
                  </td>
                  <td className="px-3 py-2.5">{ROLE_LABEL[u.role]}</td>
                  <td className="px-3 py-2.5"><StatusPill s={u.status} /></td>
                  <td className="px-3 py-2.5 hidden md:table-cell text-slate-600 text-xs">
                    {u.role === "gradeadmin" && u.gradeName}
                    {u.role === "teacher" && [u.gradeName, u.className].filter(Boolean).join(" / ")}
                    {u.role === "student" && u.className}
                  </td>
                  <td className="px-5 py-2.5 text-right">
                    {u.status === "pending"
                      ? <DButton size="sm" variant="primary" onClick={() => setDetail(u)}>授权</DButton>
                      : <DButton size="sm" variant="ghost" onClick={() => setDetail(u)}>详情</DButton>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {detail && (detail.status === "pending"
        ? <ApproveSheet key={detail.id} u={detail} me={me!} busy={busy} onClose={() => setDetail(null)} onDone={(u) => { setDetail(null); reload(); setTab("all"); }} />
        : <DetailSheet u={detail} busy={busy} onClose={() => setDetail(null)} onStatus={setStatusOf} onReset={resetPw} onDelete={remove} />
      )}
    </div>
  );
}

function ApproveSheet({ u, busy, onClose, onDone }: { u: SchoolUser; me: AuthUser; busy: boolean; onClose: () => void; onDone: (u: SchoolUser) => void }) {
  const [grades, setGrades] = useState<GradeOpt[]>([]);
  const [classes, setClasses] = useState<ClassOpt[]>([]);
  const [selGrades, setSelGrades] = useState<string[]>(u.gradeIds || []);
  const [selClasses, setSelClasses] = useState<string[]>(u.classIds || []);
  const [classId, setClassId] = useState(u.classId || "");
  const [studentNo, setStudentNo] = useState(u.studentNo || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    get<{ id: string; name: string; classCount?: number }[]>("/school/grades").then(setGrades).catch(() => {});
    get<ClassOpt[]>("/school/classes").then(setClasses).catch(() => {});
  }, []);

  const gradeClasses = (gid: string) => classes.filter((c) => c.gradeId === gid || c.gradeName === grades.find((g) => g.id === gid)?.name);

  async function approve() {
    setSaving(true);
    try {
      const body: Record<string, any> = {};
      if (u.role === "gradeadmin") body.gradeIds = selGrades;
      if (u.role === "teacher") { body.gradeIds = selGrades; body.classIds = selClasses; }
      if (u.role === "student") { if (classId) body.classId = classId; if (studentNo) body.studentNo = studentNo; }
      await patch(`/school/users/${u.id}/approve`, body);
      alert("授权成功，该用户现已可登录");
      onDone(u);
    } catch (e: any) { alert(e?.response?.data?.error || "授权失败"); }
    setSaving(false);
  }

  return (
    <Sheet title={`授权 · ${u.name}（${ROLE_LABEL[u.role]}）`} onClose={onClose}>
      {u.role === "gradeadmin" && (
        <div>
          <label className="text-xs text-slate-500">指定所辖年级（可多选）</label>
          <div className="mt-2 flex flex-wrap gap-2">
            {grades.map((g) => (
              <label key={g.id} className={`px-3 py-1.5 rounded-lg text-sm cursor-pointer border ${selGrades.includes(g.id) ? "bg-brand-50 border-brand-300 text-brand-600" : "bg-slate-50 border-slate-200 text-slate-600"}`}>
                <input type="checkbox" className="hidden" checked={selGrades.includes(g.id)} onChange={() => setSelGrades((s) => s.includes(g.id) ? s.filter((x) => x !== g.id) : [...s, g.id])} />
                {g.name}
              </label>
            ))}
          </div>
        </div>
      )}
      {u.role === "teacher" && (
        <>
          <div>
            <label className="text-xs text-slate-500">所辖年级（可多选）</label>
            <div className="mt-2 flex flex-wrap gap-2">
              {grades.map((g) => (
                <label key={g.id} className={`px-3 py-1.5 rounded-lg text-sm cursor-pointer border ${selGrades.includes(g.id) ? "bg-brand-50 border-brand-300 text-brand-600" : "bg-slate-50 border-slate-200 text-slate-600"}`}>
                  <input type="checkbox" className="hidden" checked={selGrades.includes(g.id)} onChange={() => setSelGrades((s) => s.includes(g.id) ? s.filter((x) => x !== g.id) : [...s, g.id])} />
                  {g.name}
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-500">所辖班级（可多选）</label>
            <div className="mt-2 max-h-40 overflow-y-auto space-y-1">
              {classes.map((c) => (
                <label key={c.id} className={`flex items-center gap-2 px-2 py-1.5 rounded text-sm cursor-pointer ${selClasses.includes(c.id) ? "bg-brand-50 text-brand-600" : "hover:bg-slate-50"}`}>
                  <input type="checkbox" checked={selClasses.includes(c.id)} onChange={() => setSelClasses((s) => s.includes(c.id) ? s.filter((x) => x !== c.id) : [...s, c.id])} />
                  <span>{c.name} <span className="text-xs text-slate-400">（{c.gradeName}）</span></span>
                </label>
              ))}
            </div>
          </div>
        </>
      )}
      {u.role === "student" && (
        <>
          <div>
            <label className="text-xs text-slate-500">所属班级</label>
            <select value={classId} onChange={(e) => setClassId(e.target.value)} className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white outline-none">
              <option value="">请选择班级</option>
              {classes.map((c) => <option key={c.id} value={c.id}>{c.name}（{c.gradeName}）</option>)}
            </select>
          </div>
          <Field label="学号" value={studentNo} onChange={setStudentNo} />
        </>
      )}
      <div className="flex gap-2 pt-2">
        <DButton variant="ghost" onClick={onClose}>取消</DButton>
        <DButton variant="primary" disabled={saving || busy} onClick={approve}>{saving ? "授权中…" : "确认授权"}</DButton>
      </div>
    </Sheet>
  );
}

function DetailSheet({ u, busy, onClose, onStatus, onReset, onDelete }: { u: SchoolUser; busy: boolean; onClose: () => void; onStatus: (u: SchoolUser, s: UserStatus) => void; onReset: (u: SchoolUser) => void; onDelete: (u: SchoolUser) => void }) {
  return (
    <Sheet title={`详情 · ${u.name}`} onClose={onClose}>
      <Row k="用户名" v={u.username} />
      <Row k="角色" v={ROLE_LABEL[u.role]} />
      <Row k="状态" v={<StatusPill s={u.status} />} />
      <Row k="身份证" v={u.idNumber || "—"} />
      <Row k="范围" v={[u.gradeName, u.className].filter(Boolean).join(" / ") || "—"} />
      <Row k="学号" v={u.studentNo || "—"} />
      <Row k="创建" v={u.createdAt?.replace("T", " ").slice(0, 16) || "—"} />
      <div className="pt-2 border-t border-slate-100 flex flex-wrap gap-2">
        {u.status !== "active" && <DButton size="sm" variant="primary" disabled={busy} onClick={() => onStatus(u, "active")}>启用</DButton>}
        {u.status === "active" && <DButton size="sm" variant="outline" disabled={busy} onClick={() => onStatus(u, "suspended")}>停用</DButton>}
        {u.status !== "deactivated" && <DButton size="sm" variant="outline" disabled={busy} onClick={() => onStatus(u, "deactivated")}>注销</DButton>}
        <DButton size="sm" variant="ghost" disabled={busy} onClick={() => onReset(u)}>重置密码</DButton>
        <DButton size="sm" variant="danger" disabled={busy} onClick={() => onDelete(u)}>删除</DButton>
      </div>
    </Sheet>
  );
}

function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-md p-5 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-medium text-slate-800 mb-3">{title}</h3>
        <div className="space-y-3 text-sm">{children}</div>
      </div>
    </div>
  );
}
function Row({ k, v }: { k: string; v: React.ReactNode }) { return <div className="flex"><span className="w-20 text-slate-400">{k}</span><span className="flex-1 text-slate-700">{v}</span></div>; }
function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return <div><label className="text-xs text-slate-500">{label}</label><input value={value} onChange={(e) => onChange(e.target.value)} className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-200 text-sm outline-none" /></div>;
}
function StatusPill({ s }: { s: UserStatus }) {
  const color = s === "active" ? "green" : s === "suspended" ? "amber" : s === "deactivated" ? "red" : "slate";
  return <Pill color={color as any}>{STATUS_LABEL[s]}</Pill>;
}
