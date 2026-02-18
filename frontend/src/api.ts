// ── Types ──────────────────────────────────────────────────────

export interface Session {
  session_id: string;
  source: "plex" | "jellyfin";
  title: string;
  subtitle: string;
  media_path: string;
  position_seconds: number;
  duration_seconds: number;
  thumbnail_url: string;
  year: number | null;
}

export interface Capture {
  id: string;
  source: string;
  media_title: string;
  timestamp_seconds: number;
  capture_type: "screenshot" | "clip";
  file_name: string;
  file_url: string;
  file_size_bytes: number;
  duration_seconds: number | null;
  status: "pending" | "complete" | "failed";
  error_message: string | null;
  created_at: string;
}

// ── API Client ─────────────────────────────────────────────────

const BASE = "/api";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  getSessions: () => request<Session[]>("/sessions"),

  takeScreenshot: (session_id: string, offset_seconds = 0) =>
    request<Capture>("/capture/screenshot", {
      method: "POST",
      body: JSON.stringify({ session_id, offset_seconds }),
    }),

  takeClip: (params: {
    session_id: string;
    relative_seconds?: number;
    start_seconds?: number;
    end_seconds?: number;
  }) =>
    request<Capture>("/capture/clip", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  getCaptures: (limit = 50, offset = 0) =>
    request<Capture[]>(`/captures?limit=${limit}&offset=${offset}`),

  getCapture: (id: string) => request<Capture>(`/captures/${id}`),

  deleteCapture: (id: string) =>
    request<{ deleted: string }>(`/captures/${id}`, { method: "DELETE" }),
};
