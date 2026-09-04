import { useEffect, useState } from "react";
import { get } from "../../api/client";
import { Panel, PanelHeader, Pill, Spinner, Empty, DButton } from "../../components/desktop";

interface GradeOv {
  id: string; name: string; classCount: number; studentCount: number; teacherCount: number;
  classes: { id: string; name: string; studentCount: number }[];
}

export default function GradeDashboard() {
  const [ov, setOv] = useState<{ grades: GradeOv[] } | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { get<{ grades: GradeOv[] }>("/grade/overview").then(setOv); }, []);
  if (!ov) return <Spinner label="加载年级概览…" />;
  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader title="我所辖年级" action={<Pill color="amber">年级管理员</Pill>} />
        {ov.grades.length === 0 ? <Empty text="尚未被分配年级，请联系学校管理员" /> : (
          <div className="grid sm:grid-cols-2 gap-3 p-5">
            {ov.grades.map((g) => (
              <div key={g.id} className="rounded-xl border border-slate-200 p-4">
                <div className="flex items-center justify-between">
                  <div className="font-medium text-slate-800">{g.name}</div>
                  <DButton size="sm" variant="ghost" onClick={() => setOpen(open === g.id ? null : g.id)}>{open === g.id ? "收起" : "展开班级"}</DButton>
                </div>
                <div className="grid grid-cols-3 gap-2 mt-3 text-center text-xs">
                  <Mini label="班级" value={g.classCount} />
                  <Mini label="教师" value={g.teacherCount} />
                  <Mini label="学生" value={g.studentCount} />
                </div>
                {open === g.id && (
                  <div className="mt-3 space-y-1 border-t border-slate-100 pt-2">
                    {g.classes.map((c) => (
                      <div key={c.id} className="flex items-center justify-between text-sm">
                        <span className="text-slate-600">{c.name}</span>
                        <span className="text-xs text-slate-400">{c.studentCount} 人</span>
                      </div>
                    ))}
                    {g.classes.length === 0 && <div className="text-xs text-slate-400">暂无班级</div>}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
function Mini({ label, value }: { label: string; value: number }) {
  return <div className="rounded-lg bg-slate-50 py-2"><div className="text-lg font-bold text-slate-700">{value}</div><div className="text-slate-400">{label}</div></div>;
}
