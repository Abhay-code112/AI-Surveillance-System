/* Layout.tsx — App shell with sidebar navigation (Phase 12).
 *
 * Learning notes:
 * ---------------
 * The "Layout" component wraps every page in the app.  It provides:
 *   - A fixed sidebar for navigation (Dashboard, Cameras, Events, Upload)
 *   - A header bar with the user's name and logout button
 *   - A content area where the current page renders
 *
 * We use React state to track which "page" is active instead of
 * a full router library.  This keeps things simple for learning.
 */

import type { ReactNode } from "react";
import { useAuth } from "./AuthContext";
import "./Layout.css";

interface LayoutProps {
  activePage: string;
  onNavigate: (page: string) => void;
  children: ReactNode;
}

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: "📊" },
  { id: "cameras",   label: "Cameras",   icon: "📹" },
  { id: "events",    label: "Events",    icon: "📋" },
  { id: "upload",    label: "Upload",    icon: "📤" },
];

export default function Layout({ activePage, onNavigate, children }: LayoutProps) {
  const { user, logout } = useAuth();

  return (
    <div className="layout">
      {/* ── Sidebar ──────────────────────────────────────────── */}
      <aside className="sidebar glass">
        <div className="sidebar-brand">
          <svg width="32" height="32" viewBox="0 0 48 48" fill="none">
            <rect width="48" height="48" rx="12" fill="url(#sb-grad)" />
            <path d="M14 20C14 17.79 15.79 16 18 16H30C32.21 16 34 17.79 34 20V28C34 30.21 32.21 32 30 32H18C15.79 32 14 30.21 14 28V20Z" stroke="white" strokeWidth="2"/>
            <circle cx="24" cy="24" r="4" stroke="white" strokeWidth="2"/>
            <circle cx="24" cy="24" r="1.5" fill="white"/>
            <defs>
              <linearGradient id="sb-grad" x1="0" y1="0" x2="48" y2="48">
                <stop stopColor="#3b82f6" /><stop offset="1" stopColor="#a855f7" />
              </linearGradient>
            </defs>
          </svg>
          <div>
            <h2>AI CCTV</h2>
            <span>Surveillance</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={`sidebar-link ${activePage === item.id ? "active" : ""}`}
              onClick={() => onNavigate(item.id)}
            >
              <span className="sidebar-icon">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        {/* User info at bottom */}
        <div className="sidebar-user">
          <div className="sidebar-user-info">
            <div className="sidebar-avatar">
              {user?.username.charAt(0).toUpperCase()}
            </div>
            <div>
              <p className="sidebar-username">{user?.username}</p>
              <p className="sidebar-role">{user?.role}</p>
            </div>
          </div>
          <button className="sidebar-logout" onClick={logout} title="Sign out">
            ⏻
          </button>
        </div>
      </aside>

      {/* ── Main content ────────────────────────────────────── */}
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
