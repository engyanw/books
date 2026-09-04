// 学校 / 年级 / 班级 结构（多租户层级）
export interface School {
  id: string;
  name: string;
  createdAt: string;
  createdBy: string;     // bizadmin id 或 schooladmin id
  status: "pending" | "active";  // pending：schooladmin 已注册但 bizadmin 尚未授权
  ownerId?: string;      // 所属 schooladmin 的 userId
}

export interface Grade {
  id: string;
  schoolId: string;
  name: string;          // 高一 / 高二 / 高三
}

export interface Class {
  id: string;
  schoolId: string;
  gradeId: string;
  name: string;          // 高二(1)班
}

const schools: School[] = [];
const grades: Grade[] = [];
const classes: Class[] = [];
let schoolSeq = 0, gradeSeq = 0, classSeq = 0;

// ---------- 种子 ----------
export function seedSchools() {
  if (schools.length) return;
  // 一所演示学校，对接现有演示 student/teacher 账号
  const s: School = {
    id: "sch1", name: "示范中学", createdAt: new Date().toISOString(),
    createdBy: "system", status: "active", ownerId: "seed",
  };
  schools.push(s);
  const g1: Grade = { id: "grd1", schoolId: "sch1", name: "高一" };
  const g2: Grade = { id: "grd2", schoolId: "sch1", name: "高二" };
  const g3: Grade = { id: "grd3", schoolId: "sch1", name: "高三" };
  grades.push(g1, g2, g3);
  classes.push(
    { id: "cls1", schoolId: "sch1", gradeId: "grd2", name: "高二(1)班" },
    { id: "cls2", schoolId: "sch1", gradeId: "grd2", name: "高二(2)班" },
  );
  schoolSeq = 1; gradeSeq = 3; classSeq = 2;
}

// ---------- School ----------
export function listSchools() { return [...schools]; }
export function listActiveSchools() { return schools.filter((s) => s.status === "active"); }
export function findSchool(id: string) { return schools.find((s) => s.id === id) || null; }
export function findSchoolByName(name: string) { return schools.find((s) => s.name === name) || null; }
export function saveSchool(s: School) {
  const i = schools.findIndex((x) => x.id === s.id);
  if (i >= 0) schools[i] = s; else schools.push(s);
}
export function nextSchoolId() { return `sch${++schoolSeq}`; }

// ---------- Grade ----------
export function listGrades(schoolId?: string) {
  return schoolId ? grades.filter((g) => g.schoolId === schoolId) : [...grades];
}
export function findGrade(id: string) { return grades.find((g) => g.id === id) || null; }
export function saveGrade(g: Grade) {
  const i = grades.findIndex((x) => x.id === g.id);
  if (i >= 0) grades[i] = g; else grades.push(g);
}
export function deleteGrade(id: string) {
  const i = grades.findIndex((x) => x.id === id);
  if (i >= 0) grades.splice(i, 1);
  // 级联清理班级
  for (let j = classes.length - 1; j >= 0; j--) if (classes[j].gradeId === id) classes.splice(j, 1);
}
export function nextGradeId() { return `grd${++gradeSeq}`; }

// ---------- Class ----------
export function listClasses(schoolId?: string, gradeId?: string) {
  return classes.filter((c) => (!schoolId || c.schoolId === schoolId) && (!gradeId || c.gradeId === gradeId));
}
export function findClass(id: string) { return classes.find((c) => c.id === id) || null; }
export function saveClass(c: Class) {
  const i = classes.findIndex((x) => x.id === c.id);
  if (i >= 0) classes[i] = c; else classes.push(c);
}
export function deleteClass(id: string) {
  const i = classes.findIndex((x) => x.id === id);
  if (i >= 0) classes.splice(i, 1);
}
export function nextClassId() { return `cls${++classSeq}`; }
