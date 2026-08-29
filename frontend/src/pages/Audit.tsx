import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import { PageHeader, Surface } from "../components/ui";

const EVENT_TONE: Record<string, string> = {
  EXACT_MATCH: "text-accent",
  NORMALIZED_MATCH: "text-accent",
  AUTO_MATCH: "text-accent",
  AUTO_RESOLVE: "text-accent",
  DECISION_VALIDATED: "text-sky-400",
  INVESTIGATION_STARTED: "text-sky-400",
  RETRIEVED_CONTRACT: "text-indigo-400",
  RETRIEVED_POLICY: "text-indigo-400",
  RETRIEVED_HISTORICAL_CASE: "text-indigo-400",
  GATE_REJECTED_HALLUCINATION: "text-danger",
  DUPLICATE_SKIPPED_LLM: "text-warn",
  CALCULATED_VARIANCE: "text-warn",
  HUMAN_REVIEW: "text-warn",
  EXCEPTIONS: "text-warn",
  UNRESOLVED: "text-danger",
  JOB_STARTED: "text-muted",
  INGESTED: "text-muted",
};

function eventTone(event: string): string {
  for (const [key, cls] of Object.entries(EVENT_TONE)) {
    if (event.includes(key)) return cls;
  }
  return "text-muted";
}

function fmtTs(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return ts?.slice(11, 19) || ts;
  }
}

export default function Audit() {
  const { data, isLoading } = useQuery({ queryKey: ["audit"], queryFn: () => api.audit(), refetchInterval: 5000 });
  const [search, setSearch] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const rows: any[] = data || [];
  const filtered = search
    ? rows.filter((r) => (r.event + " " + r.detail).toLowerCase().includes(search.toLowerCase()))
    : rows;

  useEffect(() => {
    if (!search) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [rows.length, search]);

  return (
    <div className="space-y-4">
      <PageHeader
        kicker="Trail"
        title="Audit log"
        subtitle="Every gate decision, in order. No event is hidden."
      />
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter events…"
          className="w-full max-w-xs rounded-lg border border-line bg-transparent px-3 py-2 text-sm text-text placeholder:text-muted"
        />
        <span className="mono text-xs text-muted">{filtered.length} events</span>
      </div>
      <Surface className="max-h-[68vh] overflow-auto">
        {isLoading ? (
          <p className="p-6 text-sm text-muted">Loading audit trail…</p>
        ) : filtered.length === 0 ? (
          <p className="p-6 text-sm text-muted">
            {search ? "No events match that filter." : "No audit events yet. Run demo to populate."}
          </p>
        ) : (
          <table className="w-full font-mono text-xs">
            <thead className="sticky top-0 bg-panel">
              <tr>
                <th className="px-4 py-2 text-left text-[10px] uppercase tracking-widest text-muted">Time</th>
                <th className="px-4 py-2 text-left text-[10px] uppercase tracking-widest text-muted">Event</th>
                <th className="px-4 py-2 text-left text-[10px] uppercase tracking-widest text-muted">Detail</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r: any, i: number) => (
                <tr key={r.id ?? i} className="border-t border-line hover:bg-white/[0.02]">
                  <td className="whitespace-nowrap px-4 py-2 text-muted">{fmtTs(r.ts)}</td>
                  <td className={`whitespace-nowrap px-4 py-2 font-medium ${eventTone(r.event)}`}>{r.event}</td>
                  <td className="px-4 py-2 text-muted">{r.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div ref={bottomRef} />
      </Surface>
    </div>
  );
}
