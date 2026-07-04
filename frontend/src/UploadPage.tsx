/* UploadPage.tsx — Video upload with drag-and-drop (Phase 16).
 *
 * Learning notes:
 * ---------------
 * This page lets users upload a video file to the ML pipeline.
 * The flow is:
 *   1. User drags a file or clicks to select one.
 *   2. We POST it to /api/jobs/predict-video → get a job ID.
 *   3. We poll GET /api/jobs/{id} every 2 seconds to check status.
 *   4. When status is "completed", we show the results.
 *
 * Drag-and-drop is handled with the HTML5 DragEvent API:
 *   - onDragOver → prevent default (allows drop).
 *   - onDrop    → read the file from event.dataTransfer.files.
 */

import { useState, useRef, useCallback } from "react";
import api from "./api";
import { useAuth } from "./AuthContext";
import "./UploadPage.css";

type JobStatus = "idle" | "uploading" | "processing" | "completed" | "failed";

interface JobResult {
  activity: string;
  confidence: number;
  is_violent: boolean;
  violence_score: number;
  top3: Array<{ activity: string; confidence: number }>;
}

export default function UploadPage() {
  const { user } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<JobStatus>("idle");
  const [result, setResult] = useState<JobResult | null>(null);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    if (!f.type.startsWith("video/")) {
      setError("Please select a video file (.mp4, .avi, .mov)");
      return;
    }
    setFile(f);
    setError("");
    setResult(null);
    setStatus("idle");
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, []);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const onDragLeave = useCallback(() => setDragOver(false), []);

  const handleUpload = async () => {
    if (!file) return;
    setStatus("uploading");
    setError("");
    setResult(null);

    try {
      const job = await api.uploadVideo(file);
      setStatus("processing");

      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const j = await api.getJob(job.id);
          if (j.status === "completed") {
            clearInterval(pollInterval);
            setResult(j.result);
            setStatus("completed");
          } else if (j.status === "failed") {
            clearInterval(pollInterval);
            setError(j.error || "Processing failed");
            setStatus("failed");
          }
        } catch {
          clearInterval(pollInterval);
          setError("Failed to check job status");
          setStatus("failed");
        }
      }, 2000);
    } catch (err: any) {
      setError(err.message || "Upload failed");
      setStatus("failed");
    }
  };

  const reset = () => {
    setFile(null);
    setStatus("idle");
    setResult(null);
    setError("");
  };

  return (
    <div className="upload-page">
      <div className="page-header">
        <div>
          <h1>Upload Video</h1>
          <p>Analyse a video for violence and activity detection</p>
        </div>
      </div>

      {user?.role !== "admin" ? (
        <div className="card empty-state" style={{ padding: "var(--space-12)" }}>
          <span className="drop-icon" style={{ color: "var(--accent-red)" }}>🔒</span>
          <p style={{ fontSize: "var(--font-lg)", fontWeight: 600, color: "var(--text-primary)", marginBottom: "var(--space-2)" }}>Access Denied</p>
          <p>You do not have permission to upload videos for analysis. Admin access is required.</p>
        </div>
      ) : (
        <>
          {/* Drop zone */}
          <div
            className={`card drop-zone ${dragOver ? "drop-zone-active" : ""} ${file ? "drop-zone-has-file" : ""}`}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              style={{ display: "none" }}
              onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
            />

            {file ? (
              <div className="drop-zone-file animate-fade-in">
                <span className="drop-icon">🎬</span>
                <p className="drop-filename">{file.name}</p>
                <p className="drop-filesize">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
              </div>
            ) : (
              <div className="drop-zone-empty">
                <span className="drop-icon">📤</span>
                <p>Drag & drop a video file here</p>
                <p className="drop-hint">or click to browse — MP4, AVI, MOV supported</p>
              </div>
            )}
          </div>

          {/* Action buttons */}
          <div className="upload-actions">
            {file && status === "idle" && (
              <button className="btn btn-primary" onClick={handleUpload}>
                Analyse Video
              </button>
            )}
            {(status === "completed" || status === "failed") && (
              <button className="btn btn-ghost" onClick={reset}>
                Upload Another
              </button>
            )}
          </div>

          {/* Processing indicator */}
          {(status === "uploading" || status === "processing") && (
            <div className="card processing-card animate-fade-in-up">
              <div className="processing-spinner" />
              <div>
                <h3>{status === "uploading" ? "Uploading..." : "AI Processing..."}</h3>
                <p>
                  {status === "uploading"
                    ? "Sending video to the server"
                    : "Running violence detection & activity recognition"}
                </p>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="card error-card animate-fade-in">
              <p>{error}</p>
            </div>
          )}
        </>
      )}

      {/* Results */}
      {result && (
        <div className="results-section animate-fade-in-up">
          <h2>Analysis Results</h2>

          <div className="results-grid">
            {/* Primary result */}
            <div className={`card result-primary ${result.is_violent ? "result-violent" : "result-safe"}`}>
              <div className="result-status-icon">
                {result.is_violent ? "🚨" : "✅"}
              </div>
              <h3>{result.activity}</h3>
              <p className="result-confidence">
                Confidence: {(result.confidence * 100).toFixed(1)}%
              </p>
              <span className={`badge ${result.is_violent ? "badge-danger" : "badge-success"}`}>
                {result.is_violent ? "VIOLENT ACTIVITY DETECTED" : "NORMAL ACTIVITY"}
              </span>
            </div>

            {/* Top 3 predictions */}
            <div className="card result-top3">
              <h3>Top Predictions</h3>
              <div className="top3-list">
                {result.top3?.map((pred, i) => (
                  <div key={`${pred.activity}-${i}`} className="top3-item">
                    <span className="top3-rank">#{i + 1}</span>
                    <span className="top3-name">{pred.activity}</span>
                    <div className="top3-bar-wrap">
                      <div
                        className="top3-bar"
                        style={{ width: `${pred.confidence * 100}%` }}
                      />
                    </div>
                    <span className="top3-pct">{(pred.confidence * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
