import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { useState } from "react";
import { api } from "../services/api";
import { Surface } from "../components/ui";

const NODE_STYLES: Record<string, { bg: string; border: string; label: string }> = {
  transaction: { bg: "bg-accent/10", border: "border-accent/30", label: "text-accent" },
  invoice:     { bg: "bg-sky-400/10", border: "border-sky-400/30", label: "text-sky-400" },
  vendor:      { bg: "bg-indigo-400/10", border: "border-indigo-400/30", label: "text-indigo-400" },
  contract:    { bg: "bg-amber-400/10", border: "border-amber-400/30", label: "text-amber-400" },
  policy:      { bg: "bg-purple-400/10", border: "border-purple-400/30", label: "text-purple-400" },
  settlement:  { bg: "bg-teal-400/10", border: "border-teal-400/30", label: "text-teal-400" },
  decision:    { bg: "bg-emerald-400/10", border: "border-emerald-400/30", label: "text-emerald-400" },
  historical_case: { bg: "bg-rose-400/10", border: "border-rose-400/30", label: "text-rose-400" },
};

function nodeStyle(type: string) {
  return NODE_STYLES[type] ?? { bg: "bg-white/[0.04]", border: "border-white/10", label: "text-muted" };
}

export default function GraphPage() {
  const { txId } = useParams();
  const { data, isLoading } = useQuery({ queryKey: ["graph", txId], queryFn: () => api.graph(txId!), enabled: !!txId });
  const [sel, setSel] = useState<any>(null);

  if (isLoading) return <p className="p-6 text-sm text-muted">Loading evidence graph for {txId}…</p>;
  if (!data) return <p className="p-6 text-sm text-muted">No graph data. Run demo first.</p>;

  const nodes: any[] = data.nodes || [];
  const edges: any[] = data.edges || [];

  return (
    <div className="space-y-4">
      <div>
        <div className="text-[11px] uppercase tracking-[0.2em] text-muted">Evidence chain</div>
        <h2 className="display mt-1 text-3xl">{txId}</h2>
        <p className="mt-1 text-xs text-muted">
          {nodes.length} nodes · {edges.length} edges · Click a node to inspect
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Node graph */}
        <div className="lg:col-span-2">
          <Surface className="p-5">
            <div className="flex flex-wrap gap-3">
              {nodes.map((n: any, i: number) => {
                const s = nodeStyle(n.type);
                const outEdges = edges.filter((e: any) => e.from === n.id);
                return (
                  <div key={n.id} className="flex items-center gap-2">
                    <button
                      onClick={() => setSel(sel?.id === n.id ? null : n)}
                      className={`rounded-xl border px-4 py-3 text-left transition-all ${s.bg} ${s.border} ${sel?.id === n.id ? "ring-1 ring-white/20" : ""} hover:brightness-110`}
                    >
                      <div className={`text-[9px] uppercase tracking-widest ${s.label}`}>{n.type}</div>
                      <div className="mono mt-0.5 text-xs text-text">{n.label}</div>
                    </button>
                    {outEdges.length > 0 && (
                      <span className="text-base text-muted" aria-hidden="true">→</span>
                    )}
                  </div>
                );
              })}
            </div>
            {nodes.length === 0 && (
              <p className="text-sm text-muted">No nodes in this graph.</p>
            )}
          </Surface>

          {/* Edge list */}
          {edges.length > 0 && (
            <Surface className="mt-3 overflow-hidden">
              <div className="px-4 pt-3 text-[10px] uppercase tracking-widest text-muted">Edges</div>
              <table className="w-full font-mono text-xs">
                <tbody>
                  {edges.map((e: any, i: number) => (
                    <tr key={i} className="border-t border-line">
                      <td className="px-4 py-2 text-text">{e.from}</td>
                      <td className="px-4 py-2 text-muted">→</td>
                      <td className="px-4 py-2 text-text">{e.to}</td>
                      {e.label && <td className="px-4 py-2 text-muted">{e.label}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </Surface>
          )}
        </div>

        {/* Detail panel */}
        <Surface className="p-4">
          {sel ? (
            <>
              <div className={`text-[10px] uppercase tracking-widest ${nodeStyle(sel.type).label}`}>{sel.type}</div>
              <div className="mono mt-1 text-sm font-medium text-text">{sel.label}</div>
              <div className="mt-4 space-y-2">
                {Object.entries(sel).filter(([k]) => !["id", "type", "label"].includes(k)).map(([k, v]) => (
                  <div key={k} className="grid grid-cols-2 gap-2 text-xs">
                    <span className="text-muted">{k}</span>
                    <span className="mono break-all text-text">{String(v)}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-muted">Click a node to inspect its metadata.</p>
          )}
        </Surface>
      </div>
    </div>
  );
}
