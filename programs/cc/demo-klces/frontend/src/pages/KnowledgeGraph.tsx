import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGet } from "../api/hooks";
import { TopNav, Tag, Button, Sheet, Loading, ErrorRetry, Empty } from "../components/ui";
import { masteryColor } from "../lib/mastery";
import { RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer, Radar, Legend } from "recharts";

interface GraphModule {
  id: string; name: string; mastery: number;
  units: { id: string; name: string; knowledgePoints: { id: string; name: string; mastery: number; frequency: number; errorCount: number }[] }[];
}
interface RadarData { user: { dimension: string; value: number }[]; grade: { dimension: string; value: number }[]; }

export default function KnowledgeGraph() {
  const navigate = useNavigate();
  const graph = useGet<GraphModule[]>("/knowledge-graph");
  const radar = useGet<RadarData>("/knowledge-graph/radar");
  const [tab, setTab] = useState(0);
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["m1"]));
  const [selKp, setSelKp] = useState<{ id: string; name: string; mastery: number; errorCount: number } | null>(null);
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number } | null>(null);

  const R1 = 110, R2 = 200, R3 = 280;
  const cx = 200, cy = 200;

  function toggle(id: string) {
    setExpanded((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  const mods = graph.data || [];
  // flatten kps for vulnerability list tab
  const allKp = mods.flatMap((m) => m.units.flatMap((u) => u.knowledgePoints.map((k) => ({ ...k, module: m.name }))));

  return (
    <div>
      <TopNav title="知识画像" right={<button className="text-lg">🔍</button>} />
      {/* 视图切换 */}
      <div className="sticky top-12 bg-slate-50 z-10 flex border-b border-slate-200">
        {["知识图谱", "能力雷达", "漏洞清单"].map((t, i) => (
          <button key={t} onClick={() => setTab(i)} className={`flex-1 py-3 text-sm relative ${tab === i ? "text-brand-600 font-medium" : "text-slate-500"}`}>
            {t}{tab === i && <span className="absolute bottom-0 left-1/4 right-1/4 h-0.5 bg-brand-500 rounded-full" />}
          </button>
        ))}
      </div>

      {graph.loading ? <Loading /> : graph.error ? <ErrorRetry onRetry={graph.refetch} /> : tab === 0 && (
        <div>
          <div className="relative bg-white"
            onPointerDown={(e) => { drag.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }; }}
            onPointerMove={(e) => { if (drag.current) setPan({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y }); }}
            onPointerUp={() => { drag.current = null; }}
            onPointerLeave={() => { drag.current = null; }}
          >
            <svg viewBox="0 0 400 400" className="w-full" style={{ height: "62vh", touchAction: "none" }}>
              <g transform={`translate(${pan.x} ${pan.y}) scale(${scale})`} style={{ transformOrigin: "center" }}>
                {/* center */}
                <circle cx={cx} cy={cy} r={28} fill="#1e54e6" />
                <text x={cx} y={cy + 4} textAnchor="middle" fill="#fff" fontSize={11}>语文</text>
                {mods.map((m, i) => {
                  const a = (i * 2 * Math.PI) / mods.length - Math.PI / 2;
                  const mx = cx + Math.cos(a) * R1, my = cy + Math.sin(a) * R1;
                  const open = expanded.has(m.id);
                  const r = 18 + (m.mastery > 80 ? 4 : 0);
                  return (
                    <g key={m.id}>
                      <line x1={cx} y1={cy} x2={mx} y2={my} stroke="#cbd5e1" strokeWidth={1.5} />
                      <circle cx={mx} cy={my} r={r} fill={masteryColor(m.mastery)} onClick={() => toggle(m.id)} className="cursor-pointer" />
                      <text x={mx} y={my + r + 12} textAnchor="middle" fill="#334155" fontSize={9}>{m.name}</text>
                      {open && m.units.map((u, j) => {
                        const ua = a + (j - (m.units.length - 1) / 2) * 0.35;
                        const ux = cx + Math.cos(ua) * R2, uy = cy + Math.sin(ua) * R2;
                        const uOpen = expanded.has(u.id);
                        return (
                          <g key={u.id}>
                            <line x1={mx} y1={my} x2={ux} y2={uy} stroke="#e2e8f0" strokeWidth={1} />
                            <circle cx={ux} cy={uy} r={12} fill={masteryColor(avg(u))} onClick={() => toggle(u.id)} className="cursor-pointer" />
                            <text x={ux} y={uy + 24} textAnchor="middle" fill="#64748b" fontSize={8}>{u.name.slice(0, 4)}</text>
                            {uOpen && u.knowledgePoints.map((k, k2) => {
                              const ka = ua + (k2 - (u.knowledgePoints.length - 1) / 2) * 0.22;
                              const kx = cx + Math.cos(ka) * R3, ky = cy + Math.sin(ka) * R3;
                              const kr = 4 + k.frequency * 0.6;
                              return (
                                <g key={k.id} className="cursor-pointer" onClick={() => setSelKp({ id: k.id, name: k.name, mastery: k.mastery, errorCount: k.errorCount })}>
                                  <line x1={ux} y1={uy} x2={kx} y2={ky} stroke="#f1f5f9" strokeWidth={1} />
                                  <circle cx={kx} cy={ky} r={kr} fill={masteryColor(k.mastery)} />
                                  <text x={kx} y={ky - kr - 3} textAnchor="middle" fill="#64748b" fontSize={7}>{k.name.slice(0, 5)}</text>
                                </g>
                              );
                            })}
                          </g>
                        );
                      })}
                    </g>
                  );
                })}
              </g>
            </svg>
            {/* 图例 + 控制 */}
            <div className="absolute bottom-2 left-3 flex items-center gap-3 text-xs text-slate-500">
              <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full bg-red-500 inline-block" />&lt;60%</span>
              <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full bg-amber-500 inline-block" />60-80%</span>
              <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full bg-green-500 inline-block" />&gt;80%</span>
            </div>
            <div className="absolute bottom-2 right-3 flex gap-1">
              <button onClick={() => setScale((s) => Math.min(2.5, s + 0.2))} className="w-7 h-7 rounded-full bg-white shadow text-slate-600">+</button>
              <button onClick={() => setScale((s) => Math.max(0.5, s - 0.2))} className="w-7 h-7 rounded-full bg-white shadow text-slate-600">−</button>
              <button onClick={() => { setScale(1); setPan({ x: 0, y: 0 }); }} className="w-7 h-7 rounded-full bg-white shadow text-xs text-slate-600">⟲</button>
            </div>
          </div>
          <p className="text-xs text-slate-400 text-center mt-2">点击节点展开/收起，拖拽平移，按钮缩放</p>
        </div>
      )}

      {tab === 1 && (
        radar.loading ? <Loading /> : (
          <div className="p-4">
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radar.data!.user} outerRadius="70%">
                  <PolarGrid />
                  <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11 }} />
                  <Radar name="我的水平" dataKey="value" stroke="#1e54e6" fill="#1e54e6" fillOpacity={0.4} />
                  <Radar name="年级平均" dataKey={(d: any) => gradeOf(d, radar.data)} stroke="#94a3b8" fill="#94a3b8" fillOpacity={0.2} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )
      )}

      {tab === 2 && (
        <div className="p-3">
          {allKp.length === 0 ? <Empty /> : [...allKp].sort((a, b) => a.mastery - b.mastery).map((k) => (
            <div key={k.id} className="bg-white rounded-xl shadow-sm p-3 mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ background: masteryColor(k.mastery) }} />
                <div>
                  <div className="text-sm font-medium text-slate-800">{k.name}</div>
                  <div className="text-xs text-slate-400">{k.module} · 掌握度 {k.mastery}%</div>
                </div>
              </div>
              <Button size="sm" variant="ghost" onClick={() => navigate(`/study/${k.id}`)}>去学习</Button>
            </div>
          ))}
        </div>
      )}

      {/* 知识点详情浮层 */}
      <Sheet open={!!selKp} onClose={() => setSelKp(null)} title={selKp?.name}>
        {selKp && (
          <div>
            <div className="flex items-center gap-3 mb-3">
              <div className="w-12 h-12 rounded-full flex items-center justify-center text-white font-bold" style={{ background: masteryColor(selKp.mastery) }}>
                {selKp.mastery}%
              </div>
              <div>
                <div className="text-sm text-slate-500">掌握度</div>
                <div className="text-xs text-slate-400">错题 {selKp.errorCount} 题</div>
              </div>
            </div>
            <Button className="w-full" onClick={() => navigate(`/study/${selKp.id}`)}>去学习</Button>
          </div>
        )}
      </Sheet>
    </div>
  );
}

function avg(u: { knowledgePoints: { mastery: number }[] }) {
  const a = u.knowledgePoints;
  return Math.round(a.reduce((s, k) => s + k.mastery, 0) / a.length);
}
function gradeOf(d: any, data: RadarData | undefined) {
  if (!data) return 0;
  const g = data.grade.find((x) => x.dimension === d.dimension);
  return g?.value ?? 0;
}
