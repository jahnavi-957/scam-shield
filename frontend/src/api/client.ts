// Typed client for the Scam Shield backend API.
// In local dev the browser reaches the backend directly (CORS is enabled for
// http://localhost:5173). In production the frontend and backend share an
// origin behind the ALB, which makes CORS irrelevant there.

const API_URL = (import.meta.env?.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

// --------------------------------------------------------------------------- #
// Types — mirror the backend Pydantic schemas exactly.
// --------------------------------------------------------------------------- #

export interface HealthResponse {
  status: string;
  service: string;
  database: string;
}

export interface EntitySummary {
  type: string;
  value: string;
  report_count: number;
}

export interface AnalysisResponse {
  message_id: number;
  source: string;
  is_scam: boolean;
  scam_type: string;
  confidence: number;
  explanation: string;
  entities: EntitySummary[];
  prior_reports: number;
  near_duplicates: number[];
  alert_triggered: boolean;
  created_at: string; // ISO-8601
}

export interface PresignedUploadResponse {
  s3_key: string;
  url: string;
  method: string;
  content_type: string;
  expires_in: number;
}

export interface ReportSummary {
  message_id: number;
  source: string;
  scam_type: string | null;
  confidence: number | null;
  is_scam: boolean | null;
  created_at: string;
}

export interface EntityHistoryResponse {
  entity_type: string;
  value: string;
  report_count: number;
  first_seen_at: string;
  last_alert_at: string | null;
  recent_reports: ReportSummary[];
}

// --------------------------------------------------------------------------- #
// Low-level helpers
// --------------------------------------------------------------------------- #

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { Accept: 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body?.detail) message = body.detail;
    } catch {
      /* ignore body parse failure */
    }
    throw new Error(message);
  }

  if (response.status === 204) return undefined as unknown as T;
  return (await response.json()) as T;
}

// --------------------------------------------------------------------------- #
// Endpoints
// --------------------------------------------------------------------------- #

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health');
}

export function analyzeText(text: string): Promise<AnalysisResponse> {
  return request<AnalysisResponse>('/analyze/text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
}

export function analyzeScreenshot(s3_key: string): Promise<AnalysisResponse> {
  return request<AnalysisResponse>('/analyze/screenshot', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ s3_key }),
  });
}

export function getPresignedUploadUrl(
  contentType = 'image/png',
): Promise<PresignedUploadResponse> {
  const query = `?content_type=${encodeURIComponent(contentType)}`;
  return request<PresignedUploadResponse>(`/uploads/presigned-url${query}`);
}

export function getEntityHistory(entityValue: string): Promise<EntityHistoryResponse> {
  const encoded = encodeURIComponent(entityValue.trim());
  return request<EntityHistoryResponse>(`/entities/${encoded}`);
}

// --------------------------------------------------------------------------- #
// Direct-to-S3 upload. The presigned URL is PUT-only and signed for a single
// content type, so we mirror that header exactly.
// --------------------------------------------------------------------------- #
export async function uploadToS3(
  presigned: PresignedUploadResponse,
  file: Blob,
): Promise<void> {
  const response = await fetch(presigned.url, {
    method: presigned.method ?? 'PUT',
    headers: {
      'Content-Type': presigned.content_type,
      'Content-Length': String(file.size),
    },
    body: file,
  });

  if (!response.ok) {
    throw new Error(
      `S3 upload failed with status ${response.status}. Please try again.`,
    );
  }
}