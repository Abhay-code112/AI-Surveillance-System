/* AuthContext.tsx — JWT Authentication state manager (Phase 12).
 *
 * Learning notes:
 * ---------------
 * React Context is a way to share state across the entire component
 * tree WITHOUT passing props manually through every level.
 *
 * How JWT auth works in the frontend:
 * 1. User fills in login form → we call POST /api/auth/login.
 * 2. Server returns a JWT token + user object.
 * 3. We store the token in localStorage and the user in React state.
 * 4. The api.ts module reads the token from localStorage and adds
 *    it as an "Authorization: Bearer <token>" header on every request.
 * 5. On page refresh, we try to restore the session by calling
 *    GET /api/auth/me with the stored token.
 *
 * This pattern is used in virtually every production React app.
 */

import { createContext, useContext, useState, useEffect } from "react";
import type { ReactNode } from "react";
import api from "./api";

interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount, try to restore the session from the stored token
  useEffect(() => {
    const token = localStorage.getItem("token");
    let interval: ReturnType<typeof setInterval>;

    if (token) {
      api.me()
        .then((u: User) => {
          setUser(u);
          // Silent refresh interval every 1 hour (3,600,000 ms)
          interval = setInterval(() => {
            api.refreshToken().then((res: any) => {
              localStorage.setItem("token", res.access_token);
            }).catch(() => {
              logout();
            });
          }, 3600000);
        })
        .catch(() => localStorage.removeItem("token"))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }

    return () => clearInterval(interval);
  }, []);

  const login = async (username: string, password: string) => {
    const res = await api.login({ username, password });
    localStorage.setItem("token", res.access_token);
    setUser(res.user);
  };

  const register = async (username: string, email: string, password: string) => {
    await api.register({ username, email, password, role: "admin" });
    // Auto-login after registration
    await login(username, password);
  };

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

/** Custom hook — use this in any component to access auth state. */
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside <AuthProvider>");
  return ctx;
}
