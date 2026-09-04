import { useEffect, useState } from "react";
import { get, post, patch, put, del } from "../api/client";
import { Panel, PanelHeader, Pill, DButton, Spinner, Empty } from "./desktop";

export type ScopeLayer = "school" | "grade" | "class";

interface KpNode { id: string; name: string; mastery: number; frequency: number; errorCount: number; origin: string; }
interface UnitNode { id: string; name: string; knowledgePoints: KpNode[]; }
interface ModNode { id: string; name: string; mastery: number; units: UnitNode[]; }
interface ScopeInfo { syncMode: "auto" | "manual"; lastSyncAt?: string; hiddenKpIds?: string[]; hiddenQIds?: string[]; }
interface Question {
  id: string; moduleId: string; unitId: string; kpId: string;
  type: string; difficulty: number; material?: string; stem: string;
  options?: string[]; answer: string; analysis: string; origin: string;
}

const ORIGIN_LABEL: Record<string, string> = { system: "系统", school: "学校", grade: "年级", class: "班级" };
const ORIGIN_COLOR: Record<string, "slate" | "brand" | "amber" | "green"> = { system: "slate", school: "brand", grade: "amber", class: "green" };

export default function ScopeContentManager({ scope, id, mode }: { scope: ScopeLayer; id: string; mode: "knowledge" | "questions" }) {
  if (mode === "knowledge") return <KpManager scope={scope} id={id} />;
  return <QManager scope={scope} id={id} />;
}

