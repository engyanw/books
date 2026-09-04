import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get } from "../../api/client";
import { Panel, PanelHeader, Pill, Spinner, LinkBtn } from "../../components/desktop";

interface Dash {
  school: { id: string; name: string };
  gradeCount: number; classCount: number; teacherCount: number;
  gradeAdminCount: number; studentCount: number; pendingCount: number;
}

export default function SchoolDashboard() {
  const [d, setD] = useState<Dash | null>(null);
  useEffect(() => { get<Dash>("/school/dashboard").then(setD); }, []);
  if (!d) return <Spinner label="加载学校概览…" />;
  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader title={d.school.name || "本校"} action={<Pill color="brand">学校管理员</Pill>} />
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 p-5">
          <Stat label="年级" value={d.gradeCount} to="/school/structure" />
          <Stat label="班级" value={d.classCount} to="/school/structure" />
          <Stat label="教师" value={d.teacherCount} to="/school/users" />
          <Stat label="年级管理员" value={d.gradeAdminCount} to="/school/users" />
          <Stat label="学生" value={d.studentCount} to="/school/users" />
          <Stat label="待授权" value={d.pendingCount} to="/school/users" highlight={d.pendingCount > 0} />
        </div>
      </Panel>
      <div className="grid md:grid-cols-2 gap-4">
        <Panel>
          <PanelHeader title="快捷操作" />
          <div className="p-5 space-y-2 text-sm">
            <LinkBtn to="/school/users" size="md" variant="outline">用户授权与生命周期</LinkBtn>
            <div className="block"><LinkBtn to="/school/structure" size="md" variant="outline">年级 / 班级结构</LinkBtn></div>
            <div className="block"><LinkBtn to="/school/knowledge" size="md" variant="outline">学校知识图谱（继承系统）</LinkBtn></div>
            <div className="block"><LinkBtn to="/school/questions" size="md" variant="outline">学校题库（继承系统）</LinkBtn></div>
          </div>
        </Panel>
        <Panel>
          <PanelHeader title="继承说明" />
          <div className="p-5 text-xs text-slate-500 space-y-2 leading-relaxed">
            <p>本层知识图谱与题库<b className="text-slate-700">缺省继承系统层</b>（业务管理员维护）。</p>
            <p>学校管理员可<b className="text-slate-700">追加</b>本校特有知识点/题目，或对继承项<b className="text-slate-700">覆盖/隐藏</b>。</p>
            <p>当系统层变化时，可在「自动同步」与「手动同步」间切换；手动模式下点「立即刷新」拉取上游最新。</p>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Stat({ label, value, to, highlight }: { label: string; value: number; to: string; highlight?: boolean }) {
  return (
    <Link to={to} className={`rounded-xl border p-4 hover:border-brand-300 transition ${highlight ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-slate-50"}`}>
      <div className={`text-2xl font-bold ${highlight ? "text-amber-600" : "text-slate-800"}`}>{value}</div>
      <div className="text-xs text-slate-400 mt-0.5">{label}</div>
    </Link>
  );
}
