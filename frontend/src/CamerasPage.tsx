/* CamerasPage.tsx — Camera management grid (Phase 14).
 *
 * Learning notes:
 * ---------------
 * This page fetches all registered cameras from /api/cameras
 * and displays them in a grid.  Each card shows the camera's
 * name, location, status, and event counts from /api/analytics/cameras.
 *
 * You can add new cameras via a form and delete existing ones.
 */

import { useState, useEffect } from "react";
import toast from "react-hot-toast";
import api from "./api";
import { useAuth } from "./AuthContext";
import "./CamerasPage.css";

interface Camera {
  id: number;
  name: string;
  location: string;
  connection_url: string;
  is_active: boolean;
  total_events?: number;
  violent_events?: number;
  thread_alive?: boolean;
  last_activity?: string;
  last_event_at?: string;
}

export default function CamerasPage() {
  const { user } = useAuth();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [location, setLocation] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchCameras = async () => {
    try {
      // Get analytics data which includes event counts
      const data = await api.getCameraAnalytics();
      setCameras(data.cameras || []);
    } catch {
      try {
        // Fallback to basic camera list
        const list = await api.getCameras();
        setCameras(list);
      } catch (err: any) {
        toast.error("Failed to fetch cameras: " + err.message);
      }
    }
    setLoading(false);
  };

  useEffect(() => { fetchCameras(); }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createCamera({ name, connection_url: url, location, is_active: true });
      setName(""); setUrl(""); setLocation("");
      setShowForm(false);
      fetchCameras();
      toast.success("Camera added successfully");
    } catch (err: any) {
      toast.error("Failed to add camera: " + err.message);
    }
  };

  const handleToggle = async (cam: Camera) => {
    try {
      await api.updateCamera(cam.id, { is_active: !cam.is_active });
      fetchCameras();
    } catch (err: any) {
      toast.error("Failed to update camera: " + err.message);
    }
  };

  const handleDelete = async (id: number) => {
    if (confirm("Delete this camera?")) {
      try {
        await api.deleteCamera(id);
        fetchCameras();
        toast.success("Camera deleted");
      } catch (err: any) {
        toast.error("Failed to delete camera: " + err.message);
      }
    }
  };

  return (
    <div className="cameras-page">
      <div className="page-header">
        <div>
          <h1>Cameras</h1>
          <p>Manage surveillance camera feeds</p>
        </div>
        {user?.role === "admin" && (
          <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Cancel" : "+ Add Camera"}
          </button>
        )}
      </div>

      {/* Add camera form */}
      {showForm && (
        <form className="card add-camera-form animate-fade-in-up" onSubmit={handleAdd}>
          <div className="form-grid">
            <div className="form-field">
              <label>Camera Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Front Entrance" required />
            </div>
            <div className="form-field">
              <label>Connection URL</label>
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="rtsp://... or 0 for webcam" required />
            </div>
            <div className="form-field">
              <label>Location</label>
              <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Building A, Floor 2" />
            </div>
          </div>
          <button type="submit" className="btn btn-primary" style={{ marginTop: "var(--space-4)" }}>
            Register Camera
          </button>
        </form>
      )}

      {/* Camera grid */}
      {loading ? (
        <div className="empty-state"><p>Loading cameras...</p></div>
      ) : cameras.length === 0 ? (
        <div className="card empty-state">
          <p>No cameras registered yet. Click "+ Add Camera" to get started.</p>
        </div>
      ) : (
        <div className="camera-grid">
          {cameras.map((cam, i) => (
            <div key={cam.id} className={`card camera-card animate-fade-in-up stagger-${(i % 6) + 1}`}>
              {/* Status indicator */}
              <div className="camera-status-bar">
                <span className={`badge ${cam.thread_alive ? "badge-success" : cam.is_active ? "badge-warning" : "badge-info"}`}>
                  {cam.thread_alive ? "STREAMING" : cam.is_active ? "IDLE" : "INACTIVE"}
                </span>
                {user?.role === "admin" && (
                  <div className="camera-actions">
                    <button className="camera-toggle" onClick={() => handleToggle(cam)} title={cam.is_active ? "Stop Stream" : "Start Stream"}>
                      {cam.is_active ? "⏸" : "▶"}
                    </button>
                    <button className="camera-delete" onClick={() => handleDelete(cam.id)} title="Delete">
                      ✕
                    </button>
                  </div>
                )}
              </div>

              {/* Camera preview */}
              <div className="camera-preview">
                {cam.thread_alive ? (
                  <img src={`/api/cameras/${cam.id}/stream`} alt={`Live feed from ${cam.name}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                ) : (
                  <span className="camera-preview-icon">📹</span>
                )}
              </div>

              {/* Info */}
              <h3 className="camera-name">{cam.name}</h3>
              <p className="camera-location">{cam.location || "No location set"}</p>

              {/* Stats */}
              <div className="camera-stats">
                <div className="camera-stat">
                  <span className="camera-stat-val">{cam.total_events ?? 0}</span>
                  <span className="camera-stat-lbl">Events</span>
                </div>
                <div className="camera-stat">
                  <span className="camera-stat-val" style={{ color: "var(--accent-red)" }}>
                    {cam.violent_events ?? 0}
                  </span>
                  <span className="camera-stat-lbl">Violent</span>
                </div>
                <div className="camera-stat">
                  <span className="camera-stat-val">{cam.last_activity ?? "—"}</span>
                  <span className="camera-stat-lbl">Last Activity</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
