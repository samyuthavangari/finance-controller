import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { useState } from "react";
import { api } from "../services/api";

export default function GraphPage() {
  const { txId } = useParams();
  const { data } = useQuery({ queryKey: ["graph", txId], queryFn: () => api.graph(txId!), enabled: !!txId });
  const [sel, setSel] = useState<any>(null);
  if (!data) return <p className="text-muted">Loading graph…</p>;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2 space-y-3 rounded-2xl bg-panel p-6 hairline">
        <h2 className="display text-3xl">Evidence graph</h2>
        <p className="text-xs text-muted">Bank → settlement → invoice → vendor → contract → policy → historical → decision</p>
        {data.nodes.map((n: any) => (
          <button
            key={n.id}
            onClick={() => setSel(n)}
            className="block w-full rounded-xl bg-white/[0.03] px-3 py-2 text-left hover:bg-white/[0.06]"
          >
            <div className="text-[10px] uppercase text-muted">{n.type}</div>
            <div className="mono text-sm">{n.label}</div>
          </button>
        ))}
      </div>
      <div className="rounded-2xl bg-panel p-4 hairline">
        <h3 className="text-sm text-muted mb-2">Node</h3>
        {sel ? (
          <pre className="text-[11px] whitespace-pre-wrap">{JSON.stringify(sel, null, 2)}</pre>
        ) : (
          <p className="text-muted text-sm">Click a node.</p>
        )}
        <h3 className="text-sm text-muted mt-4 mb-2">Edges</h3>
        <ul className="text-xs mono space-y-1">
          {data.edges.map((e: any, i: number) => (
            <li key={i}>
              {e.from} → {e.to}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
