import { useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { get } from "../../api/client";
import { Panel, Spinner } from "../../components/desktop";
import ScopeContentManager from "../../components/ScopeContentManager";

interface GradeOv { id: string; name: string; classCount: number }

export default function GradeQuestions() {
  const { user } = useAuth();
  const [grades, setGrades] = useState<GradeOv[] | null>(null);
  const [sel, setSel] = useState<string>("");

  useEffect(() => {
    get<{ grades: GradeOv[] }>("/grade/overview").then((r) => {
      setGrades(r.grades);
      if (r.grades.length && !sel) setSel(r.grades[0].id);
    });
  }, []); // eslint-disable-line

  if (!grades) return <Spinner label="加载年级…" />;
  if (grades.length === 0) return <Panel><div className="p-8 text-center text-sm text-slate-400">尚未被分配年级，请联系学校管理员授权并分配年级</div></Panel>;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm">
        <span className="text-slate-500">年级：</span>
        {grades.map((g) => (
          <button key={g.id} onClick={() => setSel(g.id)}
            className={`px-3 py-1 rounded-lg text-xs font-medium ${sel === g.id ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-500"}`}>{g.name}</button>
        ))}
      </div>
      {sel && <ScopeContentManager scope="grade" id={sel} mode="questions" />}
    </div>
  );
}
