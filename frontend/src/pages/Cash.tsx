import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Line, LineChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../services/api";
import { PageHeader, Surface } from "../components/ui";

function formatInr(v: number): string {
  if (Math.abs(v) >= 1e7) return `₹${(v / 1e7).toFixed(1)}Cr`;
  if (Math.abs(v) >= 1e5) return `₹${(v / 1e5).toFixed(1)}L`;
  if (Math.abs(v) >= 1e3) return `₹${(v / 1e3).toFixed(0)}K`;
  return `₹${v.toFixed(0)}`;
}

export default function Cash() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["cash"], queryFn: api.cash });
  const sim = useMutation({
    mutationFn: api.simulate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cash"] }),
  });
  const s = data?.summary || {};
  const series = (data?.series || []).map((p: any) => ({ ...p, cashN: Number(p.cash) }));
  const hasNegative = series.some((p: any) => p.cashN < 0);
  const accentColor = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#00e5a8";
  return (
    <div className="space-y-6">
      <PageHeader kicker="Position" title="Cash" subtitle="Forecast math is deterministic. The evidence store is not the source of totals." />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {[
          ["Current", s.current_cash ? `₹${Number(s.current_cash).toLocaleString("en-IN")}` : "—"],
          ["7-day", s.forecast_7d ? `₹${Number(s.forecast_7d).toLocaleString("en-IN")}` : "—"],
          ["14-day", s.forecast_14d ? `₹${Number(s.forecast_14d).toLocaleString("en-IN")}` : "—"],
          ["30-day", s.forecast_30d ? `₹${Number(s.forecast_30d).toLocaleString("en-IN")}` : "—"],
          ["Floor", s.minimum_expected_balance ? `₹${Number(s.minimum_expected_balance).toLocaleString("en-IN")}` : "—"],
          ["Floor date", s.minimum_cash_date || "—"],
        ].map(([l, v]) => {
          const isDanger = l === "Floor" && s.minimum_expected_balance && Number(s.minimum_expected_balance) < 0;
          return (
            <Surface key={l} className="p-4">
              <div className="text-[11px] uppercase tracking-[0.14em] text-muted">{l}</div>
              <div className={`mono mt-2 text-lg ${isDanger ? "text-danger" : ""}`}>{v}</div>
            </Surface>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-ghost" onClick={() => sim.mutate({ delay_receivables_days: 7, scenario: "recv_delay_7" })}>
          Receivables +7d
        </button>
        <button className="btn btn-ghost" onClick={() => sim.mutate({ delay_settlement_days: 5, scenario: "aws_delay_5" })}>
          Settlement +5d
        </button>
        <button className="btn btn-ghost" onClick={() => sim.mutate({ expense_increase_pct: 10, scenario: "opex_plus_10" })}>
          Expenses +10%
        </button>
        <button className="btn btn-ghost" onClick={() => sim.mutate({ early_collect: 500000, scenario: "early_5L" })}>
          Collect ₹5L early
        </button>
      </div>
      <Surface className="h-80 p-3">
        <ResponsiveContainer>
          <LineChart data={series}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" />
            <XAxis dataKey="date" tick={{ fill: "#888888", fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
            <YAxis tick={{ fill: "#888888", fontSize: 10 }} tickFormatter={formatInr} width={64} />
            <Tooltip
              contentStyle={{ background: "#111113", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8 }}
              formatter={(v: number) => [formatInr(v), "Cash"]}
            />
            {hasNegative && <ReferenceLine y={0} stroke="var(--danger)" strokeDasharray="4 2" />}
            <Line
              type="monotone"
              dataKey="cashN"
              stroke={hasNegative ? "var(--danger)" : "var(--accent)"}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </Surface>
      {hasNegative && (
        <p className="text-sm text-danger">⚠ Cash position goes negative under this scenario. Human review required before posting.</p>
      )}
    </div>
  );
}
