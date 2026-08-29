import { useMutation } from "@tanstack/react-query";
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../services/api";
import { PageHeader, Surface } from "../components/ui";
import { useState } from "react";

const SIZES = [100, 500, 1000, 5000, 10000];

export default function Stress() {
  const [points, setPoints] = useState<any[]>([]);
  const mut = useMutation({
    mutationFn: (n: number) => api.stress(n),
    onSuccess: (d, n) => {
      setPoints((p) => [
        ...p.filter((x) => x.records !== n),
        {
          records: n,
          accuracy: Number(((d.metrics?.match_accuracy || 0) * 100).toFixed(2)),
          throughput: Number((d.metrics?.throughput_rps || 0).toFixed(2)),
          llm: d.metrics?.llm_calls || 0,
          rag: d.metrics?.rag_calls || 0,
          latency: d.metrics?.duration_ms || 0,
          memory_kb: d.memory_kb,
        },
      ]);
    },
  });
  return (
    <div className="space-y-4">
      <PageHeader kicker="Load" title="Stress" subtitle="Accuracy, throughput, LLM/RAG as the batch grows. 5k/10k skip heavy investigation." />
      <div className="flex flex-wrap gap-2">
        {SIZES.map((n) => (
          <button key={n} className="btn btn-ghost" disabled={mut.isPending} onClick={() => mut.mutate(n)}>
            {n.toLocaleString()} records
          </button>
        ))}
      </div>
      {mut.isPending ? <p className="text-warn text-sm">Running… this can take a while.</p> : null}
      {mut.isError ? <p className="text-danger text-sm">{String(mut.error)}</p> : null}
      {points.length ? (
        <Surface className="h-72 p-3">
          <ResponsiveContainer>
            <LineChart data={[...points].sort((a, b) => a.records - b.records)}>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="records" tick={{ fill: "#a1a1aa" }} />
              <YAxis tick={{ fill: "#a1a1aa" }} />
              <Tooltip contentStyle={{ background: "#111113", border: "1px solid rgba(255,255,255,0.08)" }} />
              <Line dataKey="accuracy" stroke="#5eead4" />
              <Line dataKey="throughput" stroke="#fbbf24" />
            </LineChart>
          </ResponsiveContainer>
        </Surface>
      ) : null}
      <table className="data-table">
        <thead className="text-muted">
          <tr>
            {["Records", "Accuracy", "Throughput", "Latency ms", "LLM", "RAG", "Memory KB"].map((h) => (
              <th key={h} className="p-2 text-left">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {points.map((p) => (
            <tr key={p.records} className="border-t border-line">
              <td className="p-2">{p.records}</td>
              <td className="p-2">{p.accuracy}%</td>
              <td className="p-2">{p.throughput}</td>
              <td className="p-2">{p.latency}</td>
              <td className="p-2">{p.llm}</td>
              <td className="p-2">{p.rag}</td>
              <td className="p-2">{p.memory_kb ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
