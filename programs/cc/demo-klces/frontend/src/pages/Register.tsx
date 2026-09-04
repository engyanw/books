import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { get } from "../api/client";

type RegRole = "student" | "teacher" | "schooladmin" | "gradeadmin";
interface SchoolOpt { id: string; name: string; }
interface GradeOpt { id: string; name: string; }
interface ClassOpt { id: string; name: string; }

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [role, setRole] = useState<RegRole>("student");
  const [f, setF] = useState({
    username: "", password: "", confirm: "", name: "", idNumber: "",
    schoolName: "", schoolId: "", gradeId: "", classId: "", studentNo: "",
    email: "", phone: "",
  });
  const [schools, setSchools] = useState<SchoolOpt[]>([]);
  const [grades, setGrades] = useState<GradeOpt[]>([]);
  const [classes, setClasses] = useState<ClassOpt[]>([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  // 拉取学校列表（gradeadmin/teacher/student 选择用）
  useEffect(() => { get<SchoolOpt[]>("/schools").then(setSchools).catch(() => {}); }, []);
  // 选校后拉年级
  useEffect(() => {
    setGrades([]); setClasses([]); setF((p) => ({ ...p, gradeId: "", classId: "" }));
    if (f.schoolId) get<GradeOpt[]>(`/schools/${f.schoolId}/grades`).then(setGrades).catch(() => {});
  }, [f.schoolId]);
  // 选年级后拉班级
  useEffect(() => {
    setClasses([]); setF((p) => ({ ...p, classId: "" }));
    if (f.schoolId && f.gradeId) get<ClassOpt[]>(`/schools/${f.schoolId}/grades/${f.gradeId}/classes`).then(setClasses).catch(() => {});
  }, [f.schoolId, f.gradeId]);

  function set(k: string, v: string) { setF({ ...f, [k]: v }); }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (f.password !== f.confirm) { setErr("两次密码不一致"); return; }
    if (f.password.length < 6) { setErr("密码至少 6 位"); return; }
    if (!f.username.trim() || !f.name.trim()) { setErr("用户名与姓名必填"); return; }
    if (!f.idNumber.trim()) { setErr("请填写身份证号"); return; }
    if (role === "schooladmin" && !f.schoolName.trim()) { setErr("请填写学校名称"); return; }
    if ((role === "gradeadmin" || role === "teacher" || role === "student") && !f.schoolId) { setErr("请选择学校"); return; }
    if (role === "student" && !f.classId) { setErr("请选择班级"); return; }
    setBusy(true);
    try {
      await register({
        username: f.username.trim(), password: f.password, name: f.name.trim(), role,
        schoolName: role === "schooladmin" ? f.schoolName.trim() : undefined,
        schoolId: role !== "schooladmin" ? f.schoolId : undefined,
        classId: role === "student" ? f.classId : undefined,
        studentNo: role === "student" ? f.studentNo.trim() : undefined,
        idNumber: f.idNumber.trim(),
        email: f.email || undefined, phone: f.phone || undefined,
      });
      setDone(true);
    } catch (e: any) {
      setErr(e?.response?.data?.error || e?.response?.data?.message || "注册失败，用户名可能已存在");
    } finally { setBusy(false); }
  }

  if (done) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-brand-50 to-slate-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-sm p-6 max-w-sm text-center">
          <div className="text-4xl mb-3">✅</div>
          <h2 className="text-lg font-bold text-slate-900">注册成功</h2>
          <p className="text-sm text-slate-500 mt-2">
            您的账号已提交，状态为<b className="text-amber-600">待授权</b>。
            {role === "schooladmin" ? "需业务管理员授权后方可登录。" : "需学校管理员授权并分配范围后方可登录。"}
          </p>
          <button onClick={() => nav("/login", { replace: true })}
            className="mt-5 w-full py-2.5 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600">
            返回登录
          </button>
        </div>
      </div>
    );
  }

  const roleOpts: [RegRole, string][] = [
    ["student", "学生"], ["teacher", "教师"], ["schooladmin", "学校管理员"], ["gradeadmin", "年级管理员"],
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-4">
          <h1 className="text-xl font-bold text-slate-900">注册账号</h1>
          <p className="text-xs text-slate-500 mt-1">注册后需对应管理员授权方可登录</p>
        </div>

        <form onSubmit={submit} className="bg-white rounded-2xl shadow-sm p-5 space-y-3">
          <div className="grid grid-cols-2 gap-2">
            {roleOpts.map(([r, label]) => (
              <button type="button" key={r} onClick={() => setRole(r)}
                className={`py-2 rounded-lg text-xs font-medium ${role === r ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-500"}`}>
                {label}
              </button>
            ))}
          </div>
          <Field label="用户名" value={f.username} onChange={(v) => set("username", v)} placeholder="登录用用户名" />
          <Field label="真实姓名" value={f.name} onChange={(v) => set("name", v)} placeholder="真实姓名" />
          <Field label="身份证号" value={f.idNumber} onChange={(v) => set("idNumber", v)} placeholder="身份证号" />

          {role === "schooladmin" && (
            <Field label="学校名称（新建）" value={f.schoolName} onChange={(v) => set("schoolName", v)} placeholder="如 示范中学" />
          )}

          {role !== "schooladmin" && (
            <div>
              <label className="text-xs text-slate-500">所属学校（选择）</label>
              <select value={f.schoolId} onChange={(e) => set("schoolId", e.target.value)}
                className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-brand-500 outline-none bg-white">
                <option value="">请选择学校</option>
                {schools.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          )}

          {role === "student" && (
            <>
              <div>
                <label className="text-xs text-slate-500">年级（选择）</label>
                <select value={f.gradeId} onChange={(e) => set("gradeId", e.target.value)} disabled={!f.schoolId}
                  className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-brand-500 outline-none bg-white disabled:bg-slate-50">
                  <option value="">请选择年级</option>
                  {grades.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-500">班级（选择）</label>
                <select value={f.classId} onChange={(e) => set("classId", e.target.value)} disabled={!f.gradeId}
                  className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-brand-500 outline-none bg-white disabled:bg-slate-50">
                  <option value="">请选择班级</option>
                  {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <Field label="学号" value={f.studentNo} onChange={(v) => set("studentNo", v)} placeholder="学号" />
            </>
          )}

          <Field label="密码（≥6位）" type="password" value={f.password} onChange={(v) => set("password", v)} placeholder="设置密码" />
          <Field label="确认密码" type="password" value={f.confirm} onChange={(v) => set("confirm", v)} placeholder="再次输入" />
          <div className="grid grid-cols-2 gap-2">
            <Field label="邮箱（选填）" value={f.email} onChange={(v) => set("email", v)} placeholder="email" />
            <Field label="手机（选填）" value={f.phone} onChange={(v) => set("phone", v)} placeholder="手机号" />
          </div>
          {err && <div className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{err}</div>}
          <button type="submit" disabled={busy}
            className="w-full py-2.5 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 disabled:opacity-50">
            {busy ? "提交中…" : "提交注册"}
          </button>
          <div className="text-center text-xs text-slate-400">
            已有账号？<Link to="/login" className="text-brand-600 hover:underline">去登录</Link>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type = "text", placeholder }: { label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string }) {
  return (
    <div>
      <label className="text-xs text-slate-500">{label}</label>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-brand-500 outline-none" />
    </div>
  );
}
