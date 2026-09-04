// 继承式知识图谱 / 题库：system → school → grade → class 四层
import type { KnowledgePoint, Question } from "./data.js";
import { modules, questions } from "./data.js";

export type ScopeLayer = "school" | "grade" | "class";

export interface ScopeContent {
  scope: ScopeLayer;
  scopeId: string;
  extraKps: KnowledgePoint[];          // 本层新增知识点
  extraQuestions: Question[];         // 本层新增题目
  kpOverrides: Record<string, Partial<KnowledgePoint>>;  // 覆盖继承项属性
  qOverrides: Record<string, Partial<Question>>;
  hiddenKpIds: string[];               // 本层隐藏的继承项
  hiddenQIds: string[];
  syncMode: "auto" | "manual";
  lastSyncAt?: string;
  manualBase?: { kps: KnowledgePoint[]; questions: Question[] }; // manual 模式冻结快照
}

const store = new Map<string, ScopeContent>();   // key: "school:sch1" / "grade:grd2" / "class:cls1"

export function scopeKey(scope: ScopeLayer, id: string) { return `${scope}:${id}`; }
export function getScope(scope: ScopeLayer, id: string): ScopeContent {
  const k = scopeKey(scope, id);
  if (!store.has(k)) {
    store.set(k, {
      scope, scopeId: id,
      extraKps: [], extraQuestions: [],
      kpOverrides: {}, qOverrides: {},
      hiddenKpIds: [], hiddenQIds: [],
      syncMode: "auto",
    });
  }
  return store.get(k)!;
}

// ---------- 系统（根）有效集 ----------
function systemKps(): KnowledgePoint[] {
  const out: KnowledgePoint[] = [];
  for (const m of modules) for (const u of m.units) for (const k of u.knowledgePoints) out.push({ ...k });
  return out;
}
function systemQuestions(): Question[] {
  return questions.map((q) => ({ ...q }));
}

// ---------- 继承链 ----------
// chain: 从根到本层（不含 system），例如学校层 ["school:sch1"]；
//        年级层 ["school:sch1","grade:grd2"]；班级层 ["school:sch1","grade:grd2","class:cls1"]。
// 空数组 = system 层。
type Chain = string[];

function layerOf(key: string): ScopeLayer {
  return key.split(":")[0] as ScopeLayer;
}
function idOf(key: string): string {
  return key.split(":")[1];
}

// 折叠计算有效集：从 system 起，逐层应用 overrides/hidden/extras
export function effectiveKps(chain: Chain): KnowledgePoint[] {
  let base = systemKps();
  for (const key of chain) {
    const me = getScope(layerOf(key), idOf(key));
    // manual 模式：用冻结快照替换 base（仅当存在快照）
    if (me.syncMode === "manual" && me.manualBase) {
      base = me.manualBase.kps.map((k) => ({ ...k }));
    }
    base = base.map((k) => (me.kpOverrides[k.id] ? { ...k, ...me.kpOverrides[k.id] } : k));
    base = base.filter((k) => !me.hiddenKpIds.includes(k.id));
    base = [...base, ...me.extraKps.map((k) => ({ ...k }))];
  }
  return base;
}

export function effectiveQuestions(chain: Chain): Question[] {
  let base = systemQuestions();
  for (const key of chain) {
    const me = getScope(layerOf(key), idOf(key));
    if (me.syncMode === "manual" && me.manualBase) {
      base = me.manualBase.questions.map((q) => ({ ...q }));
    }
    base = base.map((q) => (me.qOverrides[q.id] ? { ...q, ...me.qOverrides[q.id] } : q));
    base = base.filter((q) => !me.hiddenQIds.includes(q.id));
    base = [...base, ...me.extraQuestions.map((q) => ({ ...q }))];
  }
  return base;
}

// ---------- 同步刷新（manual 模式冻结当前上游有效集为快照） ----------
export function refreshManual(scope: ScopeLayer, id: string, parentChain: Chain) {
  const me = getScope(scope, id);
  me.manualBase = {
    kps: effectiveKps(parentChain).map((k) => ({ ...k })),
    questions: effectiveQuestions(parentChain).map((q) => ({ ...q })),
  };
  me.lastSyncAt = new Date().toISOString();
}

