import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import { PageHeader, Surface } from "../components/ui";

export default function Audit() {
  const { data } = useQuery({ queryKey: ["audit"], queryFn: () => api.audit() });
  const rows = data || [];
  return (
    <div className="space-y-6">
      <PageHeader kicker="Trail" title="Audit" subtitle="Every gate accept and reject, in order." />
      <Surface className="max-h-[70vh] space-y-1 overflow-auto p-4 font-mono text-xs">
        {rows.map((r: any) => (
          <div key={r.id}>
            <span className="text-muted">{r.ts}</span> <span className="text-accent">{r.event}</span> {r.detail}
          </div>
        ))}
      </Surface>
    </div>
  );
}
