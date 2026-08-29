import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { DecisionChip, PageHeader, Surface, inr } from "../components/ui";

export default function ExceptionCenter() {
  const { data, isLoading } = useQuery({ queryKey: ["exceptions"], queryFn: api.exceptions });
  const rows = data || [];
  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Queue"
        title="Exceptions"
        subtitle="The controller does not force a match. Open a row for evidence, agent actions, and the refusal."
      />
      <Surface className="overflow-auto">
        {isLoading ? (
          <p className="p-8 text-sm text-muted">Loading exceptions…</p>
        ) : rows.length === 0 ? (
          <p className="p-8 text-sm text-muted">No exceptions. Run a demo close first.</p>
        ) : (
        <table className="data-table">
          <thead>
            <tr>
              {["Exception", "Txn", "Type", "Amount", "Confidence", "Decision", "Recommended"].map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((e: any) => (
              <tr key={e.id}>
                <td>
                  <Link to={`/app/exceptions/${e.id}`} className="mono text-zinc-200 hover:text-white">
                    {e.id}
                  </Link>
                </td>
                <td className="mono text-muted">{e.transaction_id}</td>
                <td>{e.exception_type}</td>
                <td className="mono">{inr(e.amount)}</td>
                <td className="mono">{((e.confidence || 0) * 100).toFixed(1)}%</td>
                <td>
                  <DecisionChip value={e.final_decision} />
                </td>
                <td className="text-muted">{e.recommended_action}</td>
              </tr>
            ))}
          </tbody>
        </table>
        )}
      </Surface>
    </div>
  );
}
