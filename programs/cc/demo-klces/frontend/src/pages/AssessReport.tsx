import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { get, post } from "../api/client";
import { TopNav, Card, Tag, Button, Loading, Sheet, Confirm } from "../components/ui";
import { levelLabel, masteryColor } from "../lib/mastery";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, PieChart, Pie, Tooltip, Legend } from "recharts";

interface Report {
  id: string; score: number; level: number; beatPercent: number; conclusion: string;
  modules: { id: string; name: string; scoreRate: number }[];
  gaps: { id: string; name: string; mastery: number; module: string; priority: string }[];
  errorCauses: { type: string; percent: number; desc: string }[];
  planSummary: { cycle: string; goal: string; stages: string[] };
}

const CAUSE_COLORS = ["#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6"];

export default function AssessReport() {
  const { id } = useParams();
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState(0);
  const [selectedCause, setSelectedCause] = useState(0);
  const [genConfirm, setGenConfirm] = useState(false);

  useEffect(() => {
    const fresh = sp.get("fresh") === "1";
    const delay = fresh ? 1600 : 300;
    const t = setTimeout(() => {
      get<Report>(`/reports/${id}`).then((d) => { setReport(d); setLoading(false); });
    }, delay);
    return () => clearTimeout(t);
  }, [id]);

  async function generatePlan() {
    setGenConfirm(false);
    await post("/knowledge-points/dummy"); // no-op to demonstrate async
    navigate("/plan");
  }

  if (loading) return <Loading text="正在生成你的知识诊断报告…" />;

  const r = report!;
  return (
    <div>
      <TopNav title="测评报告" right={<button className="text-lg">↗</button>} />
      {/* 总体结论 */}
      <Card className="text-center">
        <div className="text-5xl font-bold text-slate-900">{r.score}<span className="text-lg text-slate-400 ml-1">分</span></div>
        <div className="mt-2"><Tag color="brand">学业质量水平：{levelLabel(r.level)}（{r.level}级）</Tag></div>
        <div className="text-xs text-slate-400 mt-1">击败 {r.beatPercent}% 同年级学生</div>
        <p className="mt-3 text-sm text-slate-600 leading-relaxed bg-slate-50 rounded-xl p-3">{r.conclusion}</p>
      </Card>

      {/* Tab 栏 */}
      <div className="sticky top-12 bg-slate-50 z-10 flex border-b border-slate-200">
        {["模块详情", "漏洞清单", "错误归因", "提升方案"].map((t, i) => (
          <button key={t} onClick={() => setTab(i)}
            className={`flex-1 py-3 text-sm relative ${tab === i ? "text-brand-600 font-medium" : "text-slate-500"}`}>
            {t}
            {tab === i && <span className="absolute bottom-0 left-1/4 right-1/4 h-0.5 bg-brand-500 rounded-full" />}
          </button>
        ))}
      </div>

      <div className="pb-4">
        {tab === 0 && (
          <Card>
            <h3 className="font-medium text-slate-700 mb-3">五大模块得分率</h3>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={r.modules} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <YAxis type="category" dataKey="name" width={70} tick={{ fontSize: 10 }} />
                  <Bar dataKey="scoreRate" radius={[0, 4, 4, 0]}>
                    {r.modules.map((m) => <Cell key={m.id} fill={masteryColor(m.scoreRate)} />)}
                  </Bar>
                  <Tooltip cursor={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 space-y-1.5">
              {r.modules.map((m) => (
                <div key={m.id} className="flex items-center justify-between text-sm">
                  <span className={m.scoreRate < 60 ? "text-red-500 font-medium" : "text-slate-700"}>{m.name}</span>
                  <span className={m.scoreRate < 60 ? "text-red-500" : "text-slate-500"}>{m.scoreRate}%</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {tab === 1 && (
          <Card>
            <h3 className="font-medium text-slate-700 mb-2">漏洞清单（按优先级）</h3>
            <div className="space-y-2">
              {r.gaps.map((g) => (
                <div key={g.id} className="p-3 rounded-xl bg-slate-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full" style={{ background: masteryColor(g.mastery) }} />
                      <span className="text-sm font-medium text-slate-800">{g.name}</span>
                    </div>
                    {g.priority === "优先补漏" && <Tag color="red">优先补漏</Tag>}
                  </div>
                  <div className="flex items-center justify-between mt-1 text-xs text-slate-400">
                    <span>{g.module} · 掌握度 {g.mastery}%</span>
                    <Button size="sm" variant="ghost" onClick={() => navigate(`/study/${g.id}`)}>去学习</Button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {tab === 2 && (
          <Card>
            <h3 className="font-medium text-slate-700 mb-3">错误归因</h3>
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={r.errorCauses} dataKey="percent" nameKey="type" cx="50%" cy="50%" outerRadius="60%"
                    onClick={(_, i) => setSelectedCause(i)}>
                    {r.errorCauses.map((_, i) => <Cell key={i} fill={CAUSE_COLORS[i]} />)}
                  </Pie>
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 p-3 rounded-xl bg-slate-50 text-sm text-slate-600 leading-relaxed">
              <span className="font-medium text-slate-700">{r.errorCauses[selectedCause].type}（{r.errorCauses[selectedCause].percent}%）：</span>
              {r.errorCauses[selectedCause].desc}
            </div>
          </Card>
        )}

        {tab === 3 && (
          <Card>
            <h3 className="font-medium text-slate-700 mb-2">提升方案</h3>
            <div className="flex items-center gap-2 mb-3">
              <Tag color="brand">周期 {r.planSummary.cycle}</Tag>
              <Tag color="amber">{r.planSummary.goal}</Tag>
            </div>
            <div className="space-y-2 mb-4">
              {r.planSummary.stages.map((s, i) => (
                <div key={i} className="flex gap-2 text-sm text-slate-600">
                  <span className="w-5 h-5 rounded-full bg-brand-100 text-brand-600 text-xs flex items-center justify-center flex-shrink-0">{i + 1}</span>
                  <span>{s}</span>
                </div>
              ))}
            </div>
            <Button className="w-full" onClick={() => setGenConfirm(true)}>生成完整提升方案</Button>
          </Card>
        )}
      </div>

      <Confirm open={genConfirm} title="生成提升方案" message="确认后将生成完整提升方案并设为当前执行方案，是否继续？"
        onConfirm={generatePlan} onCancel={() => setGenConfirm(false)} />
    </div>
  );
}
