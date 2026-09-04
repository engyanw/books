import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { get, post } from "../api/client";
import { Button, Sheet, Confirm, Loading, Tag } from "../components/ui";

interface Question {
  id: string; type: "choice" | "fill" | "short"; difficulty: number;
  material?: string; stem: string; options?: string[];
}
interface SessionState {
  question: Question; index: number; totalQuestions: number; finished?: boolean; reportId?: string;
}
interface AnswerRes {
  correct: boolean; correctAnswer?: string; analysis: string;
  next: Question | null; finished: boolean; index: number; totalQuestions: number;
}

export default function AssessAnswer() {
  const { sid } = useParams();
  const navigate = useNavigate();
  const [state, setState] = useState<SessionState | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [answered, setAnswered] = useState<Record<string, { answer: string; correct: boolean; marked: boolean; analysis: string; correctAnswer?: string }>>({});
  const [pendingNext, setPendingNext] = useState<Question | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [showCard, setShowCard] = useState(false);
  const [showSubmit, setShowSubmit] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    get<SessionState>(`/sessions/${sid}`).then((d) => {
      if (d.finished && d.reportId) { navigate(`/report/${d.reportId}`); return; }
      setState(d); setLoading(false);
    });
  }, [sid]);

  function selectOption(opt: string) {
    if (!state || selected || state.question.type === "short") return;
    setSelected(opt);
    submitAnswer(opt);
  }

  async function submitAnswer(answer: string, marked = false) {
    if (!state) return;
    const res = await post<AnswerRes>(`/sessions/${sid}/answer`, { questionId: state.question.id, answer, marked });
    setAnswered((prev) => ({ ...prev, [state.question.id]: { answer, correct: res.correct, marked, analysis: res.analysis, correctAnswer: res.correctAnswer } }));
    setPendingNext(res.next);
    setShowResult(true);
  }

  function next() {
    if (!pendingNext) { setShowSubmit(true); return; }
    setState({ question: pendingNext, index: state ? state.index + 1 : 1, totalQuestions: state?.totalQuestions ?? 0 });
    setSelected(null); setPendingNext(null); setShowResult(false);
  }

  async function submit() {
    setShowSubmit(false);
    setSubmitting(true);
    const res = await post<{ reportId: string }>(`/sessions/${sid}/submit`);
    setSubmitting(false);
    navigate(`/report/${res.reportId}?fresh=1`);
  }

  function toggleMark() {
    if (!state) return;
    const id = state.question.id;
    setAnswered((prev) => {
      const cur = prev[id];
      if (!cur) return { ...prev, [id]: { answer: "", correct: false, marked: true, analysis: "" } };
      return { ...prev, [id]: { ...cur, marked: !cur.marked } };
    });
  }

  if (loading || submitting) return <Loading text={submitting ? "提交中…" : "加载题目…"} />;

  const q = state!.question;
  const total = state!.totalQuestions;
  const isLast = state!.index >= total;
  const marked = !!answered[q.id]?.marked;
  const correctAns = answered[q.id];

  return (
    <div className="min-h-screen flex flex-col">
      {/* 顶部进度 */}
      <header className="sticky top-0 z-20 bg-white border-b border-slate-200 px-3 py-2 flex items-center gap-3">
        <button onClick={() => setShowSubmit(true)} className="text-2xl text-slate-700 leading-none">✕</button>
        <div className="flex-1">
          <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
            <div className="h-full bg-brand-500 transition-all" style={{ width: `${(state!.index / total) * 100}%` }} />
          </div>
        </div>
        <span className="text-xs text-slate-500 whitespace-nowrap">{state!.index}/{total}</span>
        <button onClick={toggleMark} className={`text-sm ${marked ? "text-amber-500" : "text-slate-400"}`}>🚩标记</button>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="flex items-center gap-2 mb-3">
          <Tag color="slate">难度 {q.difficulty}</Tag>
          {marked && <Tag color="amber">疑问</Tag>}
        </div>

        {q.material && (
          <div className="bg-amber-50/60 border-l-4 border-amber-300 rounded p-3 mb-3 text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
            {q.material}
          </div>
        )}

        <p className="text-slate-900 leading-relaxed mb-4">{q.stem}</p>

        {/* 作答区 */}
        <div className="space-y-2">
          {q.type === "choice" && q.options?.map((opt, i) => {
            const val = String.fromCharCode(65 + i);
            const isSel = selected === val;
            const correctVal = correctAns?.correctAnswer;
            const showCorrect = showResult && val === correctVal;
            const showWrong = showResult && isSel && val !== correctVal;
            return (
              <button key={i} onClick={() => selectOption(val)}
                className={`w-full text-left px-4 py-3 rounded-xl border transition ${
                  showCorrect ? "border-green-500 bg-green-50" :
                  showWrong ? "border-red-500 bg-red-50" :
                  isSel ? "border-brand-500 bg-brand-50" : "border-slate-200 bg-white"
                }`}>
                <span className="text-sm">{opt}</span>
              </button>
            );
          })}

          {q.type === "fill" && (
            <input disabled={!!selected} value={selected ?? ""} onChange={(e) => setSelected(e.target.value)}
              onBlur={() => selected && submitAnswer(selected)}
              placeholder="请输入答案"
              className="w-full px-4 py-3 rounded-xl border border-slate-200 text-sm focus:border-brand-500 outline-none" />
          )}

          {q.type === "short" && (
            <textarea disabled={!!selected} value={selected ?? ""} onChange={(e) => setSelected(e.target.value)} rows={5}
              placeholder="请输入解答…"
              className="w-full px-4 py-3 rounded-xl border border-slate-200 text-sm focus:border-brand-500 outline-none resize-none" />
          )}

          {q.type === "short" && selected && !showResult && (
            <Button className="w-full mt-2" onClick={() => submitAnswer(selected)}>提交答案</Button>
          )}
        </div>

        {/* 作答反馈 */}
        {showResult && q.type !== "short" && correctAns && (
          <div className={`mt-4 p-3 rounded-xl text-sm ${correctAns.correct ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
            <div className="font-medium mb-1">{correctAns.correct ? "✓ 回答正确" : `✗ 正确答案：${correctAns.correctAnswer}`}</div>
          </div>
        )}
        {showResult && correctAns && (
          <div className="mt-2 p-3 rounded-xl bg-slate-50 text-sm text-slate-600 leading-relaxed">
            <div className="font-medium text-slate-700 mb-1">解析</div>
            {correctAns.analysis}
          </div>
        )}
      </div>

      {/* 底部操作 */}
      <footer className="sticky bottom-0 bg-white border-t border-slate-200 px-3 py-2 flex items-center gap-2">
        <Button variant="ghost" className="bg-slate-100 text-slate-500" disabled>上一题</Button>
        <Button variant="outline" className="flex-1" onClick={() => setShowCard(true)}>答题卡</Button>
        {isLast || !pendingNext
          ? <Button className="flex-1" onClick={() => setShowSubmit(true)}>交卷</Button>
          : <Button className="flex-1" disabled={!selected} onClick={next}>下一题</Button>}
      </footer>

      {/* 答题卡 */}
      <Sheet open={showCard} onClose={() => setShowCard(false)} title="答题卡">
        <div className="grid grid-cols-6 gap-2">
          {Array.from({ length: total }, (_, i) => {
            const idx = i + 1;
            const entry = Object.values(answered)[i];
            const done = !!entry;
            const mk = entry?.marked;
            return (
              <div key={i} className={`aspect-square rounded-lg flex items-center justify-center text-sm ${
                mk ? "bg-amber-100 text-amber-600 border border-amber-300" :
                done ? "bg-brand-100 text-brand-600" : "bg-slate-100 text-slate-400"
              }`}>{idx}</div>
            );
          })}
        </div>
        <div className="flex gap-4 mt-3 text-xs text-slate-500">
          <span>● 已答</span><span>○ 未答</span><span>🚩 标记</span>
        </div>
      </Sheet>

      <Confirm open={showSubmit} title="交卷" message={`还有 ${total - Object.keys(answered).length} 题未作答，确定交卷吗？`} onConfirm={submit} onCancel={() => setShowSubmit(false)} />
    </div>
  );
}
