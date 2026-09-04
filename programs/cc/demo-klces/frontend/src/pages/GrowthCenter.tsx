import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGet, usePost } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { TopNav, Card, Button, Sheet, Loading, ErrorRetry, ProgressBar, Tag } from "../components/ui";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

interface GrowthData {
  series: { date: string; score: number; mastery: number }[];
  stats: { assessmentCount: number; studyHours: number; masteredPoints: number; improvedModules: number; };
  goal: { content: string; progress: number; targetScore: number; targetMastery: number; };
}
type Range = "week" | "month" | "semester";

export default function GrowthCenter() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [range, setRange] = useState<Range>("week");
  const data = useGet<GrowthData>(`/growth?range=${range}`);
  const post = usePost();
  const [goalOpen, setGoalOpen] = useState(false);
  const [gScore, setGScore] = useState(85);
  const [gMastery, setGMastery] = useState(80);
  const [gContent, setGContent] = useState("");

  if (data.loading) return <><TopNav title="成长中心" back={false} /><Loading /></>;
  if (data.error) return <><TopNav title="成长中心" back={false} /><ErrorRetry onRetry={data.refetch} /></>;
  const d = data.data!;

  async function saveGoal() {
    await post("/growth/goal", { content: gContent || d.goal.content, targetScore: gScore, targetMastery: gMastery });
    setGoalOpen(false);
    data.refetch();
  }

  return (
    <div>
      <TopNav title="成长中心" back={false} />

      {/* 时间维度 */}
      <div className="flex p-3 gap-2">
        {([["week", "周"], ["month", "月"], ["semester", "学期"]] as [Range, string][]).map(([k, label]) => (
          <button key={k} onClick={() => setRange(k)}
            className={`flex-1 py-2 rounded-xl text-sm ${range === k ? "bg-brand-500 text-white" : "bg-white text-slate-500 shadow-sm"}`}>
            {label}
          </button>
        ))}
      </div>

      {/* 成长曲线 */}
      <Card>
        <h3 className="text-sm font-medium text-slate-700 mb-2">成长曲线</h3>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={d.series} margin={{ left: -20, right: 10, top: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} interval={range === "week" ? 0 : Math.floor(d.series.length / 6)} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="score" name="综合成绩" stroke="#1e54e6" strokeWidth={2} dot={{ r: 2 }} />
              <Line type="monotone" dataKey="mastery" name="平均掌握度" stroke="#22c55e" strokeWidth={2} dot={{ r: 2 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* 数据统计 */}
      <div className="px-3 mt-2 grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat icon="📝" label="测评次数" value={`${d.stats.assessmentCount}次`} />
        <Stat icon="⏱️" label="累计学习时长" value={`${d.stats.studyHours}h`} />
        <Stat icon="✅" label="已掌握知识点" value={`${d.stats.masteredPoints}个`} />
        <Stat icon="📈" label="提升模块数" value={`${d.stats.improvedModules}个`} />
      </div>

      {/* 目标管理 */}
      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-slate-700">我的学习目标</h3>
          <Button size="sm" variant="outline" onClick={() => setGoalOpen(true)}>设置目标</Button>
        </div>
        <p className="text-sm text-slate-600 mt-2">{d.goal.content}</p>
        <div className="mt-2"><ProgressBar value={d.goal.progress} /></div>
        <div className="flex justify-between text-xs text-slate-400 mt-1">
          <span>进度 {d.goal.progress}%</span>
          <span>目标：总分{d.goal.targetScore} · 掌握度{d.goal.targetMastery}%</span>
        </div>
      </Card>

      {/* 设置目标弹窗 */}
      <Sheet open={goalOpen} onClose={() => setGoalOpen(false)} title="设置学习目标">
        <div className="space-y-4">
          <div>
            <label className="text-sm text-slate-500">目标内容</label>
            <textarea value={gContent} onChange={(e) => setGContent(e.target.value)} rows={2} placeholder={d.goal.content}
              className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-brand-500 outline-none resize-none" />
          </div>
          <div>
            <label className="text-sm text-slate-500">目标总分：{gScore}分</label>
            <input type="range" min={60} max={100} value={gScore} onChange={(e) => setGScore(+e.target.value)} className="w-full mt-1 accent-brand-500" />
          </div>
          <div>
            <label className="text-sm text-slate-500">目标掌握度：{gMastery}%</label>
            <input type="range" min={60} max={100} value={gMastery} onChange={(e) => setGMastery(+e.target.value)} className="w-full mt-1 accent-brand-500" />
          </div>
          <Button className="w-full" onClick={saveGoal}>生成目标拆解方案</Button>
        </div>
      </Sheet>

      {/* 账号 */}
      <Card>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-brand-500 text-white grid place-items-center font-bold">{user?.name?.slice(0,1)}</div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-slate-900 truncate">{user?.name}</div>
            <div className="text-xs text-slate-400 truncate">{user?.username} · {[user?.grade, user?.className].filter(Boolean).join(" ")}</div>
          </div>
          <Button size="sm" variant="outline" onClick={() => navigate("/account")}>账号设置</Button>
          <Button size="sm" variant="ghost" onClick={logout}>退出</Button>
        </div>
      </Card>
    </div>
  );
}

function Stat({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm p-4 flex items-center gap-3">
      <span className="text-2xl">{icon}</span>
      <div>
        <div className="text-xs text-slate-400">{label}</div>
        <div className="text-lg font-bold text-slate-900">{value}</div>
      </div>
    </div>
  );
}
