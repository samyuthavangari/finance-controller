import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../services/api";
import { PageHeader, Surface } from "../components/ui";

export default function Cash() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["cash"], queryFn: api.cash });
  const sim = useMutation({
    mutationFn: api.simulate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cash"] }),
  });
  const s = data?.summary || {};
  const series = (data?.series || []).map((p: any) => ({ ...p, cashN: Number(p.cash) }));
  return (
    <div className="space-y-6">
      <PageHeader kicker="Position" title="Cash" subtitle="Forecast math is deterministic. Qdrant is not the source of totals." />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {[
          ["Current", s.current_cash ? `₹${s.current_cash}` : "—"],
          ["7-day", s.forecast_7d ? `₹${s.forecast_7d}` : "—"],
          ["14-day", s.forecast_14d ? `₹${s.forecast_14d}` : "—"],
          ["30-day", s.forecast_30d ? `₹${s.forecast_30d}` : "—"],
          ["Floor", s.minimum_expected_balance ? `₹${s.minimum_expected_balance}` : "—"],
          ["Floor date", s.minimum_cash_date || "—"],
        ].map(([l, v]) => (
          <Surface key={l} className="p-4">
            <div className="text-[11px] uppercase tracking-[0.14em] text-muted">{l}</div>
            <div className="mono mt-2 text-lg">{v}</div>
          </Surface>
        ))}
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
            <XAxis dataKey="date" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
            <YAxis tick={{ fill: "#a1a1aa", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#111113", border: "1px solid rgba(255,255,255,0.08)" }} />
            <Line type="monotone" dataKey="cashN" stroke="#5eead4" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </Surface>
    </div>
  );
}
