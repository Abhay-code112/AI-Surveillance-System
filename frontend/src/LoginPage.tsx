/* LoginPage.tsx — Premium login/register form (Phase 12).
 *
 * Learning notes:
 * ---------------
 * This component has TWO modes: Login and Register.
 * It uses React's useState hook to toggle between them.
 *
 * When the form submits, it calls the AuthContext's login() or
 * register() function, which handles the API call and token storage.
 *
 * The styling uses glassmorphism (backdrop-filter: blur) and
 * gradient accents for a premium "command center" feel.
 */

import { useState } from "react";
import type { FormEvent } from "react";
import { useAuth } from "./AuthContext";
import "./LoginPage.css";

export default function LoginPage() {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (isRegister) {
        await register(username, email, password);
      } else {
        await login(username, password);
      }
    } catch (err: any) {
      setError(err.message || "Authentication failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      {/* Animated background orbs */}
      <div className="login-bg-orb login-bg-orb-1" />
      <div className="login-bg-orb login-bg-orb-2" />
      <div className="login-bg-orb login-bg-orb-3" />

      <div className="login-container animate-fade-in-up">
        {/* Logo / Brand */}
        <div className="login-brand">
          <div className="login-logo">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <rect width="48" height="48" rx="12" fill="url(#logo-gradient)" />
              <path d="M14 20C14 17.7909 15.7909 16 18 16H30C32.2091 16 34 17.7909 34 20V28C34 30.2091 32.2091 32 30 32H18C15.7909 32 14 30.2091 14 28V20Z" stroke="white" strokeWidth="2"/>
              <circle cx="24" cy="24" r="4" stroke="white" strokeWidth="2"/>
              <circle cx="24" cy="24" r="1.5" fill="white"/>
              <path d="M18 16V13" stroke="white" strokeWidth="2" strokeLinecap="round"/>
              <path d="M30 16V13" stroke="white" strokeWidth="2" strokeLinecap="round"/>
              <defs>
                <linearGradient id="logo-gradient" x1="0" y1="0" x2="48" y2="48">
                  <stop stopColor="#3b82f6" />
                  <stop offset="1" stopColor="#a855f7" />
                </linearGradient>
              </defs>
            </svg>
          </div>
          <h1>AI Surveillance</h1>
          <p>Intelligent CCTV Monitoring Platform</p>
        </div>

        {/* Form */}
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="login-field">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              required
              autoFocus
            />
          </div>

          {isRegister && (
            <div className="login-field animate-fade-in">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />
            </div>
          )}

          <div className="login-field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              required
              minLength={6}
            />
          </div>

          {error && (
            <div className="login-error animate-fade-in">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary login-submit"
            disabled={submitting}
          >
            {submitting ? (
              <span className="login-spinner" />
            ) : isRegister ? (
              "Create Account"
            ) : (
              "Sign In"
            )}
          </button>
        </form>

        {/* Toggle mode */}
        <div className="login-toggle">
          {isRegister ? (
            <p>
              Already have an account?{" "}
              <button onClick={() => { setIsRegister(false); setError(""); }}>
                Sign in
              </button>
            </p>
          ) : (
            <p>
              No account yet?{" "}
              <button onClick={() => { setIsRegister(true); setError(""); }}>
                Create one
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
