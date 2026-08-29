import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../services/api";
import { DecisionChip, PageHeader, Surface } from "../components/ui";
import { useState } from "react";

export default function ExceptionDetail() {
  const { id } = useParams();
  const { data } = useQuery({ queryKey: ["exc", id], queryFn: () => api.exception(id!), enabled: !!id });
  const [why, setWhy] = useState(false);
  const [ev, setEv] = useState(false);
  if (!data) return <p className="text-muted">Loading…</p>;
  const tx = data.transaction;
  const d = data.decision;

  return (
    <div className="space-y-6">
      <PageHeader
        kicker={data.exception_type}
        title={data.id}
        subtitle={data.reason}
        actions={<DecisionChip value={data.final_decision} />}
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Surface className="p-5">
          <h3 className="text-[11px] uppercase tracking-[0.16em] text-muted">Transaction</h3>
          {tx ? (
            <div className="mt-3 space-y-1 text-sm">
              <div className="mono">{tx.id}</div>
              <div>{tx.vendor_name_raw}</div>
              <div className="mono">
                ₹{tx.amount} {tx.currency}
              </div>
              <div className="text-muted">{tx.date}</div>
              <div className="text-muted">Ref {tx.payment_reference}</div>
            </div>
          ) : null}
          <p className="mt-4 text-xs text-muted">Candidates {(data.candidate_invoice_ids || []).join(" ") || "—"}</p>
        </Surface>
        <Surface className="p-5">
          <h3 className="text-[11px] uppercase tracking-[0.16em] text-muted">Invoices</h3>
          <div className="mt-3 space-y-2">
            {(data.invoices || []).map((inv: any) => (
              <div key={inv.id} className="rounded-xl bg-white/[0.03] p-3 text-sm">
                <div className="mono">{inv.invoice_number}</div>
                <div className="text-muted">
                  ₹{inv.total_amount} · tax ₹{inv.tax_amount}
                </div>
              </div>
            ))}
          </div>
          {tx ? (
            <Link className="mt-4 inline-block text-xs text-accent" to={`/app/graph/${tx.id}`}>
              Evidence graph →
            </Link>
          ) : null}
        </Surface>
        <Surface className="p-5">
          <h3 className="text-[11px] uppercase tracking-[0.16em] text-muted">Investigation</h3>
          <p className="mt-3 text-sm">{data.investigation?.summary}</p>
          {d ? (
            <div className="mt-3 space-y-1 text-sm">
              <DecisionChip value={d.decision} />
              <div className="text-muted">{d.reason}</div>
              <div className="text-xs">Authorized {String(d.authorized)}</div>
            </div>
          ) : null}
          <div className="mt-4 flex gap-2">
            <button className="btn btn-ghost !px-3 !py-1 text-xs" onClick={() => setWhy(!why)}>
              Why not
            </button>
            <button className="btn btn-ghost !px-3 !py-1 text-xs" onClick={() => setEv(!ev)}>
              Evidence
            </button>
          </div>
          {why ? <pre className="mt-3 whitespace-pre-wrap text-[11px] text-muted">{data.reason}</pre> : null}
          {ev ? (
            <pre className="mt-3 whitespace-pre-wrap text-[11px] text-muted">
              {JSON.stringify(data.evidence || d?.evidence, null, 2)}
            </pre>
          ) : null}
        </Surface>
      </div>
    </div>
  );
}
