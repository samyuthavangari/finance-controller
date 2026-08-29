import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api";
import { useRef, useState } from "react";
import { PageHeader, Surface } from "../components/ui";

export default function RunPage() {
  const qc = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const runMut = useMutation({
    mutationFn: api.startRun,
    onSuccess: (d) => {
      setJobId(d.job_id);
      qc.invalidateQueries();
    },
  });
  const demo = useMutation({
    mutationFn: api.demo,
    onSuccess: (d) => {
      setJobId(d.job_id);
      qc.invalidateQueries();
    },
  });
  const { data: metrics } = useQuery({ queryKey: ["metrics"], queryFn: api.metrics });
  const run = metrics?.run;
  const c = run?.counters || {};
  const pct = run?.progress_pct ?? (run?.status === "completed" ? 100 : 0);

  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Close"
        title="Reconciliation"
        subtitle="Deterministic first. Only exceptions reach Gemini."
      />
      <div className="flex flex-wrap items-center gap-3">
        <input ref={input} type="file" className="text-sm text-muted" onChange={(e) => e.target.files?.[0] && api.upload(e.target.files[0])} />
        <button className="btn btn-primary" onClick={() => runMut.mutate()} disabled={runMut.isPending}>
          Close books
        </button>
        <button className="btn btn-ghost" onClick={() => demo.mutate()} disabled={demo.isPending}>
          Run demo
        </button>
      </div>
      {runMut.error ? <p className="text-danger text-sm">{String(runMut.error)}</p> : null}
      {run ? (
        <Surface className="space-y-4 p-5">
          <div className="flex justify-between text-sm">
            <span>
              Processing {run.records_total} records · {run.status}
            </span>
            <span className="mono">{pct}%</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
            <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
          </div>
          <div className="grid grid-cols-2 gap-2 font-mono text-sm md:grid-cols-3">
            <Row k="Exact matches" v={c.exact_matches} />
            <Row k="Normalized" v={c.normalized_matches} />
            <Row k="ML matches" v={c.ml_matches} />
            <Row k="RAG resolved" v={c.rag_resolved} />
            <Row k="Human review" v={c.human_review} />
            <Row k="Unresolved" v={c.unresolved} />
          </div>
          <p className="text-xs text-muted">job {run.job_id} · last job {jobId}</p>
        </Surface>
      ) : (
        <p className="text-muted">No run in progress.</p>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v?: number }) {
  return (
    <div className="flex justify-between rounded-xl bg-white/[0.03] px-3 py-2">
      <span className="text-muted">{k}</span>
      <span>{v ?? 0}</span>
    </div>
  );
}
