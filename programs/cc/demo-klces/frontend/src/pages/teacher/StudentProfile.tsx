import { useState } from "react";
import { useParams } from "react-router-dom";
import { useGet, usePost } from "../../api/hooks";
import { Panel, PanelHeader, Pill, DButton, Spinner, Empty, masteryColor } from "../../components/desktop";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

interface Student { id: string; name: string; className: string; avgScore: number; level: number; rank: number; note: string; }
interface GraphModule { id: string; name: string; mastery: number; units: { knowledgePoints: { mastery: number }[] }[]; }
interface Growth { series: { date: string; score: number; mastery: number }[]; }
interface ErrItem { id: string; stem: string; errorType: string; date: string; }

const LEVELS = ["", "入门", "基础", "合格", "良好", "优秀"];

export default function StudentProfile() {
  const { id } = useParams();
  const s = useGet<Student>(`/teacher/students/${id}`);
  const graph = useGet<GraphModule[]>("/knowledge-graph");
  const growth = useGet<Growth>("/growth?range=month");
  const errs = useGet<ErrItem[]>("/errors");
  const post = usePost();
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(false);

  if (s.loading) return <Spinner />;
  if (s.error) return <Empty text="学生不存在" />;
  const st = s.data!;
  if (note === "" && !saved) setNote(st.note);

  async function saveNote() {
    await post(`/teacher/students/${id}/note`, { note });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="space-y-4">
      {/* 学生信息栏 */}
      <Panel className="p-5 flex items-center gap-4">
        <div className="w-14 h-14 rounded-full bg-brand-500 text-white flex items-center justify-center text-xl font-bold">
          {st.name.charAt(0)}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-lg font-medium text-slate-900">{st.name}</span>
            <Pill color="brand">{st.className}</Pill>
          </div>
          <div className="text-sm text-slate-500 mt-1">平均分 {st.avgScore} · 水平 {LEVELS[st.level]} · 班级排名 第{st.rank}名</div>
        </div>
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 md:gap-4">
        {/* 知识图谱（模块掌握度） */}
        <Panel>
          <PanelHeader title="知识图谱 · 模块掌握度" />
          <div className="p-4 space-y-3">
            {(graph.data || []).map((m) => (
              <div key={m.id}>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-slate-700">{m.name}</span>
                  <span className="text-slate-500">{m.mastery}%</span>
                </div>
                <div className="h-2.5 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${m.mastery}%`, background: masteryColor(m.mastery) }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>

        {/* 成长曲线 */}
        <Panel>
          <PanelHeader title="成长曲线" />
          <div className="p-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={growth.data?.series || []} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 9 }} interval={4} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="score" name="成绩" stroke="#1e54e6" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="mastery" name="掌握度" stroke="#22c55e" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 md:gap-4">
        {/* 错题记录 */}
        <Panel>
          <PanelHeader title="近期错题记录" />
          <div className="p-2">
            {errs.data?.length === 0 ? <Empty /> : errs.data?.slice(0, 5).map((e) => (
              <div key={e.id} className="px-3 py-2 hover:bg-slate-50 rounded-lg">
                <div className="flex items-center justify-between">
                  <Pill color="red">{e.errorType}</Pill>
                  <span className="text-xs text-slate-400">{e.date}</span>
                </div>
                <p className="text-sm text-slate-700 mt-1 line-clamp-2">{e.stem}</p>
              </div>
            ))}
          </div>
        </Panel>

        {/* 教师备注 */}
        <Panel>
          <PanelHeader title="教师备注 · 个性化学习建议" />
          <div className="p-4">
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={6}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm outline-none focus:border-brand-500 resize-none"
              placeholder="输入个性化学习建议，保存后将同步至学生端…" />
            <div className="flex items-center justify-between mt-3">
              <span className="text-xs text-green-600">{saved ? "✓ 已保存并同步至学生端" : ""}</span>
              <DButton size="sm" onClick={saveNote}>保存备注</DButton>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
