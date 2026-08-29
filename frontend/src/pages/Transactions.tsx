import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";
import { api } from "../services/api";
import { DecisionChip, PageHeader, Surface } from "../components/ui";

const FILTERS = [
  { id: "", label: "All" },
  { id: "AUTO_MATCH", label: "Matched" },
  { id: "AUTO_RESOLVE", label: "Gate resolved" },
  { id: "HUMAN_REVIEW", label: "Review" },
  { id: "UNRESOLVED", label: "Unresolved" },
];

export default function Transactions() {
  const [f, setF] = useState("");
  const { data } = useQuery({ queryKey: ["tx", f], queryFn: () => api.transactions(f || undefined) });
  const rows = data || [];
  return (
    <div className="space-y-6">
      <PageHeader kicker="Ledger" title="Transactions" subtitle="Every row is a posted decision. Open why-matched before you argue with the F1." />
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((x) => (
          <button
            key={x.id}
            onClick={() => setF(x.id)}
            className={`rounded-full px-3 py-1 text-xs ${f === x.id ? "bg-white text-black" : "hairline text-muted hover:text-white"}`}
          >
            {x.label}
          </button>
        ))}
      </div>
      <Surface className="overflow-auto">
        <table className="data-table">
          <thead>
            <tr>
              {["Transaction", "Vendor", "Amount", "Date", "Candidate", "Score", "Decision", ""].map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r: any) => (
              <tr key={r.id}>
                <td className="mono">{r.transaction?.id}</td>
                <td>{r.vendor}</td>
                <td className="mono">₹{r.amount}</td>
                <td className="text-muted">{r.date}</td>
                <td className="mono text-muted">{r.invoice?.invoice_number || r.candidate_invoice_ids?.[0] || "—"}</td>
                <td className="mono">{((r.match_score || 0) * 100).toFixed(1)}%</td>
                <td>
                  <DecisionChip value={r.decision} />
                </td>
                <td>
                  <details className="text-xs">
                    <summary className="cursor-pointer text-muted">Why</summary>
                    <pre className="mt-1 max-w-xs whitespace-pre-wrap text-muted">
                      {JSON.stringify(r.why?.checks || r.why, null, 2)}
                    </pre>
                  </details>
                  <Link className="ml-2 text-xs text-accent" to={`/app/graph/${r.transaction?.id}`}>
                    Graph
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Surface>
    </div>
  );
}
