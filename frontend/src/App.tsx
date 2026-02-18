import { useCallback, useEffect, useRef, useState } from "react";
import { api, Capture, Session } from "./api";

// ── Helpers ────────────────────────────────────────────────────

function fmtTime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
    : `${m}:${String(sec).padStart(2, "0")}`;
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

// ── Session Card ───────────────────────────────────────────────

function SessionCard({
  session,
  onCapture,
}: {
  session: Session;
  onCapture: (c: Capture) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState(false);

  const handleScreenshot = async () => {
    setLoading(true);
    setError("");
    try {
      const c = await api.takeScreenshot(session.session_id);
      onCapture(c);
      setFlash(true);
      setTimeout(() => setFlash(false), 600);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const progress = session.duration_seconds
    ? (session.position_seconds / session.duration_seconds) * 100
    : 0;

  return (
    <div
      className={`session-card ${flash ? "flash" : ""}`}
      style={{
        border: "1px solid #333",
        borderRadius: 12,
        overflow: "hidden",
        background: "#1a1a2e",
        transition: "box-shadow 0.3s",
      }}
    >
      {session.thumbnail_url && (
        <div style={{ position: "relative" }}>
          <img
            src={session.thumbnail_url}
            alt=""
            style={{ width: "100%", height: 200, objectFit: "cover", display: "block" }}
            onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
          />
          <span
            style={{
              position: "absolute",
              bottom: 8,
              right: 8,
              background: "rgba(0,0,0,0.7)",
              color: "#fff",
              padding: "2px 8px",
              borderRadius: 4,
              fontSize: 13,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {fmtTime(session.position_seconds)} / {fmtTime(session.duration_seconds)}
          </span>
        </div>
      )}

      {/* Progress bar */}
      <div style={{ height: 3, background: "#333" }}>
        <div
          style={{
            height: "100%",
            width: `${progress}%`,
            background: session.source === "plex" ? "#e5a00d" : "#00a4dc",
            transition: "width 5s linear",
          }}
        />
      </div>

      <div style={{ padding: "12px 16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              textTransform: "uppercase",
              color: session.source === "plex" ? "#e5a00d" : "#00a4dc",
            }}
          >
            {session.source}
          </span>
          {session.year && (
            <span style={{ fontSize: 12, color: "#888" }}>({session.year})</span>
          )}
        </div>
        <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 2 }}>
          {session.title}
        </div>
        {session.subtitle && (
          <div style={{ fontSize: 14, color: "#aaa", marginBottom: 12 }}>
            {session.subtitle}
          </div>
        )}

        <button
          onClick={handleScreenshot}
          disabled={loading}
          style={{
            width: "100%",
            padding: "10px 0",
            background: loading ? "#555" : "#e5a00d",
            color: "#000",
            border: "none",
            borderRadius: 8,
            fontWeight: 700,
            fontSize: 15,
            cursor: loading ? "wait" : "pointer",
            transition: "background 0.2s",
          }}
        >
          {loading ? "Capturing…" : "Screenshot"}
        </button>

        {error && (
          <div style={{ marginTop: 8, color: "#ff6b6b", fontSize: 13 }}>{error}</div>
        )}
      </div>
    </div>
  );
}

// ── Gallery ────────────────────────────────────────────────────

function Gallery({
  captures,
  onDelete,
}: {
  captures: Capture[];
  onDelete: (id: string) => void;
}) {
  if (captures.length === 0) {
    return (
      <div style={{ textAlign: "center", color: "#666", padding: 40 }}>
        No captures yet. Take a screenshot while something is playing!
      </div>
    );
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
        gap: 12,
      }}
    >
      {captures.map((c) => (
        <div
          key={c.id}
          style={{
            border: "1px solid #333",
            borderRadius: 10,
            overflow: "hidden",
            background: "#1a1a2e",
          }}
        >
          {c.capture_type === "screenshot" && c.status === "complete" ? (
            <a href={c.file_url} target="_blank" rel="noopener">
              <img
                src={c.file_url}
                alt={c.media_title}
                style={{ width: "100%", height: 150, objectFit: "cover", display: "block" }}
              />
            </a>
          ) : (
            <div
              style={{
                width: "100%",
                height: 150,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "#111",
                color: "#888",
                fontSize: 13,
              }}
            >
              {c.status === "pending"
                ? "Processing…"
                : c.status === "failed"
                  ? "Failed"
                  : c.capture_type === "clip"
                    ? `Clip · ${fmtTime(c.duration_seconds ?? 0)}`
                    : "Screenshot"}
            </div>
          )}

          <div style={{ padding: "8px 12px" }}>
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {c.media_title}
            </div>
            <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>
              {fmtTime(c.timestamp_seconds)} · {fmtSize(c.file_size_bytes)} ·{" "}
              {fmtDate(c.created_at)}
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              {c.status === "complete" && (
                <a
                  href={`/api/captures/${c.id}/file`}
                  download
                  style={{
                    flex: 1,
                    textAlign: "center",
                    padding: "6px 0",
                    background: "#2a4a7f",
                    color: "#fff",
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    textDecoration: "none",
                  }}
                >
                  Download
                </a>
              )}
              <button
                onClick={() => onDelete(c.id)}
                style={{
                  flex: 1,
                  padding: "6px 0",
                  background: "#4a1a1a",
                  color: "#ff6b6b",
                  border: "none",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── App ────────────────────────────────────────────────────────

type Tab = "now-playing" | "gallery";

export default function App() {
  const [tab, setTab] = useState<Tab>("now-playing");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [captures, setCaptures] = useState<Capture[]>([]);
  const [sessionsError, setSessionsError] = useState("");
  const pollRef = useRef<number | undefined>(undefined);

  // Poll sessions
  const fetchSessions = useCallback(async () => {
    try {
      const s = await api.getSessions();
      setSessions(s);
      setSessionsError("");
    } catch (e: any) {
      setSessionsError(e.message);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
    pollRef.current = window.setInterval(fetchSessions, 5000);
    return () => clearInterval(pollRef.current);
  }, [fetchSessions]);

  // Fetch gallery
  const fetchCaptures = useCallback(async () => {
    try {
      setCaptures(await api.getCaptures());
    } catch {}
  }, []);

  useEffect(() => {
    if (tab === "gallery") fetchCaptures();
  }, [tab, fetchCaptures]);

  const handleCapture = (c: Capture) => {
    setCaptures((prev) => [c, ...prev]);
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteCapture(id);
      setCaptures((prev) => prev.filter((c) => c.id !== id));
    } catch {}
  };

  const tabStyle = (t: Tab) => ({
    padding: "10px 24px",
    background: tab === t ? "#e5a00d" : "transparent",
    color: tab === t ? "#000" : "#888",
    border: "none",
    borderRadius: 8,
    fontWeight: 700 as const,
    fontSize: 14,
    cursor: "pointer" as const,
    transition: "all 0.2s",
  });

  return (
    <div
      style={{
        maxWidth: 800,
        margin: "0 auto",
        padding: "20px 16px",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        color: "#eee",
        minHeight: "100vh",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 24,
        }}
      >
        <h1 style={{ fontSize: 24, fontWeight: 800, margin: 0 }}>
          MediaSnap
        </h1>
        <div style={{ display: "flex", gap: 4, background: "#111", borderRadius: 10, padding: 3 }}>
          <button style={tabStyle("now-playing")} onClick={() => setTab("now-playing")}>
            Now Playing
          </button>
          <button style={tabStyle("gallery")} onClick={() => setTab("gallery")}>
            Gallery
          </button>
        </div>
      </div>

      {/* Content */}
      {tab === "now-playing" && (
        <>
          {sessionsError && (
            <div style={{ color: "#ff6b6b", marginBottom: 16, fontSize: 14 }}>
              Error connecting: {sessionsError}
            </div>
          )}
          {sessions.length === 0 && !sessionsError && (
            <div style={{ textAlign: "center", color: "#666", padding: 60 }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>📺</div>
              <div style={{ fontSize: 16 }}>Nothing playing right now</div>
              <div style={{ fontSize: 13, marginTop: 4 }}>
                Start something on Plex or Jellyfin and it will appear here.
              </div>
            </div>
          )}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
              gap: 16,
            }}
          >
            {sessions.map((s) => (
              <SessionCard key={s.session_id} session={s} onCapture={handleCapture} />
            ))}
          </div>
        </>
      )}

      {tab === "gallery" && <Gallery captures={captures} onDelete={handleDelete} />}

      {/* Global styles for flash animation */}
      <style>{`
        body { background: #0f0f23; margin: 0; }
        .session-card.flash { box-shadow: 0 0 20px rgba(229, 160, 13, 0.5); }
        a { color: inherit; }
        * { box-sizing: border-box; }
      `}</style>
    </div>
  );
}