import { useNavigate } from "react-router-dom";
import { useGet } from "../api/hooks";
import { Card, Tag, ProgressBar, Skeleton, ErrorRetry } from "../components/ui";
import { levelLabel } from "../lib/mastery";
import { RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer, Radar } from "recharts";

interface Profile {
  name: string; grade: string; level: number; beatPercent: number;
  studyHours: number; assessmentCount: number;
  radar: { dimension: string; value: number }[];
}
interface TodayTask { id: string; title: string; questionCount: number; estMinutes: number; progress: number; kpId: string; type: string; }
interface Todos { pendingAssessment: number; pendingRetest: number; pendingCorrection: number; }
interface Bit { title: string; content: string; kpId: string; }

export default function Home() {
  const navigate = useNavigate();
  const profile = useGet<Profile>("/profile");
  const task = useGet<TodayTask>("/today-task");
  const todos = useGet<Todos>("/todos");
  const bit = useGet<Bit>("/bits");

  return (
    <div className="pb-2">
      {/* 顶部导航 */}
      <header className="bg-gradient-to-r from-brand-500 to-brand-600 text-white px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">📖</span>
          <span className="font-bold">语文学习评价</span>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="opacity-90">{profile.data?.grade}</span>
          <button>🔔</button>
          <button onClick={() => navigate("/growth")}>👤</button>
        </div>
      </header>

      {/* 综合数据概览 */}
      <Card className="-mt-4 bg-gradient-to-br from-brand-500 to-brand-700 text-white">
        {profile.loading ? <Skeleton className="h-24 w-full" /> : profile.error ? <ErrorRetry onRetry={profile.refetch} /> : (
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <div className="text-xs opacity-80">综合水平</div>
              <div className="text-4xl font-bold">{levelLabel(profile.data!.level)}<span className="text-lg ml-1">{profile.data!.level}级</span></div>
              <div className="text-xs opacity-80 mt-1">击败 {profile.data!.beatPercent}% 的同年级学生</div>
              <div className="flex gap-4 mt-2 text-xs">
                <span>⏱ {profile.data!.studyHours}h</span>
                <span>📝 {profile.data!.assessmentCount}次测评</span>
              </div>
            </div>
            <div className="w-28 h-28">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={profile.data!.radar} cx="50%" cy="50%" outerRadius="70%">
                  <PolarGrid stroke="rgba(255,255,255,0.3)" />
                  <PolarAngleAxis dataKey="dimension" tick={{ fill: "rgba(255,255,255,0.8)", fontSize: 9 }} />
                  <Radar name="素养" dataKey="value" stroke="#fff" fill="rgba(255,255,255,0.4)" />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </Card>

      {/* 今日学习任务 */}
      <Card>
        <div className="flex items-center justify-between mb-2">
          <Tag>今日任务</Tag>
          <span className="text-xs text-slate-400">{task.data?.type}</span>
        </div>
        {task.loading ? <Skeleton className="h-12 w-full" /> : task.error ? <ErrorRetry onRetry={task.refetch} /> : (
          <div className="flex items-center gap-3" onClick={() => navigate(`/study/${task.data!.kpId}`)}>
            <div className="flex-1">
              <div className="font-medium text-slate-900">{task.data!.title}</div>
              <div className="text-xs text-slate-500 mt-0.5">{task.data!.questionCount}题 · 约{task.data!.estMinutes}分钟</div>
              <div className="mt-2"><ProgressBar value={task.data!.progress} /></div>
            </div>
            <button className="bg-brand-500 text-white px-4 py-2 rounded-xl text-sm font-medium">去学习</button>
          </div>
        )}
      </Card>

      {/* 待办提醒 */}
      <div className="px-3 my-2">
        <div className="text-sm font-medium text-slate-700 mb-2">待办提醒</div>
        <div className="flex gap-3 overflow-x-auto no-scrollbar pb-1">
          <TodoCard label="待测评" count={todos.data?.pendingAssessment ?? 0} onClick={() => navigate("/assess")} />
          <TodoCard label="待复测" count={todos.data?.pendingRetest ?? 0} onClick={() => navigate("/growth")} />
          <TodoCard label="待订正错题" count={todos.data?.pendingCorrection ?? 0} onClick={() => navigate("/errors")} />
        </div>
      </div>

      {/* 快捷入口 */}
      <div className="px-3 my-2">
        <div className="grid grid-cols-4 gap-3">
          <Shortcut icon="📝" label="测评中心" onClick={() => navigate("/assess")} />
          <Shortcut icon="🗺️" label="知识画像" onClick={() => navigate("/knowledge")} />
          <Shortcut icon="📚" label="学习中心" onClick={() => navigate("/plan")} />
          <Shortcut icon="❌" label="错题本" onClick={() => navigate("/errors")} />
        </div>
      </div>

      {/* 每日一识 */}
      <Card>
        <div className="flex items-center gap-3">
          <span className="text-2xl">💡</span>
          <div className="flex-1">
            <div className="text-xs text-brand-600 font-medium">{bit.data?.title}</div>
            <div className="text-sm text-slate-700 mt-1 leading-relaxed">{bit.data?.content}</div>
          </div>
          <button onClick={() => bit.data && navigate(`/study/${bit.data.kpId}`)} className="text-brand-600 text-sm">查看详情 ›</button>
        </div>
      </Card>
    </div>
  );
}

function TodoCard({ label, count, onClick }: { label: string; count: number; onClick: () => void }) {
  return (
    <button onClick={onClick} className="relative bg-white rounded-2xl shadow-sm p-3 min-w-[6.5rem] text-left">
      {count > 0 && <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />}
      <div className="text-2xl font-bold text-slate-900">{count}</div>
      <div className="text-xs text-slate-500 mt-0.5">{label}</div>
    </button>
  );
}

function Shortcut({ icon, label, onClick }: { icon: string; label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="bg-white rounded-2xl shadow-sm py-4 flex flex-col items-center gap-1">
      <span className="text-2xl">{icon}</span>
      <span className="text-xs text-slate-600">{label}</span>
    </button>
  );
}
