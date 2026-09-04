import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useGet, usePost } from "../api/hooks";
import { TopNav, Card, Tag, Button, Loading, ErrorRetry, ProgressBar, Sheet, Confirm } from "../components/ui";

interface Study {
  lecture: string[];
  examples: { stem: string; answer: string; analysis: string; scoringPoints?: string[] }[];
  training: string[]; // question ids
}
interface KpDetail { id: string; name: string; mastery: number; errorCount: number; moduleName: string; unitName: string; }
interface TrainRes { score: number; correct: number; total: number; correctRate: number; mastery: number; }

export default function KnowledgeStudy() {
  const { kpId } = useParams();
  const navigate = useNavigate();
  const study = useGet<Study>(`/knowledge-points/${kpId}/study`);
  const kp = useGet<KpDetail>(`/knowledge-points/${kpId}`);
  const post = usePost();
  const [tab, setTab] = useState(0);
  const [openExample, setOpenExample] = useState<number | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<TrainRes | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [confirmDone, setConfirmDone] = useState(false);

  if (study.loading) return <><TopNav title="知识点学习" /><Loading /></>;
  if (study.error) return <><TopNav title="知识点学习" /><ErrorRetry onRetry={study.refetch} /></>;

  const s = study.data!;
  const mastery = kp.data?.mastery ?? 0;

  async function submitTrain() {
    setSubmitting(true);
    const res = await post<TrainRes>(`/knowledge-points/${kpId}/train`, { answers });
    setResult(res); setSubmitting(false);
    kp.refetch();
  }

  return (
    <div className="min-h-screen flex flex-col">
      <TopNav title={kp.data?.name ?? "知识点学习"}
        right={<Tag color="brand">掌握度 {mastery}%</Tag>} />

      {/* Tab */}
      <div className="sticky top-12 bg-slate-50 z-10 flex border-b border-slate-200">
        {["知识讲解", "典型例题", "专项训练"].map((t, i) => (
          <button key={t} onClick={() => setTab(i)} className={`flex-1 py-3 text-sm relative ${tab === i ? "text-brand-600 font-medium" : "text-slate-500"}`}>
            {t}{tab === i && <span className="absolute bottom-0 left-1/4 right-1/4 h-0.5 bg-brand-500 rounded-full" />}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3 pb-24">
        {tab === 0 && (
          <Card>
            {s.lecture.map((p, i) => <p key={i} className="text-sm text-slate-700 leading-relaxed mb-3">{p}</p>)}
            <div className="mt-2"><ProgressBar value={mastery} /></div>
          </Card>
        )}

        {tab === 1 && (
          <div className="space-y-3">
            {s.examples.map((ex, i) => (
              <Card key={i}>
                <p className="text-sm text-slate-800 font-medium">{ex.stem}</p>
                {openExample === i ? (
                  <div className="mt-3 text-sm">
                    <div className="p-2 rounded bg-green-50 text-green-700 mb-2">答案：{ex.answer}</div>
                    <div className="text-slate-600 leading-relaxed">解析：{ex.analysis}</div>
                    {ex.scoringPoints && (
                      <div className="mt-2 flex flex-wrap gap-1">{ex.scoringPoints.map((p, j) => <Tag key={j} color="amber">得分点 {p}</Tag>)}</div>
                    )}
                  </div>
                ) : (
                  <Button size="sm" variant="outline" className="mt-3" onClick={() => setOpenExample(i)}>查看解析</Button>
                )}
              </Card>
            ))}
          </div>
        )}

        {tab === 2 && (
          <div className="space-y-3">
            <div className="text-xs text-slate-500 text-center">共 {s.training.length} 道训练题，完成提交后即时判分</div>
            {s.training.map((qid, i) => (
              <Card key={qid}>
                <div className="text-xs text-slate-400 mb-1">第 {i + 1} 题（{qid}）</div>
                <input value={answers[qid] ?? ""} onChange={(e) => setAnswers((a) => ({ ...a, [qid]: e.target.value }))}
                  placeholder="输入答案（选择题填 A/B/C/D）"
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-brand-500 outline-none" />
              </Card>
            ))}
            {result && (
              <Card className="bg-brand-50">
                <div className="text-center">
                  <div className="text-3xl font-bold text-brand-600">{result.score}分</div>
                  <div className="text-xs text-slate-500 mt-1">正确率 {result.correctRate}% · {result.correct}/{result.total} · 掌握度更新至 {result.mastery}%</div>
                </div>
              </Card>
            )}
            <Button className="w-full" disabled={submitting} onClick={submitTrain}>{submitting ? "提交中…" : "提交训练"}</Button>
          </div>
        )}
      </div>

      {/* 底部操作 */}
      <footer className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-md bg-white border-t border-slate-200 px-3 py-2 flex gap-2">
        <Button variant="outline" className="flex-1" onClick={() => navigate("/errors")}>❤ 收藏知识点</Button>
        <Button className="flex-1" disabled={!done && !result} onClick={() => setConfirmDone(true)}>✓ 打卡完成</Button>
      </footer>
      <div className="h-14" />

      <Confirm open={confirmDone} title="打卡完成" message="确认完成本知识点的学习与训练？"
        onConfirm={() => { setDone(true); setConfirmDone(false); navigate(-1); }} onCancel={() => setConfirmDone(false)} />
    </div>
  );
}
