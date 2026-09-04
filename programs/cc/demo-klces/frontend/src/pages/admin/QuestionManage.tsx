import { useState } from "react";
import { useGet } from "../../api/hooks";
import { api } from "../../api/client";
import { Panel, Pill, DButton, Spinner, Empty } from "../../components/desktop";

interface Q {
  id: string; type: string; difficulty: number; stem: string; material?: string;
  options?: string[]; answer: string; analysis: string;
  moduleId: string; unitId: string; kpId: string; errorType?: string;
}
interface TreeNode { id: string; name: string; units: { id: string; name: string; knowledgePoints: { id: string; name: string }[] }[]; }

const TYPES = [
  { v: "", label: "全部题型" }, { v: "choice", label: "选择题" }, { v: "fill", label: "填空题" }, { v: "short", label: "简答题" },
];
const DIFFS = [
  { v: "", label: "全部难度" }, { v: "1", label: "难度1" }, { v: "2", label: "难度2" }, { v: "3", label: "难度3" }, { v: "4", label: "难度4" },
];
const TYPE_LABEL: Record<string, string> = { choice: "选择题", fill: "填空题", short: "简答题" };

export default function QuestionManage() {
  const tree = useGet<TreeNode[]>("/admin/knowledge-tree");
  const [filters, setFilters] = useState({ moduleId: "", type: "", difficulty: "" });
  const [selId, setSelId] = useState<string | null>(null);
  const query = new URLSearchParams();
  if (filters.moduleId) query.set("moduleId", filters.moduleId);
  if (filters.type) query.set("type", filters.type);
  if (filters.difficulty) query.set("difficulty", filters.difficulty);
  const list = useGet<Q[]>(`/admin/questions?${query.toString()}`);

  const sel = list.data?.find((q) => q.id === selId) ?? null;
  const [edit, setEdit] = useState<Q | null>(null);
  if (sel && (!edit || edit.id !== sel.id)) setEdit({ ...sel });

  async function save() {
    if (!edit) return;
    await api.put(`/admin/questions/${edit.id}`, edit);
    alert("已保存");
    list.refetch();
  }
  async function del(id: string) {
    if (!confirm("确认删除该试题？")) return;
    await api.delete(`/admin/questions/${id}`);
    if (selId === id) setSelId(null);
    list.refetch();
  }
  async function toggleShelf(id: string) { alert(`试题 ${id} 已上下架`); }

  return (
    <div className="space-y-4">
      {/* 筛选栏 */}
      <Panel className="px-4 md:px-5 py-3 flex items-center gap-2 md:gap-3 flex-wrap">
        <span className="text-sm text-slate-500">筛选：</span>
        <select value={filters.moduleId} onChange={(e) => setFilters({ ...filters, moduleId: e.target.value })}
          className="px-3 py-1.5 rounded-lg border border-slate-300 text-sm outline-none">
          <option value="">全部模块</option>
          {(tree.data || []).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
        <select value={filters.type} onChange={(e) => setFilters({ ...filters, type: e.target.value })}
          className="px-3 py-1.5 rounded-lg border border-slate-300 text-sm outline-none">
          {TYPES.map((t) => <option key={t.v} value={t.v}>{t.label}</option>)}
        </select>
        <select value={filters.difficulty} onChange={(e) => setFilters({ ...filters, difficulty: e.target.value })}
          className="px-3 py-1.5 rounded-lg border border-slate-300 text-sm outline-none">
          {DIFFS.map((d) => <option key={d.v} value={d.v}>{d.label}</option>)}
        </select>
        <span className="ml-auto text-xs text-slate-400">共 {list.data?.length ?? 0} 题</span>
        <DButton size="sm" onClick={() => alert("批量导入：支持题库 Excel 模板")}>批量导入</DButton>
        <DButton size="sm" variant="outline" onClick={() => alert("新建试题")}>+ 新建</DButton>
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 md:gap-4 lg:h-[calc(100vh-13rem)]">
        {/* 试题列表 */}
        <Panel className="overflow-y-auto lg:max-h-[calc(100vh-13rem)] max-h-[60vh]">
          {list.loading ? <Spinner /> : list.data?.length === 0 ? <Empty text="无匹配试题" /> : list.data?.map((q) => (
            <button key={q.id} onClick={() => setSelId(q.id)}
              className={`w-full text-left px-4 py-3 border-b border-slate-100 ${selId === q.id ? "bg-brand-50" : "hover:bg-slate-50"}`}>
              <div className="flex items-center gap-2 mb-1">
                <Pill color="brand">{TYPE_LABEL[q.type] || q.type}</Pill>
                <Pill>难度{q.difficulty}</Pill>
                <span className="text-xs text-slate-400">{q.id}</span>
              </div>
              <p className="text-sm text-slate-700 line-clamp-2">{q.stem}</p>
            </button>
          ))}
        </Panel>

        {/* 编辑区 */}
        <Panel className="overflow-y-auto lg:max-h-[calc(100vh-13rem)]">
          {!edit ? <Empty text="← 选择一道试题进行编辑" /> : (
            <div className="p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="font-medium text-slate-900">编辑试题 {edit.id}</h2>
                <div className="flex gap-2">
                  <DButton variant="outline" size="sm" onClick={() => toggleShelf(edit.id)}>上下架</DButton>
                  <DButton variant="danger" size="sm" onClick={() => del(edit.id)}>删除</DButton>
                </div>
              </div>
              <Field label="题干">
                <textarea value={edit.stem} onChange={(e) => setEdit({ ...edit, stem: e.target.value })} rows={3}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm outline-none focus:border-brand-500 resize-none" />
              </Field>
              <Field label="阅读材料（选填）">
                <textarea value={edit.material || ""} onChange={(e) => setEdit({ ...edit, material: e.target.value })} rows={2}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm outline-none focus:border-brand-500 resize-none" />
              </Field>
              {edit.type === "choice" && (
                <Field label="选项（每行一项，A.开头）">
                  <textarea value={(edit.options || []).join("\n")} onChange={(e) => setEdit({ ...edit, options: e.target.value.split("\n") })} rows={4}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm outline-none focus:border-brand-500 resize-none" />
                </Field>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field label="答案">
                  <input value={edit.answer} onChange={(e) => setEdit({ ...edit, answer: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm outline-none focus:border-brand-500" />
                </Field>
                <Field label="题型">
                  <select value={edit.type} onChange={(e) => setEdit({ ...edit, type: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm outline-none">
                    <option value="choice">选择题</option><option value="fill">填空题</option><option value="short">简答题</option>
                  </select>
                </Field>
                <Field label="难度">
                  <select value={edit.difficulty} onChange={(e) => setEdit({ ...edit, difficulty: +e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm outline-none">
                    {[1, 2, 3, 4].map((d) => <option key={d} value={d}>难度{d}</option>)}
                  </select>
                </Field>
                <Field label="错误类型标签">
                  <select value={edit.errorType || ""} onChange={(e) => setEdit({ ...edit, errorType: e.target.value || undefined })}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm outline-none">
                    <option value="">无</option>
                    <option>记忆型</option><option>理解型</option><option>方法型</option><option>审题型</option>
                  </select>
                </Field>
              </div>
              <Field label="解析">
                <textarea value={edit.analysis} onChange={(e) => setEdit({ ...edit, analysis: e.target.value })} rows={3}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm outline-none focus:border-brand-500 resize-none" />
              </Field>
              <div className="flex gap-2 pt-2 border-t border-slate-100">
                <DButton onClick={save}>保存</DButton>
                <span className="ml-auto text-xs text-slate-400 self-center">支持审核、上下架</span>
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="text-xs text-slate-500 block mb-1">{label}</label>{children}</div>;
}
