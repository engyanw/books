import { Link, useLocation, useNavigate } from "react-router-dom";

const tabs = [
  { to: "/", label: "首页", icon: "🏠" },
  { to: "/assess", label: "测评", icon: "📝" },
  { to: "/plan", label: "学习", icon: "📚" },
  { to: "/errors", label: "错题", icon: "❌" },
  { to: "/growth", label: "我的", icon: "👤" },
];

export default function BottomTab() {
  const { pathname } = useLocation();
  return (
    <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-md sm:max-w-2xl lg:max-w-3xl bg-white border-t border-slate-200 flex z-30"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
      {tabs.map((t) => {
        const active = pathname === t.to || (t.to !== "/" && pathname.startsWith(t.to));
        return (
          <Link key={t.to} to={t.to} className={`flex-1 flex flex-col items-center py-2 text-xs ${active ? "text-brand-600" : "text-slate-400"}`}>
            <span className="text-lg leading-none">{t.icon}</span>
            <span className="mt-0.5">{t.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export function useNav() { return useNavigate(); }

interface TopNavProps {
  title: string;
  back?: boolean;
  right?: React.ReactNode;
}
export function TopNav({ title, back = true, right }: TopNavProps) {
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-20 bg-white/95 backdrop-blur border-b border-slate-200 h-12 flex items-center px-3">
      <div className="w-10 flex items-center">
        {back && (
          <button onClick={() => navigate(-1)} className="text-2xl text-slate-700 leading-none">‹</button>
        )}
      </div>
      <h1 className="flex-1 text-center font-medium text-slate-900 truncate">{title}</h1>
      <div className="w-10 flex justify-end text-slate-600">{right}</div>
    </header>
  );
}

export function Card({ children, className = "", flush = false }: { children: React.ReactNode; className?: string; flush?: boolean }) {
  return <div className={`bg-white rounded-2xl shadow-sm ${flush ? "" : "mx-3 my-2"} p-4 ${className}`}>{children}</div>;
}

export function Tag({ children, color = "brand" }: { children: React.ReactNode; color?: "brand" | "red" | "amber" | "green" | "slate" }) {
  const map: Record<string, string> = {
    brand: "bg-brand-50 text-brand-600",
    red: "bg-red-50 text-red-600",
    amber: "bg-amber-50 text-amber-600",
    green: "bg-green-50 text-green-600",
    slate: "bg-slate-100 text-slate-600",
  };
  return <span className={`px-2 py-0.5 rounded text-xs ${map[color]}`}>{children}</span>;
}

export function ProgressBar({ value, className = "" }: { value: number; className?: string }) {
  return (
    <div className={`h-2 rounded-full bg-slate-100 overflow-hidden ${className}`}>
      <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${Math.min(100, value)}%` }} />
    </div>
  );
}

export function Button({ children, variant = "primary", className = "", onClick, disabled, size = "md" }: {
  children: React.ReactNode; variant?: "primary" | "ghost" | "outline" | "danger";
  className?: string; onClick?: () => void; disabled?: boolean; size?: "sm" | "md" | "lg";
}) {
  const base = "inline-flex items-center justify-center font-medium rounded-xl transition active:scale-95 disabled:opacity-40";
  const sizes = { sm: "px-3 py-1.5 text-sm", md: "px-4 py-2 text-sm", lg: "px-5 py-2.5 text-base" };
  const variants = {
    primary: "bg-brand-500 text-white shadow-sm",
    ghost: "text-brand-600",
    outline: "border border-brand-200 text-brand-600 bg-brand-50",
    danger: "bg-red-500 text-white",
  };
  return (
    <button onClick={onClick} disabled={disabled} className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}>
      {children}
    </button>
  );
}

/** Bottom sheet / modal */
export function Sheet({ open, onClose, children, title }: { open: boolean; onClose: () => void; children: React.ReactNode; title?: string }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center">
      <div className="absolute inset-0 bg-black/40 animate-fade" onClick={onClose} />
      <div className="relative w-full max-w-md bg-white rounded-t-2xl max-h-[80vh] overflow-y-auto animate-sheet">
        <div className="sticky top-0 bg-white border-b border-slate-100 px-4 py-3 flex items-center justify-between">
          <span className="font-medium">{title}</span>
          <button onClick={onClose} className="text-slate-400 text-xl leading-none">×</button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

export function Confirm({ open, title, message, onConfirm, onCancel }: {
  open: boolean; title?: string; message: string; onConfirm: () => void; onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-8">
      <div className="absolute inset-0 bg-black/40 animate-fade" onClick={onCancel} />
      <div className="relative bg-white rounded-2xl w-full max-w-xs p-5 animate-fade">
        <h3 className="font-medium text-slate-900 mb-2">{title || "提示"}</h3>
        <p className="text-sm text-slate-500 mb-4">{message}</p>
        <div className="flex gap-3">
          <Button variant="ghost" className="flex-1 bg-slate-100 text-slate-600" onClick={onCancel}>取消</Button>
          <Button className="flex-1" onClick={onConfirm}>确定</Button>
        </div>
      </div>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse bg-slate-200 rounded ${className}`} />;
}

export function Empty({ text = "暂无数据" }: { text?: string }) {
  return <div className="py-12 text-center text-slate-400 text-sm">{text}</div>;
}

export function ErrorRetry({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="py-12 text-center">
      <p className="text-slate-400 text-sm mb-3">加载失败</p>
      <Button size="sm" variant="outline" onClick={onRetry}>重试</Button>
    </div>
  );
}

export function Loading({ text = "加载中..." }: { text?: string }) {
  return (
    <div className="py-16 text-center text-slate-400 text-sm">
      <div className="inline-block w-6 h-6 border-2 border-brand-200 border-t-brand-500 rounded-full animate-spin mb-2" />
      <p>{text}</p>
    </div>
  );
}
