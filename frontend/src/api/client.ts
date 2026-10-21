// Typed client for the Scam Shield backend API.
// Development talks to the local backend. Production uses the same origin by
// default, or an explicitly HTTPS API origin when one is configured.

const LOCAL_HOSTNAMES = new Set(['localhost', '127.0.0.1', '[::1]']);

function normalizeBaseUrl(value: string): string {
  return value.replace(/\/+$/, '');
}

function resolveApiBaseUrl(): string {
  const configured = (import.meta.env.VITE_API_URL as string | undefined)?.trim();

  if (import.meta.env.DEV) {
    const candidate = configured || 'http://localhost:8000';
    const parsed = new URL(candidate, window.location.origin);

    if (
      !LOCAL_HOSTNAMES.has(parsed.hostname) ||
      !['http:', 'https:'].includes(parsed.protocol)
    ) {
      throw new Error('VITE_API_URL must point to a localhost API during development.');
    }

    return normalizeBaseUrl(candidate);
  }

  if (!configured) return '';

  // A same-origin path is safe in production. Protocol-relative URLs are
  // intentionally rejected because they can resolve to HTTP.
  if (configured.startsWith('/') && !configured.startsWith('//')) {
    const relativeUrl = new URL(configured, 'https://scamshield.invalid');
    if (relativeUrl.origin !== 'https://scamshield.invalid') {
      throw new Error('VITE_API_URL must be a relative path or an HTTPS URL in production.');
    }
    return normalizeBaseUrl(configured);
  }

  let parsed: URL;
  try {
    parsed = new URL(configured);
  } catch {
    throw new Error('VITE_API_URL must be a relative path or an HTTPS URL in production.');
  }

  if (parsed.protocol !== 'https:') {
    throw new Error('VITE_API_URL must use HTTPS in production.');
  }

  return normalizeBaseUrl(configured);
}

const API_BASE_URL = resolveApiBaseUrl();

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
  truncated?: boolean;
  classifier_kind?: string;
  similarity_score?: number | null;
  matched_scam_id?: string | null;
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

export interface FastApiValidationError {
  loc?: Array<string | number>;
  msg?: string;
  type?: string;
  [key: string]: unknown;
}

export type FastApiDetail = string | FastApiValidationError[];

export class ApiError extends Error {
  readonly status: number;
  readonly detail: FastApiDetail | null;

  constructor(status: number, detail: FastApiDetail | null) {
    const detailMessage = formatApiErrorDetail(detail);
    super(detailMessage || `Request failed with status ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

// --------------------------------------------------------------------------- #
// Low-level helpers
// --------------------------------------------------------------------------- #

function parseApiDetail(body: unknown): FastApiDetail | null {
  if (!body || typeof body !== 'object' || !('detail' in body)) return null;

  const detail = body.detail;
  if (typeof detail === 'string') return detail;
  if (!Array.isArray(detail)) return null;

  return detail.filter(
    (item): item is FastApiValidationError =>
      Boolean(item) && typeof item === 'object' && !Array.isArray(item),
  );
}

function formatApiErrorDetail(detail: FastApiDetail | null): string {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;

  return detail
    .map((item) => item.msg?.trim() || 'Request validation failed')
    .join('; ');
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });

  if (!response.ok) {
    let detail: FastApiDetail | null = null;
    try {
      detail = parseApiDetail(await response.json());
    } catch {
      /* ignore body parse failure */
    }
    throw new ApiError(response.status, detail);
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
  const query = `?value=${encodeURIComponent(entityValue.trim())}`;
  return request<EntityHistoryResponse>(`/entities${query}`);
}

export type SupportedImageContentType = 'image/png' | 'image/jpeg';

export function normalizeImageContentType(
  contentType: string,
): SupportedImageContentType | null {
  switch (contentType.trim().toLowerCase()) {
    case 'image/png':
      return 'image/png';
    case 'image/jpeg':
    case 'image/jpg':
      return 'image/jpeg';
    default:
      return null;
  }
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
    },
    body: file,
  });

  if (!response.ok) {
    throw new Error(
      `S3 upload failed with status ${response.status}. Please try again.`,
    );
  }
}
