import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useGet, usePost } from "../api/hooks";
import { TopNav, Card, Tag, Button, Loading, ErrorRetry, Confirm } from "../components/ui";

interface ErrDetail {
  id: string; kpId: string; moduleId: string; difficulty: number; errorType: string;
  stem: string; material?: string; options?: string[];
  myAnswer: string; correctAnswer: string; cause: string; date: string;
  rework?: boolean; collected?: boolean; kpName?: string; moduleName?: string;
}
interface Variant { id: string; type: string; stem: string; options?: string[]; }

export default function ErrorDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const err = useGet<ErrDetail>(`/errors/${id}`);
  const post = usePost();
  const [reworked, setReworked] = useState(false);
  const [collected, setCollected] = useState(false);
  const [variantConfirm, setVariantConfirm] = useState(false);

  if (err.loading) return <><TopNav title="错题详情" /><Loading /></>;
  if (err.error) return <><TopNav title="错题详情" /><ErrorRetry onRetry={err.refetch} /></>;

  const e = err.data!;
  return (
    <div className="min-h-screen flex flex-col">
      <TopNav title="错题详情" right={<button className="text-lg">⋯</button>} />

      <div className="flex-1 overflow-y-auto px-3 py-2 pb-24">
        {/* 原题 */}
        <Card>
          {e.material && <div className="bg-amber-50/60 border-l-4 border-amber-300 rounded p-2 mb-2 text-sm text-slate-700">{e.material}</div>}
          <p className="text-sm text-slate-900 leading-relaxed">{e.stem}</p>
          {e.options && <div className="mt-2 space-y-1">{e.options.map((o, i) => <div key={i} className="text-sm text-slate-600">{o}</div>)}</div>}
          <div className="flex gap-1.5 mt-3 flex-wrap">
            <Tag color="slate">{e.moduleName}</Tag>
            <Tag color="slate">难度{e.difficulty}</Tag>
            <Tag color="red">{e.errorType}</Tag>
          </div>
        </Card>

        {/* 作答对比 */}
        <Card>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-red-50 p-3">
              <div className="text-xs text-red-500 font-medium mb-1">我的答案</div>
              <div className="text-sm text-slate-700 line-through">{e.myAnswer}</div>
            </div>
            <div className="rounded-xl bg-green-50 p-3">
              <div className="text-xs text-green-600 font-medium mb-1">正确答案</div>
              <div className="text-sm text-slate-800 font-medium">{e.correctAnswer}</div>
            </div>
          </div>
        </Card>

        {/* 错误分析 */}
        <Card>
          <h3 className="font-medium text-slate-800 mb-2">错误原因分析</h3>
          <p className="text-sm text-slate-600 leading-relaxed">{e.cause}</p>
          <button onClick={() => navigate(`/study/${e.kpId}`)}
            className="mt-3 inline-flex items-center gap-1 text-brand-600 text-sm">关联知识点：{e.kpName} ›</button>
        </Card>
      </div>

      {/* 底部操作 */}
      <footer className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-md bg-white border-t border-slate-200 px-3 py-2 flex gap-2">
        <Button variant="outline" className="flex-1" disabled={reworked} onClick={async () => { await post(`/errors/${id}/rework`); setReworked(true); }}>
          {reworked || e.rework ? "已加入重做" : "加入重做"}
        </Button>
        <Button variant="outline" className="flex-1" onClick={() => setVariantConfirm(true)}>同类变式题</Button>
        <Button variant="ghost" className="flex-1 bg-red-50 text-red-500" onClick={() => setCollected(!collected)}>
          {collected ? "♥ 已收藏" : "♡ 收藏"}
        </Button>
      </footer>
      <div className="h-14" />

      <Confirm open={variantConfirm} title="同类变式题" message="将推送 3 道同知识点、同类型的变式题，完成后自动判分。是否开始？"
        onConfirm={async () => {
          setVariantConfirm(false);
          const res = await post<{ sessionId: string }>("/assessments/sessions", { type: "a2", unitId: undefined });
          // 用现有 session 流程：跳到答题页（变式题作为专项训练）
          navigate(`/assess/answer/${res.sessionId}`);
        }} onCancel={() => setVariantConfirm(false)} />
    </div>
  );
}
