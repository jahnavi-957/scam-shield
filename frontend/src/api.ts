// Minimal typed client for the Scam Shield backend API.
// In local dev the browser reaches the backend directly (CORS is enabled for
// http://localhost:5173). In production the frontend and backend share an
// origin behind the ALB, which makes CORS irrelevant there.

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export interface HealthStatus {
  status: string;
  service: string;
  database: string;
}

export async function fetchHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return (await response.json()) as HealthStatus;
}