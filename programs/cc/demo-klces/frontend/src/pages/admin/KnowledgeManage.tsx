import { useState } from "react";
import { useGet, usePost } from "../../api/hooks";
import { api } from "../../api/client";
import { Panel, Pill, DButton, Spinner, Empty, masteryColor } from "../../components/desktop";

interface TreeNode {
  id: string; name: string;
  units: { id: string; name: string; knowledgePoints: { id: string; name: string; mastery: number; frequency: number }[] }[];
}
interface KpDetail { id: string; name: string; mastery: number; frequency: number; errorCount: number; moduleName: string; unitName: string; }

export default function KnowledgeManage() {
  const tree = useGet<TreeNode[]>("/admin/knowledge-tree");
  const [selKp, setSelKp] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [edit, setEdit] = useState<{ name: string; mastery: number; frequency: number }>({ name: "", mastery: 0, frequency: 0 });
  const kp = useGet<KpDetail>(selKp ? `/knowledge-points/${selKp}` : null);
  const post = usePost();
  const [newKpName, setNewKpName] = useState("");
  const [addUnitId, setAddUnitId] = useState<string | null>(null);

  // sync edit form when kp loads
  if (kp.data && edit.name === "" && kp.data.name) setEdit({ name: kp.data.name, mastery: kp.data.mastery, frequency: kp.data.frequency });

  function toggle(id: string) {
    setExpanded((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  async function save() {
    await api.put(`/admin/knowledge-points/${selKp}`, edit);
    alert("已保存并同步至前端");
    tree.refetch();
  }
  async function del() {
    if (!confirm("确认删除该知识点？")) return;
    await api.delete(`/admin/knowledge-points/${selKp}`);
    setSelKp(null);
    setEdit({ name: "", mastery: 0, frequency: 0 });
    tree.refetch();
  }
  async function addKp(unitId: string) {
    if (!newKpName.trim()) return;
    await post("/admin/knowledge-points", { unitId, name: newKpName, mastery: 50, frequency: 5 });
    setNewKpName(""); setAddUnitId(null);
    tree.refetch();
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-3 md:gap-4 lg:h-[calc(100vh-7rem)]">
      {/* 左侧目录树 */}
      <Panel className="overflow-y-auto lg:max-h-[calc(100vh-7rem)] max-h-[60vh]">
        <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
          <span className="font-medium text-slate-800">知识目录树</span>
          <DButton variant="outline" size="sm" onClick={() => alert("批量导入：支持 Excel/CSV 模板上传")}>批量导入</DButton>
        </div>
        {tree.loading ? <Spinner /> : tree.data?.map((m) => (
          <div key={m.id} className="text-sm">
            <button onClick={() => toggle(m.id)} className="w-full text-left px-4 py-2 hover:bg-slate-50 flex items-center gap-1 font-medium text-slate-800">
              <span className="text-xs text-slate-400">{expanded.has(m.id) ? "▼" : "▶"}</span>
              📁 {m.name}
              <span className="ml-auto text-xs text-slate-400">{m.units.length}单元</span>
            </button>
            {expanded.has(m.id) && m.units.map((u) => (
              <div key={u.id}>
                <button onClick={() => toggle(u.id)} className="w-full text-left pl-9 pr-4 py-1.5 hover:bg-slate-50 flex items-center gap-1 text-slate-600">
                  <span className="text-xs text-slate-400">{expanded.has(u.id) ? "▼" : "▶"}</span>
                  📂 {u.name}
                  <span className="ml-auto text-xs text-slate-400">{u.knowledgePoints.length}</span>
                </button>
                {expanded.has(u.id) && u.knowledgePoints.map((k) => (
                  <button key={k.id} onClick={() => { setSelKp(k.id); setEdit({ name: k.name, mastery: k.mastery, frequency: k.frequency }); }}
                    className={`w-full text-left pl-14 pr-4 py-1.5 flex items-center gap-2 ${selKp === k.id ? "bg-brand-50 text-brand-600" : "hover:bg-slate-50 text-slate-600"}`}>
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: masteryColor(k.mastery) }} />
                    <span className="truncate">{k.name}</span>
                  </button>
                ))}
                {expanded.has(u.id) && (
                  <div className="pl-14 pr-4 py-1.5">
                    {addUnitId === u.id ? (
                      <div className="flex gap-1">
                        <input value={newKpName} onChange={(e) => setNewKpName(e.target.value)} placeholder="新知识点名称"
                          className="flex-1 px-2 py-1 rounded border border-slate-300 text-xs outline-none focus:border-brand-500" />
                        <DButton size="sm" onClick={() => addKp(u.id)}>+</DButton>
                        <DButton variant="ghost" size="sm" onClick={() => setAddUnitId(null)}>×</DButton>
                      </div>
                    ) : (
                      <button onClick={() => setAddUnitId(u.id)} className="text-xs text-brand-600 hover:underline">+ 新增知识点</button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}
      </Panel>

      {/* 右侧编辑区 */}
      <Panel className="overflow-y-auto lg:max-h-[calc(100vh-7rem)]">
        {!selKp || !kp.data ? (
          <Empty text="← 在左侧目录树选择一个知识点进行编辑" />
        ) : (
          <div className="p-5 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium text-slate-900">{kp.data.name}</h2>
              <Pill color="brand">掌握度 {kp.data.mastery}%</Pill>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
              <Info label="所属模块" value={kp.data.moduleName} />
              <Info label="所属单元" value={kp.data.unitName} />
              <Info label="错题数" value={`${kp.data.errorCount} 题`} />
            </div>
            <Field label="知识点名称">
              <input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm outline-none focus:border-brand-500" />
            </Field>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label={`掌握度：${edit.mastery}%`}>
                <input type="range" min={0} max={100} value={edit.mastery} onChange={(e) => setEdit({ ...edit, mastery: +e.target.value })} className="w-full accent-brand-500" />
              </Field>
              <Field label={`考频权重：${edit.frequency}`}>
                <input type="range" min={1} max={10} value={edit.frequency} onChange={(e) => setEdit({ ...edit, frequency: +e.target.value })} className="w-full accent-brand-500" />
              </Field>
            </div>
            <Field label="所属层级">
              <div className="flex gap-2 text-sm">
                <Pill>{kp.data.moduleName}</Pill><span>›</span><Pill>{kp.data.unitName}</Pill><span>›</span><Pill color="brand">知识点</Pill>
              </div>
            </Field>
            <Field label="前置知识点">
              <input placeholder="输入前置知识点 id，逗号分隔（示例：k2, k3）"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm outline-none focus:border-brand-500" />
            </Field>
            <div className="flex gap-2 pt-2 border-t border-slate-100">
              <DButton onClick={save}>保存修改</DButton>
              <DButton variant="danger" onClick={del}>删除知识点</DButton>
              <span className="ml-auto text-xs text-slate-400 self-center">修改后实时同步至前端</span>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return <div className="bg-slate-50 rounded-lg p-3"><div className="text-xs text-slate-400">{label}</div><div className="text-slate-800 mt-0.5">{value}</div></div>;
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="text-xs text-slate-500 block mb-1">{label}</label>{children}</div>;
}
