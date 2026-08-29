const API = import.meta.env.VITE_API_URL ?? "";
const TOKEN = import.meta.env.VITE_API_TOKEN || "demo-token";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export const api = {
  metrics: () => req<any>("/api/metrics"),
  benchmark: () => req<any>("/api/benchmark"),
  exceptions: () => req<any[]>("/api/exceptions"),
  exception: (id: string) => req<any>(`/api/exceptions/${id}`),
  review: (id: string, decision: string) =>
    req(`/api/exceptions/${id}/review`, { method: "POST", body: JSON.stringify({ decision }) }),
  transactions: (decision?: string) =>
    req<any[]>(`/api/transactions${decision ? `?decision=${decision}` : ""}`),
  run: (jobId: string) => req<any>(`/api/reconciliation/${jobId}`),
  startRun: () => req<any>("/api/reconciliation/run", { method: "POST", body: JSON.stringify({ investigate: true }) }),
  demo: () => req<any>("/api/demo/run", { method: "POST", body: "{}" }),
  settlementAsk: (question: string) =>
    req<any>("/api/settlement/ask", { method: "POST", body: JSON.stringify({ question }) }),
  cash: () => req<any>("/api/cash-position"),
  simulate: (body: any) => req<any>("/api/cash-position/simulate", { method: "POST", body: JSON.stringify(body) }),
  audit: (runId?: string) => req<any[]>(`/api/audit${runId ? `?run_id=${runId}` : ""}`),
  graph: (txId: string) => req<any>(`/api/graph/${txId}`),
  stress: (records: number) =>
    req<any>("/api/stress-test", { method: "POST", body: JSON.stringify({ records }) }),
  upload: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API}/api/datasets/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${TOKEN}` },
      body: fd,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
};
