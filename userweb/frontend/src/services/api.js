const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

function formatErrorDetail(detail) {
  if (!detail) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((err) => {
        const field = Array.isArray(err.loc) ? err.loc.at(-1) : null;
        return field ? `${field}: ${err.msg}` : err.msg;
      })
      .join("; ");
  }
  return null;
}

export async function checkHealth() {
  const response = await fetch(`${BACKEND_URL}/`);
  if (!response.ok) throw new Error(`Backend returned status ${response.status}`);
  return response.json();
}

export async function analyzeVitals(vitals) {
  const response = await fetch(`${BACKEND_URL}/analyze-vitals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(vitals),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(formatErrorDetail(body?.detail) || `Backend returned status ${response.status}`);
  }
  return response.json();
}

export { BACKEND_URL };
