/* App.tsx — Main application router (Phase 12-16 integration).
 *
 * Learning notes:
 * ---------------
 * This is the root component of our app. It uses the `useAuth` hook
 * from our AuthContext to check if a user is logged in.
 *
 * If not logged in -> Show the LoginPage.
 * If logged in     -> Show the Layout wrapper with a sidebar.
 *
 * Inside the Layout, we conditionally render the active page
 * (Dashboard, Cameras, Events, or Upload) based on state.
 */

import { useState } from "react";
import { useAuth } from "./AuthContext";
import { Toaster } from "react-hot-toast";

import LoginPage from "./LoginPage";
import Layout from "./Layout";
import DashboardPage from "./DashboardPage";
import CamerasPage from "./CamerasPage";
import EventsPage from "./EventsPage";
import UploadPage from "./UploadPage";

export default function App() {
  const { user, loading } = useAuth();
  const [activePage, setActivePage] = useState("dashboard");

  // Show a loading state while we check the token on refresh
  if (loading) {
    return (
      <div style={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
        Loading AI Surveillance Platform...
      </div>
    );
  }

  // If no user is logged in, show the login page
  if (!user) {
    return <LoginPage />;
  }

  // Simple router function to render the correct page
  const renderPage = () => {
    switch (activePage) {
      case "dashboard": return <DashboardPage />;
      case "cameras":   return <CamerasPage />;
      case "events":    return <EventsPage />;
      case "upload":    return <UploadPage />;
      default:          return <DashboardPage />;
    }
  };

  return (
    <>
      <Toaster position="top-right" />
      <Layout activePage={activePage} onNavigate={setActivePage}>
        {renderPage()}
      </Layout>
    </>
  );
}
