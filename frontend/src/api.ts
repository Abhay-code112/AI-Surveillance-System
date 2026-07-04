/* api.ts — Centralised HTTP client for the backend (Phase 12).
 *
 * Learning notes:
 * ---------------
 * Instead of scattering `fetch()` calls across components, we create
 * ONE module that handles:
 *   1. Base URL configuration (points at our FastAPI backend).
 *   2. Automatic JWT token injection via Authorization header.
 *   3. Consistent error handling.
 *
 * Every component imports `api` and calls e.g. `api.get("/events")`.
 */

const BASE_URL = "";

/** Retrieve the stored JWT token. */
function getToken(): string | null {
  return localStorage.getItem("token");
}

/** Generic fetch wrapper that adds auth headers and handles errors. */
async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  // Don't set Content-Type for FormData (browser sets it with boundary)
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json();
}

/** API methods matching our backend routes. */
const api = {
  // ── Auth ────────────────────────────────────────────────────
  register: (data: { username: string; email: string; password: string; role?: string }) =>
    request("/api/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: { username: string; password: string }) =>
    request<{ access_token: string; expires_in: number; user: any }>(
      "/api/auth/login",
      { method: "POST", body: JSON.stringify(data) }
    ),

  me: () => request<any>("/api/auth/me"),

  refreshToken: () => request<any>("/api/auth/refresh", { method: "POST" }),

  // ── Health ──────────────────────────────────────────────────
  health: () => request<any>("/api/health"),

  // ── Events ──────────────────────────────────────────────────
  getEvents: (page = 1, perPage = 20) =>
    request<any>(`/api/events?page=${page}&per_page=${perPage}`),

  // ── Alerts ──────────────────────────────────────────────────
  getAlerts: () => request<any>("/api/alerts"),

  // ── Cameras ─────────────────────────────────────────────────
  getCameras: () => request<any[]>("/api/cameras/"),
  createCamera: (data: any) =>
    request<any>("/api/cameras/", { method: "POST", body: JSON.stringify(data) }),
  deleteCamera: (id: number) =>
    request<void>(`/api/cameras/${id}`, { method: "DELETE" }),
  updateCamera: (id: number, data: any) =>
    request<any>(`/api/cameras/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  // ── Jobs ────────────────────────────────────────────────────
  uploadVideo: (file: File) => {
    const form = new FormData();
    form.append("video", file);
    return request<any>("/api/jobs/predict-video", { method: "POST", body: form });
  },
  getJob: (id: string) => request<any>(`/api/jobs/${id}`),

  // ── Analytics ───────────────────────────────────────────────
  getSummary: () => request<any>("/api/analytics/summary"),
  getActivityBreakdown: (hours = 24) =>
    request<any>(`/api/analytics/activity-breakdown?hours=${hours}`),
  getTimeline: (hours = 24, bucket = "hour") =>
    request<any>(`/api/analytics/timeline?hours=${hours}&bucket=${bucket}`),
  getCameraAnalytics: () => request<any>("/api/analytics/cameras"),
  getRecentAlerts: (limit = 10) =>
    request<any>(`/api/analytics/recent-alerts?limit=${limit}`),
};

export default api;
export { BASE_URL, getToken };