// ---------- 来源标注（UI 用） ----------
export type LayerName = "system" | "school" | "grade" | "class";
export function kpOrigin(kpId: string, chain: Chain): LayerName {
  for (const key of chain) {
    if (getScope(layerOf(key), idOf(key)).extraKps.some((k) => k.id === kpId)) return layerOf(key);
  }
  return "system";
}
export function qOrigin(qId: string, chain: Chain): LayerName {
  for (const key of chain) {
    if (getScope(layerOf(key), idOf(key)).extraQuestions.some((q) => q.id === qId)) return layerOf(key);
  }
  return "system";
}

// ---------- 层级 CRUD（在指定 scope 层操作本层 extras/overrides/hidden） ----------
// 新增知识点（本层）：合成 id 加前缀避免与上游冲突
let extraKpSeq = 0, extraQSeq = 0;
export function addExtraKp(scope: ScopeLayer, id: string, kp: Omit<KnowledgePoint, "id">): KnowledgePoint {
  const me = getScope(scope, id);
  const newId = `${scope[0]}${id}_k${++extraKpSeq}`;  // 形如 ssch1_k1
  const full: KnowledgePoint = { ...kp, id: newId };
  me.extraKps.push(full);
  return full;
}
export function addExtraQuestion(scope: ScopeLayer, id: string, q: Omit<Question, "id">): Question {
  const me = getScope(scope, id);
  const newId = `${scope[0]}${id}_q${++extraQSeq}`;
  const full: Question = { ...q, id: newId };
  me.extraQuestions.push(full);
  return full;
}
export function patchExtraKp(scope: ScopeLayer, id: string, kpId: string, patch: Partial<KnowledgePoint>) {
  const me = getScope(scope, id);
  const ex = me.extraKps.find((k) => k.id === kpId);
  if (ex) { Object.assign(ex, patch); return ex; }
  // 否则视为对继承项的覆盖
  me.kpOverrides[kpId] = { ...(me.kpOverrides[kpId] || {}), ...patch };
  return { id: kpId, ...patch } as KnowledgePoint;
}
export function patchExtraQuestion(scope: ScopeLayer, id: string, qId: string, patch: Partial<Question>) {
  const me = getScope(scope, id);
  const ex = me.extraQuestions.find((q) => q.id === qId);
  if (ex) { Object.assign(ex, patch); return ex; }
  me.qOverrides[qId] = { ...(me.qOverrides[qId] || {}), ...patch };
  return { id: qId, ...patch } as Question;
}
export function removeKp(scope: ScopeLayer, id: string, kpId: string) {
  const me = getScope(scope, id);
  // 若是本层 extras，直接删除
  const i = me.extraKps.findIndex((k) => k.id === kpId);
  if (i >= 0) { me.extraKps.splice(i, 1); return; }
  // 否则标记隐藏继承项
  if (!me.hiddenKpIds.includes(kpId)) me.hiddenKpIds.push(kpId);
  // 撤销可能的覆盖
  delete me.kpOverrides[kpId];
}
export function removeQuestion(scope: ScopeLayer, id: string, qId: string) {
  const me = getScope(scope, id);
  const i = me.extraQuestions.findIndex((q) => q.id === qId);
  if (i >= 0) { me.extraQuestions.splice(i, 1); return; }
  if (!me.hiddenQIds.includes(qId)) me.hiddenQIds.push(qId);
  delete me.qOverrides[qId];
}
export function restoreKp(scope: ScopeLayer, id: string, kpId: string) {
  const me = getScope(scope, id);
  me.hiddenKpIds = me.hiddenKpIds.filter((x) => x !== kpId);
}
export function restoreQuestion(scope: ScopeLayer, id: string, qId: string) {
  const me = getScope(scope, id);
  me.hiddenQIds = me.hiddenQIds.filter((x) => x !== qId);
}
