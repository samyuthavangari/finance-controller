import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../services/api";
import { PageHeader, Surface } from "../components/ui";

const SUGGESTIONS = [
  "Why did TX_0022 auto-resolve?",
  "Why is TX_0002 unresolved?",
  "What settlements exist for TX_0082?",
  "List recent AUTO_RESOLVE decisions",
];

export default function SettlementAgent() {
  const [q, setQ] = useState(SUGGESTIONS[0]);
  const [log, setLog] = useState<{ q: string; a: any }[]>([]);
  const mut = useMutation({
    mutationFn: (question: string) => api.settlementAsk(question),
    onSuccess: (a, question) => setLog((l) => [{ q: question, a }, ...l]),
  });

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        kicker="Q&A"
        title="Settlement"
        subtitle="Asks over closed books in SQL. Amounts come from Decimal tools. Chat cannot AUTO_RESOLVE the ledger."
      />
      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="rounded-full hairline px-3 py-1 text-xs text-muted hover:text-white" onClick={() => setQ(s)}>
            {s}
          </button>
        ))}
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          mut.mutate(q);
        }}
      >
        <input
          className="flex-1 rounded-full border border-white/10 bg-panel px-4 py-2.5 text-sm"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button className="btn btn-primary" disabled={mut.isPending}>
          {mut.isPending ? "Asking…" : "Ask"}
        </button>
      </form>
      {mut.isError ? <p className="text-sm text-danger">{String(mut.error)}</p> : null}
      <div className="space-y-3">
        {log.map((row, i) => (
          <Surface key={i} className="p-5 text-sm">
            <div className="text-accent">{row.q}</div>
            <p className="mt-2 leading-relaxed">{row.a.answer}</p>
            <div className="mt-2 text-xs text-muted">
              LLM={String(row.a.used_llm)} · {row.a.gate_notes}
            </div>
          </Surface>
        ))}
      </div>
    </div>
  );
}
