export function useApiToken() {
  return import.meta.env.VITE_API_TOKEN || "demo-token";
}
