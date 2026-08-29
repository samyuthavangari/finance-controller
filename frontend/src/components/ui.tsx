import type { ReactNode } from "react";

export function pct(n?: number | null) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

export function inr(s?: string | number | null) {
  if (s === null || s === undefined) return "—";
  const n = typeof s === "number" ? s : Number(s);
  if (Number.isNaN(n)) return String(s);
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);
}

export function PageHeader({
  kicker,
  title,
  subtitle,
  actions,
}: {
  kicker?: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {kicker ? <div className="text-[11px] uppercase tracking-[0.18em] text-muted">{kicker}</div> : null}
        <h2 className="display text-[32px] leading-none mt-1">{title}</h2>
        {subtitle ? <p className="text-sm text-muted mt-2 max-w-2xl leading-relaxed">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex items-center gap-2 shrink-0">{actions}</div> : null}
    </header>
  );
}

export function Surface({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`glass rounded-2xl ${className}`}>{children}</div>;
}

export function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="glass rounded-2xl p-4">
      <div className="text-[11px] uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className="text-[22px] font-medium mt-2 mono tracking-tight">{value}</div>
      {hint ? <div className="text-xs text-muted mt-1">{hint}</div> : null}
    </div>
  );
}

export function DecisionChip({ value }: { value: string }) {
  const tone =
    value === "AUTO_MATCH" || value === "AUTO_RESOLVE"
      ? "text-accent bg-accent/10"
      : value === "HUMAN_REVIEW"
        ? "text-warn bg-warn/10"
        : "text-danger bg-danger/10";
  return <span className={`text-[10px] font-medium px-2 py-1 rounded-full ${tone}`}>{value}</span>;
}

export function PartitionBar({
  parts,
}: {
  parts: { label: string; n: number; className: string }[];
}) {
  const total = parts.reduce((s, p) => s + p.n, 0) || 1;
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full bg-white/[0.06]">
        {parts.map((p) => (
          <div key={p.label} className={p.className} style={{ width: `${(p.n / total) * 100}%` }} />
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        {parts.map((p) => (
          <span key={p.label} className="inline-flex items-center gap-1.5">
            <i className={`inline-block h-1.5 w-1.5 rounded-full ${p.className}`} />
            <span className="mono text-zinc-200">{p.n}</span> {p.label}
          </span>
        ))}
      </div>
    </div>
  );
}
