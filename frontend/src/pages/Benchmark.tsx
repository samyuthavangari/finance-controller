import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../services/api";
import { Kpi, PageHeader, Surface, pct } from "../components/ui";

export default function Benchmark() {
  const { data } = useQuery({ queryKey: ["bm"], queryFn: api.benchmark });
  const m = data?.metrics;
  if (!m) return <p className="text-muted">Run a demo first. These numbers come from the evaluation engine, not placeholders.</p>;
  const types = Object.entries(data.by_exception_type || {}).map(([k, v]: any) => ({
    type: k,
    accuracy: Number((v.accuracy * 100).toFixed(1)),
    n: v.n,
  }));
  return (
    <div className="space-y-6">
      <PageHeader kicker="Eval" title="Benchmark" subtitle="Hidden ground truth. Not a slide." />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Dataset" value={`${m.records} records`} />
        <Kpi label="Match accuracy" value={pct(m.match_accuracy)} />
        <Kpi label="Precision" value={pct(m.precision)} />
        <Kpi label="Recall" value={pct(m.recall)} />
        <Kpi label="F1" value={pct(m.f1)} />
        <Kpi label="Auto resolution" value={pct(m.auto_resolution_rate)} />
        <Kpi label="Human review" value={pct(m.human_review_rate)} />
        <Kpi label="Unresolved" value={pct(m.unresolved_rate)} />
        <Kpi label="False positive rate" value={pct(m.false_positive_rate)} />
        <Kpi label="Throughput" value={`${(m.throughput_rps || 0).toFixed(1)} r/s`} />
      </div>
      <Surface className="p-4">
        <h3 className="mb-3 text-sm">Accuracy by exception type</h3>
        <div className="h-72">
          <ResponsiveContainer>
            <BarChart data={types}>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="type" tick={{ fill: "#a1a1aa", fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={70} />
              <YAxis tick={{ fill: "#a1a1aa" }} />
              <Tooltip contentStyle={{ background: "#111113", border: "1px solid rgba(255,255,255,0.08)" }} />
              <Bar dataKey="accuracy" fill="#5eead4" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Surface>
      <Surface className="p-4">
        <h3 className="mb-3 text-sm">Confidence calibration</h3>
        <table className="data-table">
          <thead className="text-muted">
            <tr>
              <th className="text-left">Bucket</th>
              <th>n</th>
              <th>Actual accuracy</th>
            </tr>
          </thead>
          <tbody>
            {(data.calibration || []).map((b: any) => (
              <tr key={b.bucket} className="border-t border-line">
                <td className="py-2">{b.bucket}</td>
                <td className="text-center">{b.n}</td>
                <td className="text-center">{b.accuracy === null ? "—" : pct(b.accuracy)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Surface>
    </div>
  );
}
