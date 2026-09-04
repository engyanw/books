import { useEffect, useState } from "react";
import { get, post, patch, del } from "../../api/client";
import { Panel, PanelHeader, Pill, DButton, Spinner, Empty } from "../../components/desktop";

interface Grade { id: string; name: string; classCount?: number }
interface Cls { id: string; name: string; gradeId: string; gradeName?: string }

export default function SchoolStructure() {
  const [grades, setGrades] = useState<Grade[] | null>(null);
  const [classes, setClasses] = useState<Cls[] | null>(null);
  const [busy, setBusy] = useState(false);

  async function reload() {
    const [g, c] = await Promise.all([get<Grade[]>("/school/grades"), get<Cls[]>("/school/classes")]);
    setGrades(g); setClasses(c);
  }
  useEffect(() => { reload(); }, []); // eslint-disable-line

  async function addGrade(name: string) {
    if (!name.trim()) return;
    setBusy(true);
    try { await post("/school/grades", { name: name.trim() }); reload(); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }
  async function renameGrade(g: Grade, name: string) {
    if (!name.trim() || name === g.name) return;
    setBusy(true);
    try { await patch(`/school/grades/${g.id}`, { name: name.trim() }); reload(); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }
  async function delGrade(g: Grade) {
    if (!confirm(`删除年级「${g.name}」及其下所有班级？`)) return;
    setBusy(true);
    try { await del(`/school/grades/${g.id}`); reload(); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }
  async function addClass(gid: string, name: string) {
    if (!name.trim()) return;
    setBusy(true);
    try { await post("/school/classes", { name: name.trim(), gradeId: gid }); reload(); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }
  async function renameClass(c: Cls, name: string) {
    if (!name.trim() || name === c.name) return;
    setBusy(true);
    try { await patch(`/school/classes/${c.id}`, { name: name.trim() }); reload(); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }
  async function delClass(c: Cls) {
    if (!confirm(`删除班级「${c.name}」？`)) return;
    setBusy(true);
    try { await del(`/school/classes/${c.id}`); reload(); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }

  if (!grades || !classes) return <Spinner label="加载结构…" />;
  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader title="年级管理" action={<AddInline placeholder="新建年级名" onSubmit={addGrade} disabled={busy} />} />
        {grades.length === 0 ? <Empty text="尚未创建年级" /> : (
          <div className="divide-y divide-slate-100">
            {grades.map((g) => {
              const gcs = classes.filter((c) => c.gradeId === g.id);
              return (
                <div key={g.id} className="px-5 py-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Pill color="brand">{g.name}</Pill>
                    <span className="text-xs text-slate-400">{g.classCount ?? gcs.length} 个班</span>
                    <div className="ml-auto flex gap-1">
                      <RenameInline label="年级名" value={g.name} onSubmit={(n) => renameGrade(g, n)} disabled={busy} />
                      <DButton size="sm" variant="ghost" disabled={busy} onClick={() => delGrade(g)}>删除</DButton>
                    </div>
                  </div>
                  <div className="pl-3 border-l-2 border-slate-100 space-y-1.5">
                    <AddInline placeholder="+ 新建班级" onSubmit={(n) => addClass(g.id, n)} disabled={busy} />
                    {gcs.map((c) => (
                      <div key={c.id} className="flex items-center gap-2 text-sm">
                        <span className="text-slate-600">{c.name}</span>
                        <div className="ml-auto flex gap-1">
                          <RenameInline label="班级名" value={c.name} onSubmit={(n) => renameClass(c, n)} disabled={busy} />
                          <DButton size="sm" variant="ghost" disabled={busy} onClick={() => delClass(c)}>删除</DButton>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}

function AddInline({ placeholder, onSubmit, disabled }: { placeholder: string; onSubmit: (v: string) => void; disabled?: boolean }) {
  const [v, setV] = useState("");
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(v); setV(""); }} className="flex gap-1">
      <input value={v} onChange={(e) => setV(e.target.value)} placeholder={placeholder} className="px-2.5 py-1 text-sm rounded-lg border border-slate-200 outline-none w-28" />
      <DButton size="sm" variant="outline" disabled={disabled}>添加</DButton>
    </form>
  );
}
function RenameInline({ label, value, onSubmit, disabled }: { label: string; value: string; onSubmit: (v: string) => void; disabled?: boolean }) {
  const [editing, setEditing] = useState(false);
  const [v, setV] = useState(value);
  if (editing) return (
    <form onSubmit={(e) => { e.preventDefault(); setEditing(false); onSubmit(v); }} className="flex gap-1">
      <input value={v} onChange={(e) => setV(e.target.value)} autoFocus className="px-2 py-1 text-sm rounded border border-slate-200 w-24" />
      <DButton size="sm" variant="ghost" disabled={disabled}>✓</DButton>
    </form>
  );
  return <DButton size="sm" variant="ghost" disabled={disabled} onClick={() => { setV(value); setEditing(true); }}>改名</DButton>;
}
