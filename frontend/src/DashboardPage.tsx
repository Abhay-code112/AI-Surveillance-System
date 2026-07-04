/* DashboardPage.tsx — Live analytics dashboard (Phase 13).
 *
 * Learning notes:
 * ---------------
 * This is the "home" page of the surveillance platform.  It shows:
 *   1. **Stat cards** — total events, violent events, cameras, alerts.
 *   2. **Live event feed** — pushed via WebSocket in real-time.
 *   3. **Activity breakdown** — fetched from the analytics API.
 *
 * WebSocket integration:
 * - We open a WebSocket to `ws://127.0.0.1:8000/ws/events`.
 * - When the server pushes a "new_event" message, we prepend it
 *   to the live feed with an animation.
 * - If the connection drops, we auto-reconnect after 3 seconds.
 */

import { useState, useEffect, useRef } from "react";
import toast from "react-hot-toast";
import api from "./api";
import "./DashboardPage.css";

interface LiveEvent {
  id: number;
  timestamp: string;
  camera_id: string;
  activity: string;
  confidence: number;
  is_violent: boolean;
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<any>(null);
  const [breakdown, setBreakdown] = useState<any[]>([]);
  const [liveEvents, setLiveEvents] = useState<LiveEvent[]>([]);
  const [activeCameras, setActiveCameras] = useState<any[]>([]);
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("connecting");
  const wsRef = useRef<WebSocket | null>(null);

  // Fetch analytics on mount
  useEffect(() => {
    api.getSummary().then(setSummary).catch((err) => toast.error("Failed to load summary: " + err.message));
    api.getActivityBreakdown(24).then((d) => setBreakdown(d.breakdown)).catch((err) => toast.error("Failed to load breakdown: " + err.message));
    api.getEvents(1, 15).then((data) => {
      setLiveEvents(data.items || []);
    }).catch((err) => toast.error("Failed to load events: " + err.message));
    
    api.getCameras().then((data) => {
      setActiveCameras(data.filter((c: any) => c.thread_alive));
    }).catch(console.error);

    // Refresh summary every 30 seconds
    const interval = setInterval(() => {
      api.getSummary().then(setSummary).catch(console.error);
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket connection for live events
  useEffect(() => {
    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/ws/events`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => setWsStatus("connected");

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "new_event") {
            setLiveEvents((prev) => [data.event, ...prev].slice(0, 50));
            // Also refresh summary
            api.getSummary().then(setSummary).catch(console.error);
          }
        } catch { /* ignore parse errors */ }
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
        setTimeout(connect, 3000); // auto-reconnect
      };

      ws.onerror = () => ws.close();
    }

    connect();
    return () => wsRef.current?.close();
  }, []);

  const stats = [
    { label: "Total Events",  value: summary?.total_events ?? "—",  icon: "📋", color: "var(--accent-blue)" },
    { label: "Violent Events", value: summary?.violent_events ?? "—", icon: "🚨", color: "var(--accent-red)" },
    { label: "Active Cameras", value: summary?.active_cameras ?? "—", icon: "📹", color: "var(--accent-green)" },
    { label: "Total Alerts",   value: summary?.total_alerts ?? "—",   icon: "🔔", color: "var(--accent-orange)" },
  ];

  return (
    <div className="dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <div>
          <h1>Dashboard</h1>
          <p>Real-time surveillance overview</p>
        </div>
        <div className={`ws-status ws-${wsStatus}`}>
          <span className="ws-dot" />
          {wsStatus === "connected" ? "Live" : wsStatus === "connecting" ? "Connecting..." : "Reconnecting..."}
        </div>
      </div>

      {/* Stat cards */}
      <div className="stats-grid">
        {stats.map((s, i) => (
          <div key={s.label} className={`stat-card card animate-fade-in-up stagger-${i + 1}`}>
            <div className="stat-icon" style={{ background: s.color + "20", color: s.color }}>
              {s.icon}
            </div>
            <div className="stat-info">
              <span className="stat-value">{s.value}</span>
              <span className="stat-label">{s.label}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Live Video Feeds */}
      {activeCameras.length > 0 && (
        <div className="dashboard-live-feeds card animate-fade-in-up">
          <h3><span className="live-dot" /> Live Camera Feeds</h3>
          <div className="live-feeds-grid">
            {activeCameras.map(cam => (
              <div key={cam.id} className="live-feed-wrapper">
                <img src={`/api/cameras/${cam.id}/stream`} alt={`Camera ${cam.name}`} />
                <div className="live-feed-label">
                  <span className="feed-status-dot"></span> {cam.name}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Two-column: Live feed + Activity breakdown */}
      <div className="dashboard-grid">
        {/* Live event feed */}
        <div className="card live-feed-card">
          <h3>
            <span className="live-dot" /> Live Event Feed
          </h3>
          {liveEvents.length === 0 ? (
            <div className="empty-state">
              <p>No events yet. Events will appear here in real-time as cameras detect activity.</p>
            </div>
          ) : (
            <div className="live-feed-list">
              {liveEvents.map((evt) => (
                <div
                  key={evt.id}
                  className={`feed-item animate-slide-right ${evt.is_violent ? "feed-violent" : ""}`}
                >
                  <div className="feed-activity">
                    <span className={`badge ${evt.is_violent ? "badge-danger" : "badge-success"}`}>
                      {evt.is_violent ? "VIOLENT" : "NORMAL"}
                    </span>
                    <span className="feed-name">{evt.activity}</span>
                  </div>
                  <div className="feed-meta">
                    <span>{evt.camera_id}</span>
                    <span>{(evt.confidence * 100).toFixed(0)}%</span>
                    <span>{new Date(evt.timestamp).toLocaleTimeString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Activity breakdown */}
        <div className="card breakdown-card">
          <h3>Activity Breakdown (24h)</h3>
          {breakdown.length === 0 ? (
            <div className="empty-state">
              <p>No activity data yet. Upload a video or start a camera to see activity breakdown.</p>
            </div>
          ) : (
            <div className="breakdown-list">
              {breakdown.map((item, i) => {
                const maxCount = Math.max(...breakdown.map((b) => b.count));
                const pct = maxCount > 0 ? (item.count / maxCount) * 100 : 0;
                return (
                  <div key={item.activity} className={`breakdown-row animate-fade-in-up stagger-${i + 1}`}>
                    <div className="breakdown-label">
                      <span className="breakdown-name">{item.activity}</span>
                      <span className="breakdown-count">{item.count}</span>
                    </div>
                    <div className="breakdown-bar-bg">
                      <div
                        className="breakdown-bar"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="breakdown-conf">
                      Avg: {(item.avg_confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
