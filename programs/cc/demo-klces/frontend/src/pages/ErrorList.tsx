import { useNavigate } from "react-router-dom";
import { useGet } from "../api/hooks";
import { TopNav, Card, Tag, Loading, ErrorRetry, Empty } from "../components/ui";
import { masteryColor } from "../lib/mastery";

interface ErrItem { id: string; kpId: string; moduleId: string; difficulty: number; errorType: string; stem: string; date: string; rework: boolean; collected: boolean; }

export default function ErrorList() {
  const navigate = useNavigate();
  const list = useGet<ErrItem[]>("/errors");

  return (
    <div>
      <TopNav title="错题本" back={false} />
      {list.loading ? <Loading /> : list.error ? <ErrorRetry onRetry={list.refetch} /> : list.data!.length === 0 ? <Empty text="暂无错题" /> : (
        <div className="p-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
          {list.data!.map((e) => (
            <button key={e.id} onClick={() => navigate(`/errors/${e.id}`)} className="text-left">
              <Card className="p-3 h-full" flush>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <Tag color="red">{e.errorType}</Tag>
                      <Tag color="slate">难度{e.difficulty}</Tag>
                      {e.rework && <Tag color="amber">待重做</Tag>}
                    </div>
                    <p className="text-sm text-slate-800 line-clamp-2">{e.stem}</p>
                    <div className="text-xs text-slate-400 mt-1">{e.date}</div>
                  </div>
                  <span className="text-slate-300">›</span>
                </div>
              </Card>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
