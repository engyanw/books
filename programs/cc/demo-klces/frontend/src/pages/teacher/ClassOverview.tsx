import { useState } from "react";
import { Link } from "react-router-dom";
import { useGet, usePost } from "../../api/hooks";
import { Panel, PanelHeader, Pill, DButton, Spinner, Empty, masteryColor } from "../../components/desktop";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from "recharts";

interface ClassSummary { id: string; name: string; studentCount: number; avgScore: number; }
interface WeakPoint { kpId: string; name: string; module: string; errorRate: number; }
interface Student { id: string; name: string; score: number; level: number; mastery: number; trend: number; }
interface ClassDetail {
  id: string; name: string; studentCount: number; avgScore: number; avgMastery: number;
  levelDist: { level: number; count: number }[];
  weakPoints: WeakPoint[];
  students: Student[];
}
const LEVEL_NAMES = ["", "入门", "基础", "合格", "良好", "优秀"];

export default function ClassOverview() {
  const classes = useGet<ClassSummary[]>("/teacher/classes");
  const [cid, setCid] = useState("c1");
  const detail = useGet<ClassDetail>(`/teacher/classes/${cid}`);
  const post = usePost();
  const [publishOpen, setPublishOpen] = useState(false);

  return (
    <div className="space-y-4">
      {/* 班级切换 + 操作 */}
      <Panel className="px-4 md:px-5 py-3 flex items-center gap-2 md:gap-3 flex-wrap">
        <span className="text-sm text-slate-500">班级：</span>
        {classes.data?.map((c) => (
          <button key={c.id} onClick={() => setCid(c.id)}
            className={`px-3 py-1 rounded-lg text-sm ${cid === c.id ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-600"}`}>
            {c.name}
          </button>
        ))}
        <div className="ml-auto flex gap-2">
          <DButton variant="outline" size="sm" onClick={() => setPublishOpen(true)}>布置专项训练</DButton>
          <DButton size="sm" onClick={() => setPublishOpen(true)}>+ 发布班级测评</DButton>
        </div>
      </Panel>

      {detail.loading ? <Spinner /> : detail.error ? <Empty text="加载失败" /> : (() => {
        const d = detail.data!;
        return (
          <>
            {/* 整体数据卡 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
              <StatCard label="班级人数" value={`${d.studentCount}人`} />
              <StatCard label="平均分" value={`${d.avgScore}分`} />
              <StatCard label="平均掌握度" value={`${d.avgMastery}%`} />
              <StatCard label="优秀率(良好及以上)" value={`${Math.round(((d.levelDist.find((x) => x.level === 4)?.count ?? 0) + (d.levelDist.find((x) => x.level === 5)?.count ?? 0)) / d.studentCount * 100)}%`} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 md:gap-4">
              {/* 水平分布 */}
              <Panel>
                <PanelHeader title="学业水平分布" />
                <div className="p-4 h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={d.levelDist.map((x) => ({ name: LEVEL_NAMES[x.level], 人数: x.count }))}>
                      <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip cursor={false} />
                      <Bar dataKey="人数" radius={[4, 4, 0, 0]}>
                        {d.levelDist.map((x, i) => <Cell key={i} fill={x.level >= 4 ? "#22c55e" : x.level >= 3 ? "#f59e0b" : "#ef4444"} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Panel>

              {/* 共性短板榜 */}
              <Panel>
                <PanelHeader title="共性短板榜（班级错误率 TOP）" />
                <div className="p-2">
                  {d.weakPoints.map((w, i) => (
                    <div key={w.kpId} className="flex items-center gap-3 px-3 py-2 hover:bg-slate-50 rounded-lg">
                      <span className="w-5 h-5 rounded-full bg-red-100 text-red-500 text-xs flex items-center justify-center">{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-slate-800 truncate">{w.name}</div>
                        <div className="text-xs text-slate-400">{w.module}</div>
                      </div>
                      <div className="w-24 h-2 rounded-full bg-slate-100 overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${w.errorRate}%`, background: masteryColor(100 - w.errorRate) }} />
                      </div>
                      <span className="text-xs text-red-500 w-10 text-right">{w.errorRate}%</span>
                    </div>
                  ))}
                </div>
              </Panel>
            </div>

            {/* 学生列表 */}
            <Panel>
              <PanelHeader title="学生列表" action={<span className="text-xs text-slate-400">点击姓名查看学情档案</span>} />
              <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[560px]">
                <thead className="bg-slate-50 text-slate-500 text-xs">
                  <tr>
                    <th className="text-left px-5 py-2 font-medium">姓名</th>
                    <th className="text-left px-3 py-2 font-medium">得分</th>
                    <th className="text-left px-3 py-2 font-medium">水平</th>
                    <th className="text-left px-3 py-2 font-medium">掌握度</th>
                    <th className="text-left px-3 py-2 font-medium">较上次</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {d.students.map((s) => (
                    <tr key={s.id} className="border-t border-slate-100 hover:bg-slate-50">
                      <td className="px-5 py-2.5 font-medium text-slate-800">{s.name}</td>
                      <td className="px-3 py-2.5 text-slate-700">{s.score}</td>
                      <td className="px-3 py-2.5"><Pill color={s.level >= 4 ? "green" : s.level >= 3 ? "amber" : "red"}>{LEVEL_NAMES[s.level]}</Pill></td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${s.mastery}%`, background: masteryColor(s.mastery) }} />
                          </div>
                          <span className="text-xs text-slate-500">{s.mastery}%</span>
                        </div>
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={s.trend >= 0 ? "text-green-600" : "text-red-500"}>{s.trend >= 0 ? "▲" : "▼"}{Math.abs(s.trend)}</span>
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <Link to={`/teacher/student/${s.id}`} className="text-brand-600 hover:underline">查看档案</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </Panel>
          </>
        );
      })()}

      {/* 发布测评弹层（简化） */}
      {publishOpen && (
        <PublishModal onClose={() => setPublishOpen(false)} onPublish={async (name) => {
          await post("/teacher/assessments", { name, type: "单元专项", className: classes.data?.find((c) => c.id === cid)?.name, deadline: "2026-09-10" });
          setPublishOpen(false);
          alert("已发布：" + name);
        }} />
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Panel className="p-4">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="text-2xl font-bold text-slate-900 mt-1">{value}</div>
    </Panel>
  );
}

function PublishModal({ onClose, onPublish }: { onClose: () => void; onPublish: (name: string) => void }) {
  const [name, setName] = useState("");
  const [type, setType] = useState("单元专项");
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <Panel className="relative w-96 p-5">
        <h3 className="font-medium text-slate-800 mb-3">发布测评</h3>
        <label className="text-xs text-slate-500">测评名称</label>
        <input value={name} onChange={(e) => setName(e.target.value)} className="w-full mt-1 mb-3 px-3 py-2 rounded-lg border border-slate-300 text-sm outline-none focus:border-brand-500" placeholder="如：文言虚词专项训练" />
        <label className="text-xs text-slate-500">测评类型</label>
        <select value={type} onChange={(e) => setType(e.target.value)} className="w-full mt-1 mb-4 px-3 py-2 rounded-lg border border-slate-300 text-sm outline-none">
          <option>入门诊断</option><option>单元专项</option><option>阶段综合</option>
        </select>
        <div className="flex justify-end gap-2">
          <DButton variant="outline" size="sm" onClick={onClose}>取消</DButton>
          <DButton size="sm" onClick={() => onPublish(name || type)} disabled={!name}>确认发布</DButton>
        </div>
      </Panel>
    </div>
  );
}
