import { Link } from "react-router-dom";

export function Panel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-white rounded-xl shadow-sm border border-slate-200 ${className}`}>{children}</div>;
}

export function PanelHeader({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
      <h2 className="font-medium text-slate-800">{title}</h2>
      {action}
    </div>
  );
}

export function Pill({ children, color = "slate" }: { children: React.ReactNode; color?: "slate" | "brand" | "green" | "red" | "amber" }) {
  const m: Record<string, string> = {
    slate: "bg-slate-100 text-slate-600",
    brand: "bg-brand-50 text-brand-600",
    green: "bg-green-50 text-green-600",
    red: "bg-red-50 text-red-600",
    amber: "bg-amber-50 text-amber-600",
  };
  return <span className={`px-2 py-0.5 rounded text-xs ${m[color]}`}>{children}</span>;
}

export function DButton({ children, variant = "primary", onClick, disabled, size = "md" }: {
  children: React.ReactNode; variant?: "primary" | "ghost" | "outline" | "danger";
  onClick?: () => void; disabled?: boolean; size?: "sm" | "md";
}) {
  const b = "inline-flex items-center justify-center font-medium rounded-lg transition active:scale-95 disabled:opacity-40";
  const s = { sm: "px-2.5 py-1 text-xs", md: "px-3.5 py-1.5 text-sm" };
  const v = {
    primary: "bg-brand-500 text-white hover:bg-brand-600",
    ghost: "text-slate-600 hover:bg-slate-100",
    outline: "border border-slate-300 text-slate-600 hover:bg-slate-50",
    danger: "bg-red-500 text-white hover:bg-red-600",
  };
  return <button onClick={onClick} disabled={disabled} className={`${b} ${s[size]} ${v[variant]}`}>{children}</button>;
}

export function Spinner({ label = "加载中..." }: { label?: string }) {
  return (
    <div className="py-10 text-center text-slate-400 text-sm flex items-center justify-center gap-2">
      <span className="inline-block w-4 h-4 border-2 border-brand-200 border-t-brand-500 rounded-full animate-spin" />
      {label}
    </div>
  );
}

export function Empty({ text = "暂无数据" }: { text?: string }) {
  return <div className="py-10 text-center text-slate-400 text-sm">{text}</div>;
}

export function LinkBtn({ to, children, variant = "ghost", size = "sm" }: {
  to: string; children: React.ReactNode; variant?: "primary" | "ghost" | "outline"; size?: "sm" | "md";
}) {
  const s = { sm: "px-2.5 py-1 text-xs", md: "px-3.5 py-1.5 text-sm" };
  const v = {
    primary: "bg-brand-500 text-white hover:bg-brand-600",
    ghost: "text-brand-600 hover:bg-brand-50",
    outline: "border border-brand-200 text-brand-600 hover:bg-brand-50",
  };
  return <Link to={to} className={`inline-flex items-center justify-center font-medium rounded-lg transition ${s[size]} ${v[variant]}`}>{children}</Link>;
}

export function masteryColor(m: number) {
  if (m < 60) return "#ef4444";
  if (m < 80) return "#f59e0b";
  return "#22c55e";
}
