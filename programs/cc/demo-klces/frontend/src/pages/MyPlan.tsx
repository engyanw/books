import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGet } from "../api/hooks";
import { TopNav, Card, Tag, Button, Sheet, Loading, ErrorRetry } from "../components/ui";

interface Plan { id: string; name: string; goal: string; totalDays: number; completionRate: number; stages: Stage[]; }
interface Stage { id: string; name: string; goal: string; knowledgePoints: string[]; estDays: number; status: string; }
interface Task { id: string; date: string; title: string; content: string; estMinutes: number; status: string; kpId: string; }

export default function MyPlan() {
  const navigate = useNavigate();
  const plan = useGet<Plan>("/plan/current");
  const tasks = useGet<Task[]>("/plan/tasks");
  const [stageDetail, setStageDetail] = useState<Stage | null>(null);

  if (plan.loading) return <><TopNav title="我的提升方案" back={false} /><Loading /></>;
  if (plan.error) return <><TopNav title="我的提升方案" back={false} /><ErrorRetry onRetry={plan.refetch} /></>;

  const p = plan.data!;
  return (
    <div>
      <TopNav title="我的提升方案" back={false} right={<button className="text-sm text-brand-600" onClick={() => navigate("/growth")}>历史方案</button>} />

      {/* 方案总览 */}
      <Card>
        <h3 className="font-medium text-slate-900">{p.name}</h3>
        <div className="flex items-center justify-between mt-2 text-sm">
          <div>
            <div className="text-xs text-slate-400">提升目标</div>
            <div className="text-slate-700">{p.goal}</div>
          </div>
          <div className="text-right">
            <div className="text-xs text-slate-400">总周期 · {p.totalDays}天</div>
            <div className="flex items-center gap-2 mt-1 justify-end">
              <div className="relative w-12 h-12">
                <svg viewBox="0 0 36 36" className="w-12 h-12 -rotate-90">
                  <circle cx="18" cy="18" r="15" fill="none" stroke="#e2e8f0" strokeWidth="4" />
                  <circle cx="18" cy="18" r="15" fill="none" stroke="#1e54e6" strokeWidth="4"
                    strokeDasharray={`${(p.completionRate / 100) * 94.2} 94.2`} strokeLinecap="round" />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-slate-700">{p.completionRate}%</span>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* 阶段进度轴 */}
      <div className="px-4 mt-2">
        <div className="flex items-center">
          {p.stages.map((s, i) => (
            <div key={s.id} className="flex-1 flex flex-col items-center" onClick={() => setStageDetail(s)}>
              <div className="w-full flex items-center">
                {i > 0 && <div className={`flex-1 h-0.5 ${p.stages[i - 1].status === "done" ? "bg-brand-500" : "bg-slate-200"}`} />}
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs ${
                  s.status === "done" ? "bg-brand-500 text-white" :
                  s.status === "current" ? "bg-brand-100 text-brand-600 ring-2 ring-brand-400" : "bg-slate-100 text-slate-400"
                }`}>{s.status === "done" ? "✓" : i + 1}</div>
                {i < p.stages.length - 1 && <div className={`flex-1 h-0.5 ${s.status === "done" ? "bg-brand-500" : "bg-slate-200"}`} />}
              </div>
              <span className={`text-xs mt-1 ${s.status === "current" ? "text-brand-600 font-medium" : "text-slate-400"}`}>{s.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 每日任务列表 */}
      <div className="px-3 mt-3">
        <h4 className="text-sm font-medium text-slate-700 mb-2">每日任务</h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {tasks.loading ? <Loading /> : tasks.data!.map((t) => (
          <div key={t.id} className={`rounded-2xl p-4 shadow-sm ${
            t.status === "today" ? "bg-gradient-to-br from-brand-50 to-white ring-1 ring-brand-200" :
            t.status === "done" ? "bg-slate-100 opacity-70" : "bg-white"
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-900">{t.title}</span>
                  {t.status === "today" && <Tag color="brand">今日</Tag>}
                  {t.status === "done" && <Tag color="green">已完成</Tag>}
                </div>
                <div className="text-xs text-slate-500 mt-1">{t.content}</div>
                <div className="text-xs text-slate-400 mt-1">{t.date} · 约{t.estMinutes}分钟</div>
              </div>
              {t.status === "today"
                ? <Button size="sm" onClick={() => navigate(`/study/${t.kpId}`)}>开始学习</Button>
                : t.status === "done"
                ? <span className="text-slate-300 text-xs">✓</span>
                : <Button size="sm" variant="outline" onClick={() => navigate(`/study/${t.kpId}`)}>预习</Button>}
            </div>
          </div>
        ))}
        </div>
      </div>

      <p className="text-xs text-slate-400 text-center my-4 px-6">方案会根据你的复测结果动态调整，确保学习效率最大化</p>

      <Sheet open={!!stageDetail} onClose={() => setStageDetail(null)} title={stageDetail?.name}>
        {stageDetail && (
          <div className="space-y-2 text-sm">
            <div><span className="text-slate-400">学习目标：</span><span className="text-slate-700">{stageDetail.goal}</span></div>
            <div><span className="text-slate-400">预计时长：</span><span className="text-slate-700">{stageDetail.estDays}天</span></div>
            <div><span className="text-slate-400">状态：</span><Tag color={stageDetail.status === "done" ? "green" : stageDetail.status === "current" ? "brand" : "slate"}>{stageDetail.status === "done" ? "已完成" : stageDetail.status === "current" ? "进行中" : "未开始"}</Tag></div>
          </div>
        )}
      </Sheet>
    </div>
  );
}
