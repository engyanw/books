import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGet, usePost } from "../api/hooks";
import { TopNav, Card, Tag, Button, Sheet, Skeleton, ErrorRetry } from "../components/ui";

interface Assessment { id: string; type: string; title: string; desc: string; duration: string; count: number; tag: string; action: string; }
interface Unit { id: string; name: string; module: string; }
interface Stage { id: string; name: string; desc: string; }
interface History { id: string; name: string; date: string; score: number; level: number; reportId: string; }

export default function AssessCenter() {
  const navigate = useNavigate();
  const list = useGet<Assessment[]>("/assessments");
  const history = useGet<History[]>("/assessments/history");
  const units = useGet<Unit[]>("/assessments/units");
  const stages = useGet<Stage[]>("/assessments/stages");
  const post = usePost();
  const [sheetType, setSheetType] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function startSession(type: string, unitId?: string, stageId?: string) {
    setSheetType(null);
    setBusy(true);
    try {
      const res = await post<{ sessionId: string }>("/assessments/sessions", { type, unitId, stageId });
      navigate(`/assess/answer/${res.sessionId}`);
    } finally { setBusy(false); }
  }

  return (
    <div>
      <TopNav title="测评中心" back={false} right={<button onClick={() => navigate("/growth")} className="text-sm">复测记录</button>} />
      <div className="p-3 text-sm text-slate-500 bg-brand-50/50">根据你的作答情况，系统将自适应调整题目难度，精准定位知识漏洞</div>

      {busy && <div className="text-center py-8 text-brand-600 text-sm">正在准备测评…</div>}

      <div className="px-3 mt-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {list.loading ? <Skeleton className="h-32 w-full" /> : list.error ? <ErrorRetry onRetry={list.refetch} /> : list.data!.map((a) => (
          <Card key={a.id} className="space-y-3 h-full flex flex-col" flush>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium text-slate-900">{a.title}</h3>
                  <Tag>{a.type}</Tag>
                </div>
                <p className="text-sm text-slate-500 mt-1 leading-relaxed">{a.desc}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <Tag color="slate">{a.duration}</Tag>
              <Tag color="slate">{a.count}题</Tag>
              <Tag color="amber">{a.tag}</Tag>
            </div>
            <div className="flex justify-end mt-auto">
              <Button onClick={() => {
                if (a.id === "a1") startSession("a1");
                else if (a.id === "a2") setSheetType("a2");
                else setSheetType("a3");
              }}>{a.action}</Button>
            </div>
          </Card>
        ))}
      </div>

      {/* 历史 */}
      <div className="px-3 mt-4">
        <h3 className="font-medium text-slate-700 mb-2">历史测评</h3>
        <Card className="p-0 overflow-hidden">
          {history.loading ? <Skeleton className="h-24 w-full" /> : history.error ? <ErrorRetry onRetry={history.refetch} /> : history.data!.map((h, i) => (
            <div key={h.id} className={`flex items-center px-4 py-3 ${i ? "border-t border-slate-100" : ""}`}>
              <div className="flex-1">
                <div className="text-sm font-medium text-slate-800">{h.name}</div>
                <div className="text-xs text-slate-400 mt-0.5">{h.date}</div>
              </div>
              <div className="text-right mr-3">
                <span className="text-lg font-bold text-slate-900">{h.score}</span>
                <span className="text-xs text-slate-400 ml-1">分 · {h.level}级</span>
              </div>
              <Button size="sm" variant="outline" onClick={() => navigate(`/report/${h.reportId}`)}>查看报告</Button>
            </div>
          ))}
        </Card>
      </div>

      {/* 单元选择浮层 */}
      <Sheet open={sheetType === "a2"} onClose={() => setSheetType(null)} title="选择单元">
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {units.loading ? <Skeleton className="h-32 w-full" /> : units.data?.map((u) => (
            <button key={u.id} onClick={() => startSession("a2", u.id)}
              className="w-full text-left p-3 rounded-xl bg-slate-50 hover:bg-brand-50">
              <div className="text-sm font-medium text-slate-800">{u.name}</div>
              <div className="text-xs text-slate-400">{u.module}</div>
            </button>
          ))}
        </div>
      </Sheet>

      {/* 阶段选择浮层 */}
      <Sheet open={sheetType === "a3"} onClose={() => setSheetType(null)} title="选择阶段">
        <div className="space-y-2">
          {stages.data?.map((s) => (
            <button key={s.id} onClick={() => startSession("a3", undefined, s.id)}
              className="w-full text-left p-3 rounded-xl bg-slate-50 hover:bg-brand-50">
              <div className="text-sm font-medium text-slate-800">{s.name}</div>
              <div className="text-xs text-slate-400">{s.desc}</div>
            </button>
          ))}
        </div>
      </Sheet>
    </div>
  );
}
