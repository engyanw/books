import { useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { get } from "../../api/client";
import { Panel, Spinner } from "../../components/desktop";
import ScopeContentManager from "../../components/ScopeContentManager";

interface MyClass { id: string; name: string; gradeName?: string }

export default function ClassContent() {
  const { user } = useAuth();
  const [classes, setClasses] = useState<MyClass[] | null>(null);
  const [sel, setSel] = useState<string>("");
  const [tab, setTab] = useState<"knowledge" | "questions">("knowledge");

  useEffect(() => {
    get<MyClass[]>("/teacher/my-classes").then((cs) => {
      setClasses(cs);
      if (cs.length && !sel) setSel(cs[0].id);
    });
  }, []); // eslint-disable-line

  if (!classes) return <Spinner label="加载班级…" />;
  if (classes.length === 0) return <Panel><div className="p-8 text-center text-sm text-slate-400">尚未被分配班级，请联系学校管理员授权并分配班级</div></Panel>;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm">
        <span className="text-slate-500">班级：</span>
        {classes.map((c) => (
          <button key={c.id} onClick={() => setSel(c.id)}
            className={`px-3 py-1 rounded-lg text-xs font-medium ${sel === c.id ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-500"}`}>{c.name}</button>
        ))}
      </div>
      <div className="flex gap-1 text-xs">
        <button onClick={() => setTab("knowledge")} className={`px-3 py-1 rounded ${tab === "knowledge" ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-500"}`}>知识图谱</button>
        <button onClick={() => setTab("questions")} className={`px-3 py-1 rounded ${tab === "questions" ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-500"}`}>题库</button>
      </div>
      {sel && <ScopeContentManager scope="class" id={sel} mode={tab} />}
    </div>
  );
}
