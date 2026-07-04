/* EventsPage.tsx — Surveillance event history (Phase 15).
 *
 * Learning notes:
 * ---------------
 * This page shows a paginated table of all detected events.
 * Each row shows the timestamp, activity, confidence, camera,
 * and whether it was violent.
 *
 * Pagination is handled server-side via query params:
 *   GET /api/events?page=1&per_page=20
 * The server returns { events: [...], total: N, page: 1 }.
 */

import { useState, useEffect } from "react";
import api from "./api";
import "./EventsPage.css";

interface SurveillanceEvent {
  id: number;
  timestamp: string;
  activity: string;
  confidence: number;
  is_violent: boolean;
  violence_score: number;
  camera_id: string;
  mode: string;
  alert_sent: boolean;
}

export default function EventsPage() {
  const [events, setEvents] = useState<SurveillanceEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const perPage = 15;

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const data = await api.getEvents(page, perPage);
      setEvents(data.events);
      setTotal(data.total);
    } catch (err) {
      console.error("Failed to fetch events:", err);
    }
    setLoading(false);
  };

  useEffect(() => { fetchEvents(); }, [page]);

  const totalPages = Math.ceil(total / perPage);

  return (
    <div className="events-page">
      <div className="page-header">
        <div>
          <h1>Events</h1>
          <p>{total} surveillance events recorded</p>
        </div>
        <button className="btn btn-ghost" onClick={fetchEvents}>
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="empty-state"><p>Loading events...</p></div>
      ) : events.length === 0 ? (
        <div className="card empty-state">
          <p>No events recorded yet. Upload a video or start a camera to detect activities.</p>
        </div>
      ) : (
        <>
          <div className="card events-table-wrap">
            <table className="events-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Timestamp</th>
                  <th>Activity</th>
                  <th>Confidence</th>
                  <th>Status</th>
                  <th>Camera</th>
                  <th>Mode</th>
                  <th>Alert</th>
                </tr>
              </thead>
              <tbody>
                {events.map((evt, i) => (
                  <tr key={evt.id} className={`animate-fade-in stagger-${(i % 6) + 1}`}>
                    <td className="event-id">#{evt.id}</td>
                    <td>{new Date(evt.timestamp).toLocaleString()}</td>
                    <td className="event-activity">{evt.activity}</td>
                    <td>
                      <div className="conf-bar-wrap">
                        <div
                          className="conf-bar"
                          style={{
                            width: `${evt.confidence * 100}%`,
                            background: evt.confidence > 0.7 ? "var(--accent-green)" : "var(--accent-yellow)",
                          }}
                        />
                        <span>{(evt.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${evt.is_violent ? "badge-danger" : "badge-success"}`}>
                        {evt.is_violent ? "VIOLENT" : "NORMAL"}
                      </span>
                    </td>
                    <td className="event-camera">{evt.camera_id || "Upload"}</td>
                    <td>
                      <span className={`badge ${evt.mode === "live" ? "badge-info" : "badge-warning"}`}>
                        {evt.mode?.toUpperCase() || "VIDEO"}
                      </span>
                    </td>
                    <td>{evt.alert_sent ? "✅" : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="pagination">
              <button
                className="btn btn-ghost"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                ← Previous
              </button>
              <span className="pagination-info">
                Page {page} of {totalPages}
              </span>
              <button
                className="btn btn-ghost"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