// ===================== 知识点 =====================
function KpManager({ scope, id }: { scope: ScopeLayer; id: string }) {
  const [tree, setTree] = useState<ModNode[] | null>(null);
  const [info, setInfo] = useState<ScopeInfo | null>(null);
  const [sel, setSel] = useState<KpNode | null>(null);
  const [open, setOpen] = useState<{ unitId: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const base = `/scope/${scope}/${id}`;

  async function reload() {
    const [t, s] = await Promise.all([
      get<{ tree: ModNode[]; scope: ScopeInfo }>(`${base}/knowledge-tree`),
      get<ScopeInfo>(`${base}/sync`),
    ]);
    setTree(t.tree); setInfo(t.scope);
  }
  useEffect(() => { reload(); }, [scope, id]); // eslint-disable-line

  async function addKp(unitId: string, name: string, mastery: number, frequency: number) {
    setBusy(true);
    try { await post(`${base}/knowledge-points`, { unitId, name, mastery, frequency }); setOpen(null); reload(); }
    catch (e: any) { alert(e?.response?.data?.error || "新增失败"); }
    setBusy(false);
  }
  async function saveKp(kp: KpNode, patch_: Partial<KpNode>) {
    setBusy(true);
    try { await put(`${base}/knowledge-points/${kp.id}`, patch_); setSel(null); reload(); }
    catch (e: any) { alert(e?.response?.data?.error || "保存失败"); }
    setBusy(false);
  }
  async function hideKp(kp: KpNode) {
    if (!confirm(`隐藏知识点「${kp.name}」？（本层隐藏继承项，可恢复）`)) return;
    setBusy(true);
    try { await del(`${base}/knowledge-points/${kp.id}`); reload(); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }
  async function restoreKp(kpId: string) {
    setBusy(true);
    try { await patch(`${base}/knowledge-points/${kpId}/restore`, {}); reload(); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }
  async function setSync(m: "auto" | "manual") {
    setBusy(true);
    try { await patch(`${base}/sync`, { syncMode: m }); reload(); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }
  async function refresh() {
    setBusy(true);
    try { await post(`${base}/refresh`, {}); reload(); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }

  if (!tree) return <Spinner label="加载知识图谱…" />;
  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader title="继承与同步" action={
          info && (
            <div className="flex items-center gap-2">
              <Pill color={info.syncMode === "auto" ? "green" : "amber"}>{info.syncMode === "auto" ? "自动同步" : "手动同步"}</Pill>
              <select value={info.syncMode} disabled={busy} onChange={(e) => setSync(e.target.value as any)}
                className="px-2 py-1 text-xs rounded border border-slate-200 bg-white outline-none disabled:opacity-50">
                <option value="auto">自动</option><option value="manual">手动</option>
              </select>
              {info.syncMode === "manual" && <DButton size="sm" variant="outline" disabled={busy} onClick={refresh}>立即刷新</DButton>}
            </div>
          )
        } />
        <div className="px-5 py-3 text-xs text-slate-500">
          {info?.syncMode === "manual"
            ? "手动模式：上游（系统/学校/年级）变化不会立即生效，点击「立即刷新」拉取最新。"
            : "自动模式：上游变化实时继承到本层有效集。"} {info?.lastSyncAt && `上次刷新 ${info.lastSyncAt.replace("T", " ").slice(0, 16)}`}
        </div>
      </Panel>

      {tree.map((m) => (
        <Panel key={m.id}>
          <PanelHeader title={m.name} action={<span className="text-xs text-slate-400">平均掌握度 {m.mastery}</span>} />
          <div className="divide-y divide-slate-100">
            {m.units.map((u) => (
              <div key={u.id} className="px-5 py-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-slate-700">{u.name}</span>
                  <DButton size="sm" variant="ghost" onClick={() => setOpen(open?.unitId === u.id ? null : { unitId: u.id })}>+ 新增知识点</DButton>
                </div>
                {open?.unitId === u.id && (
                  <AddKpForm busy={busy} onAdd={(n, mst, fr) => addKp(u.id, n, mst, fr)} />
                )}
                <div className="space-y-1.5">
                  {u.knowledgePoints.map((k) => {
                    const hidden = info?.hiddenKpIds?.includes(k.id);
                    return (
                      <div key={k.id} className={`flex items-center gap-2 px-2 py-1.5 rounded text-sm ${hidden ? "opacity-40 line-through" : "hover:bg-slate-50"}`}>
                        <Pill color={ORIGIN_COLOR[k.origin]}>{ORIGIN_LABEL[k.origin]}</Pill>
                        <span className="flex-1 text-slate-700">{k.name}</span>
                        <span className="text-xs text-slate-400">掌握{k.mastery}</span>
                        {hidden
                          ? <DButton size="sm" variant="ghost" disabled={busy} onClick={() => restoreKp(k.id)}>恢复</DButton>
                          : <>
                              <DButton size="sm" variant="ghost" onClick={() => setSel(k)}>编辑</DButton>
                              <DButton size="sm" variant="ghost" disabled={busy} onClick={() => hideKp(k)}>隐藏</DButton>
                            </>}
                      </div>
                    );
                  })}
                  {u.knowledgePoints.length === 0 && <div className="text-xs text-slate-400 px-2 py-1">无知识点</div>}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      ))}

      {sel && <KpEditSheet kp={sel} busy={busy} onClose={() => setSel(null)} onSave={(p) => saveKp(sel, p)} />}
    </div>
  );
}

function AddKpForm({ busy, onAdd }: { busy: boolean; onAdd: (name: string, mastery: number, frequency: number) => void }) {
  const [name, setName] = useState("");
  const [mastery, setMastery] = useState(50);
  const [frequency, setFrequency] = useState(5);
  return (
    <div className="flex gap-2 mb-2">
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="知识点名称" className="flex-1 px-2 py-1 text-xs rounded border border-slate-200 outline-none" />
      <input type="number" value={mastery} onChange={(e) => setMastery(+e.target.value)} className="w-16 px-2 py-1 text-xs rounded border border-slate-200" title="掌握度" />
      <input type="number" value={frequency} onChange={(e) => setFrequency(+e.target.value)} className="w-16 px-2 py-1 text-xs rounded border border-slate-200" title="考频" />
      <DButton size="sm" disabled={busy || !name} onClick={() => onAdd(name, mastery, frequency)}>添加</DButton>
    </div>
  );
}

function KpEditSheet({ kp, busy, onClose, onSave }: { kp: KpNode; busy: boolean; onClose: () => void; onSave: (p: Partial<KpNode>) => void }) {
  const [name, setName] = useState(kp.name);
  const [mastery, setMastery] = useState(kp.mastery);
  const [frequency, setFrequency] = useState(kp.frequency);
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-sm p-5" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-medium text-slate-800 mb-3">编辑知识点</h3>
        <div className="space-y-3 text-sm">
          <div><label className="text-xs text-slate-500">名称</label><input value={name} onChange={(e) => setName(e.target.value)} className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-200 outline-none" /></div>
          <div><label className="text-xs text-slate-500">掌握度：{mastery}</label><input type="range" min={0} max={100} value={mastery} onChange={(e) => setMastery(+e.target.value)} className="w-full accent-brand-500" /></div>
          <div><label className="text-xs text-slate-500">考频：{frequency}</label><input type="range" min={1} max={10} value={frequency} onChange={(e) => setFrequency(+e.target.value)} className="w-full accent-brand-500" /></div>
        </div>
        <div className="flex gap-2 mt-4">
          <DButton variant="ghost" onClick={onClose}>取消</DButton>
          <DButton variant="primary" disabled={busy} onClick={() => onSave({ name, mastery, frequency })}>保存</DButton>
        </div>
      </div>
    </div>
  );
}

// ===================== 题目 =====================
function QManager({ scope, id }: { scope: ScopeLayer; id: string }) {
  const [list, setList] = useState<Question[] | null>(null);
  const [sel, setSel] = useState<Question | null>(null);
  const [add, setAdd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState({ moduleId: "", type: "" });
  const base = `/scope/${scope}/${id}`;

  async function reload() {
    const params: Record<string, string> = {};
    if (filter.moduleId) params.moduleId = filter.moduleId;
    if (filter.type) params.type = filter.type;
    setList(await get<Question[]>(`${base}/questions`, params));
  }
  useEffect(() => { reload(); }, [scope, id, filter]); // eslint-disable-line

  async function saveQ(q: Question, p: Partial<Question>) {
    setBusy(true);
    try { await put(`${base}/questions/${q.id}`, p); setSel(null); reload(); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }
  async function addQ(b: Partial<Question>) {
    setBusy(true);
    try { await post(`${base}/questions`, { stem: b.stem, answer: b.answer, analysis: b.analysis, type: b.type || "choice", difficulty: b.difficulty || 2, moduleId: b.moduleId, options: b.options }); setAdd(false); reload(); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }
  async function hideQ(q: Question) {
    if (!confirm(`隐藏题目「${q.stem.slice(0, 12)}」？`)) return;
    setBusy(true);
    try { await del(`${base}/questions/${q.id}`); reload(); }
    catch (e: any) { alert(e?.response?.data?.error); }
    setBusy(false);
  }

  if (!list) return <Spinner label="加载题库…" />;
  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader title={`题目（${list.length}）`} action={<DButton size="sm" variant="primary" onClick={() => setAdd(true)}>+ 新增</DButton>} />
        <div className="px-5 py-2 flex gap-2 text-xs">
          <select value={filter.moduleId} onChange={(e) => setFilter({ ...filter, moduleId: e.target.value })} className="px-2 py-1 rounded border border-slate-200 bg-white">
            <option value="">全部模块</option><option value="m1">文言文基础</option><option value="m2">古代诗歌鉴赏</option><option value="m3">现代文阅读</option><option value="m4">语言文字运用</option><option value="m5">写作</option>
          </select>
          <select value={filter.type} onChange={(e) => setFilter({ ...filter, type: e.target.value })} className="px-2 py-1 rounded border border-slate-200 bg-white">
            <option value="">全部题型</option><option value="choice">选择题</option><option value="fill">填空题</option><option value="short">简答题</option>
          </select>
        </div>
        {list.length === 0 ? <Empty text="无题目" /> : (
          <div className="divide-y divide-slate-100">
            {list.map((q) => (
              <div key={q.id} className="px-5 py-3 flex items-start gap-2">
                <Pill color={ORIGIN_COLOR[q.origin]}>{ORIGIN_LABEL[q.origin]}</Pill>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-slate-800 truncate">{q.stem}</div>
                  <div className="text-xs text-slate-400 mt-0.5">{q.type} · 难度{q.difficulty} · {q.id}</div>
                </div>
                <DButton size="sm" variant="ghost" onClick={() => setSel(q)}>编辑</DButton>
                <DButton size="sm" variant="ghost" disabled={busy} onClick={() => hideQ(q)}>隐藏</DButton>
              </div>
            ))}
          </div>
        )}
      </Panel>
      {sel && <QEditSheet q={sel} busy={busy} onClose={() => setSel(null)} onSave={(p) => saveQ(sel, p)} />}
      {add && <QAddSheet busy={busy} onClose={() => setAdd(false)} onAdd={addQ} />}
    </div>
  );
}

function QEditSheet({ q, busy, onClose, onSave }: { q: Question; busy: boolean; onClose: () => void; onSave: (p: Partial<Question>) => void }) {
  const [stem, setStem] = useState(q.stem);
  const [answer, setAnswer] = useState(q.answer);
  const [analysis, setAnalysis] = useState(q.analysis);
  return (
    <Sheet title="编辑题目" onClose={onClose}>
      <Textarea label="题干" value={stem} onChange={setStem} rows={3} />
      <Textarea label="答案" value={answer} onChange={setAnswer} rows={2} />
      <Textarea label="解析" value={analysis} onChange={setAnalysis} rows={3} />
      <div className="flex gap-2 mt-3"><DButton variant="ghost" onClick={onClose}>取消</DButton><DButton variant="primary" disabled={busy} onClick={() => onSave({ stem, answer, analysis })}>保存</DButton></div>
    </Sheet>
  );
}
function QAddSheet({ busy, onClose, onAdd }: { busy: boolean; onClose: () => void; onAdd: (b: Partial<Question>) => void }) {
  const [stem, setStem] = useState("");
  const [answer, setAnswer] = useState("");
  const [analysis, setAnalysis] = useState("");
  const [type, setType] = useState("choice");
  const [difficulty, setDifficulty] = useState(2);
  const [moduleId, setModuleId] = useState("m1");
  return (
    <Sheet title="新增题目" onClose={onClose}>
      <div className="grid grid-cols-3 gap-2">
        <select value={type} onChange={(e) => setType(e.target.value)} className="px-2 py-2 text-sm rounded border border-slate-200 bg-white"><option value="choice">选择</option><option value="fill">填空</option><option value="short">简答</option></select>
        <select value={String(difficulty)} onChange={(e) => setDifficulty(+e.target.value)} className="px-2 py-2 text-sm rounded border border-slate-200 bg-white"><option value="1">难度1</option><option value="2">难度2</option><option value="3">难度3</option><option value="4">难度4</option></select>
        <select value={moduleId} onChange={(e) => setModuleId(e.target.value)} className="px-2 py-2 text-sm rounded border border-slate-200 bg-white"><option value="m1">文言文</option><option value="m2">诗歌</option><option value="m3">现代文</option><option value="m4">语言运用</option><option value="m5">写作</option></select>
      </div>
      <Textarea label="题干" value={stem} onChange={setStem} rows={3} />
      <Textarea label="答案" value={answer} onChange={setAnswer} rows={2} />
      <Textarea label="解析" value={analysis} onChange={setAnalysis} rows={2} />
      <div className="flex gap-2 mt-3"><DButton variant="ghost" onClick={onClose}>取消</DButton><DButton variant="primary" disabled={busy || !stem} onClick={() => onAdd({ stem, answer, analysis, type, difficulty, moduleId })}>添加</DButton></div>
    </Sheet>
  );
}

function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-md p-5 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-medium text-slate-800 mb-3">{title}</h3>
        <div className="space-y-3">{children}</div>
      </div>
    </div>
  );
}
function Textarea({ label, value, onChange, rows }: { label: string; value: string; onChange: (v: string) => void; rows: number }) {
  return (
    <div>
      <label className="text-xs text-slate-500">{label}</label>
      <textarea value={value} onChange={(e) => onChange(e.target.value)} rows={rows} className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-200 text-sm outline-none focus:border-brand-500 resize-none" />
    </div>
  );
}
