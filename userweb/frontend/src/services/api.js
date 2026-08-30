const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

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
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail || `Backend returned status ${response.status}`);
  }
  return response.json();
}

export { BACKEND_URL };
