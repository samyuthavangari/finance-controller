import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { DecisionChip, PageHeader, PartitionBar, Surface, inr, pct } from "../components/ui";

export default function Dashboard() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["metrics"], queryFn: api.metrics });
  const { data: exceptions } = useQuery({ queryKey: ["exceptions"], queryFn: api.exceptions });
  const demo = useMutation({
    mutationFn: api.demo,
    onSuccess: async () => {
      await qc.invalidateQueries();
      await qc.refetchQueries({ queryKey: ["metrics"] });
    },
  });

  const m = data?.benchmark;
  const counters = data?.run?.counters || {};
  const cash = data?.cash;
  const cost = data?.cost || {};
  const rows = (exceptions || []).slice(0, 6);

  const exact =
    Number(counters.exact_matches || 0) +
    Number(counters.normalized_matches || 0) +
    Number(counters.fuzzy_matches || 0) +
    Number(counters.ml_matches || 0);
  const rag = Number(counters.rag_resolved || 0);
  const review = Number(counters.human_review || 0);
  const open = Number(counters.unresolved || 0);

  return (
    <div className="space-y-8">
      <PageHeader
        kicker="Control system"
        title="Books"
        subtitle="One number that matters: how much of the close we could prove. The rest stays an exception."
        actions={
          <button className="btn btn-primary" disabled={demo.isPending} onClick={() => demo.mutate()}>
            {demo.isPending ? "Closing…" : "Run demo"}
          </button>
        }
      />

      {demo.isError ? <p className="text-sm text-danger">{String(demo.error)}</p> : null}
      {error ? <p className="text-sm text-danger">Backend unreachable on :8000.</p> : null}

      {isLoading ? (
        <Surface className="p-10 text-center text-sm text-muted">Loading last close…</Surface>
      ) : !m && !data?.run ? (
        <Surface className="p-10 text-center">
          <p className="display text-3xl">No close yet.</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            Run the 200-record synthetic batch. Match rate, exceptions, and cash all come from the API — nothing is
            painted on.
          </p>
        </Surface>
      ) : !m && data?.run ? (
        <p className="text-sm text-muted">Run {data.run.status}. Benchmark is empty — run demo again.</p>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-[1.4fr_0.8fr]">
            <Surface className="p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.16em] text-muted">F1 vs hidden GT</div>
                  <div className="display mt-1 text-[64px] leading-none">{pct(m.f1)}</div>
                  <div className="mt-2 text-sm text-muted">
                    Match {pct(m.match_accuracy)} · auto {pct(m.auto_resolution_rate)} · refused {pct(m.unresolved_rate)}
                  </div>
                </div>
                <div className="text-right text-xs text-muted">
                  <div className="mono text-zinc-200">{m.records ?? 0} records</div>
                  <div className="mt-1">{(m.throughput_rps || 0).toFixed(1)} r/s</div>
                </div>
              </div>
              <div className="mt-8">
                <PartitionBar
                  parts={[
                    { label: "exact / alias", n: exact, className: "bg-accent" },
                    { label: "gate resolve", n: rag, className: "bg-indigo-400" },
                    { label: "review", n: review, className: "bg-warn" },
                    { label: "unresolved", n: open, className: "bg-danger" },
                  ]}
                />
              </div>
            </Surface>

            <div className="grid gap-4">
              <Surface className="p-5">
                <div className="text-[11px] uppercase tracking-[0.16em] text-muted">Cash</div>
                <div className="mono mt-2 text-2xl">{inr(cash?.current_cash)}</div>
                <div className="mt-1 text-sm text-muted">30-day {inr(cash?.forecast_30d)}</div>
                <Link to="/app/cash" className="mt-4 inline-block text-xs text-accent">
                  Open forecast →
                </Link>
              </Surface>
              <Surface className="p-5">
                <div className="text-[11px] uppercase tracking-[0.16em] text-muted">Who did the work</div>
                <div className="mt-3 space-y-2 text-sm">
                  <Row k="Deterministic" v={pct(cost.deterministic_pct)} />
                  <Row k="LLM saved" v={pct(cost.llm_calls_saved_pct)} />
                  <Row k="AI-assisted" v={pct(cost.ai_assisted_pct)} />
                </div>
              </Surface>
            </div>
          </div>

          <Surface className="overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4">
              <h3 className="text-sm font-medium">Open exceptions</h3>
              <Link to="/app/exceptions" className="text-xs text-muted hover:text-white">
                View all
              </Link>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Exception</th>
                  <th>Type</th>
                  <th>Amount</th>
                  <th>Decision</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="text-muted">
                      No exceptions in the last close.
                    </td>
                  </tr>
                ) : (
                  rows.map((e: any) => (
                    <tr key={e.id}>
                      <td>
                        <Link to={`/app/exceptions/${e.id}`} className="mono text-zinc-200 hover:text-white">
                          {e.id}
                        </Link>
                      </td>
                      <td className="text-muted">{e.exception_type}</td>
                      <td className="mono">{inr(e.amount)}</td>
                      <td>
                        <DecisionChip value={e.final_decision} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </Surface>

          {data?.run ? (
            <p className="mono text-[11px] text-muted">
              {data.run.job_id} · {data.run.status} · {data.run.duration_ms} ms
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted">{k}</span>
      <span className="mono">{v}</span>
    </div>
  );
}
