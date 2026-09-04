import { useState } from "react";
import { useGet } from "../../api/hooks";
import { Panel, PanelHeader, Pill, DButton, Spinner, Empty } from "../../components/desktop";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid } from "recharts";

interface TA {
  id: string; name: string; type: string; className: string;
  status: "ongoing" | "done"; deadline: string;
  avgScore?: number; submission?: number; total?: number;
  gradeDist?: { range: string; count: number }[];
  correctRate?: { module: string; rate: number }[];
}

export default function ClassAssessManage() {
  const list = useGet<TA[]>("/teacher/assessments");
  const [selId, setSelId] = useState<string | null>(null);
  const [publishOpen, setPublishOpen] = useState(false);

  const ongoing = list.data?.filter((a) => a.status === "ongoing") ?? [];
  const done = list.data?.filter((a) => a.status === "done") ?? [];
  const sel = list.data?.find((a) => a.id === selId) ?? done[0];

  return (
    <div className="space-y-4">
      <Panel className="px-5 py-3 flex items-center">
        <h2 className="font-medium text-slate-800">测评管理</h2>
        <div className="ml-auto"><DButton size="sm" onClick={() => setPublishOpen(true)}>+ 发布测评</DButton></div>
      </Panel>

      {list.loading ? <Spinner /> : list.error ? <Empty text="加载失败" /> : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 md:gap-4">
          {/* 进行中 */}
          <Panel>
            <PanelHeader title="进行中测评" />
            <div className="p-2">
              {ongoing.length === 0 ? <Empty text="无进行中测评" /> : ongoing.map((a) => (
                <div key={a.id} className="px-3 py-2.5 hover:bg-slate-50 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-medium text-slate-800">{a.name}</span>
                      <Pill color="brand">{a.type}</Pill>
                    </div>
                    <span className="text-xs text-amber-500">截止 {a.deadline}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
                    <span>{a.className}</span>
                    <div className="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                      <div className="h-full bg-brand-500 rounded-full" style={{ width: `${((a.submission ?? 0) / (a.total || 1)) * 100}%` }} />
                    </div>
                    <span>{a.submission}/{a.total} 已提交</span>
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          {/* 已完成 + 详情 */}
          <Panel>
            <PanelHeader title="已完成测评" />
            <div className="p-2">
              {done.length === 0 ? <Empty text="无已完成测评" /> : done.map((a) => (
                <button key={a.id} onClick={() => setSelId(a.id)}
                  className={`w-full text-left px-3 py-2.5 rounded-lg ${sel?.id === a.id ? "bg-brand-50" : "hover:bg-slate-50"}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-medium text-slate-800">{a.name}</span>
                      <Pill>{a.type}</Pill>
                    </div>
                    <span className="text-sm font-bold text-slate-700">{a.avgScore}分</span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1">{a.className} · {a.deadline} · {a.submission}/{a.total}人</div>
                </button>
              ))}
            </div>
          </Panel>
        </div>
      )}

      {/* 成绩分析详情 */}
      {sel && sel.gradeDist && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 md:gap-4">
          <Panel>
            <PanelHeader title={`${sel.name} · 成绩分布`} action={<DButton variant="outline" size="sm" onClick={() => alert("已导出成绩报告")}>导出报告</DButton>} />
            <div className="p-4 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sel.gradeDist}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="range" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip cursor={false} />
                  <Bar dataKey="count" name="人数" fill="#1e54e6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
          <Panel>
            <PanelHeader title="各模块正确率" />
            <div className="p-4 space-y-2">
              {sel.correctRate?.map((c) => (
                <div key={c.module} className="flex items-center gap-3">
                  <span className="w-28 text-sm text-slate-600">{c.module}</span>
                  <div className="flex-1 h-3 rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${c.rate}%`, background: c.rate >= 70 ? "#22c55e" : c.rate >= 60 ? "#f59e0b" : "#ef4444" }} />
                  </div>
                  <span className="text-xs text-slate-500 w-10 text-right">{c.rate}%</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}

      {publishOpen && (
        <div className="fixed inset-0 z-40 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setPublishOpen(false)} />
          <Panel className="relative w-96 p-5">
            <h3 className="font-medium text-slate-800 mb-3">发布测评</h3>
            <p className="text-sm text-slate-500">选择测评类型、指定班级、设置截止时间后发布。完整表单将在班级学情页配置。</p>
            <div className="flex justify-end mt-4"><DButton size="sm" onClick={() => setPublishOpen(false)}>关闭</DButton></div>
          </Panel>
        </div>
      )}
    </div>
  );
}
