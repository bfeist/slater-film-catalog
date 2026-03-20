import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

export type UserRole = "full" | "guest";

interface AuthContextValue {
  isAuthenticated: boolean;
  /** Increments on every login/logout so consumers can re-fetch. */
  authVersion: number;
  username: string | null;
  role: UserRole | null;
  login: (token: string, username: string, role: UserRole) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  isAuthenticated: false,
  authVersion: 0,
  username: null,
  role: null,
  login: () => {},
  logout: () => {},
});

function getStoredToken(): string | null {
  try {
    return globalThis.sessionStorage?.getItem("authToken") ?? null;
  } catch {
    return null;
  }
}

function getStoredUsername(): string | null {
  try {
    return globalThis.sessionStorage?.getItem("authUsername") ?? null;
  } catch {
    return null;
  }
}

function getStoredRole(): UserRole | null {
  try {
    const r = globalThis.sessionStorage?.getItem("authRole") ?? null;
    return r === "full" || r === "guest" ? r : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }): ReactNode {
  const [isAuthenticated, setIsAuthenticated] = useState(() => getStoredToken() !== null);
  const [authVersion, setAuthVersion] = useState(0);
  const [username, setUsername] = useState<string | null>(() => getStoredUsername());
  const [role, setRole] = useState<UserRole | null>(() => getStoredRole());

  const login = useCallback((token: string, user: string, userRole: UserRole) => {
    try {
      sessionStorage.setItem("authToken", token);
      sessionStorage.setItem("authUsername", user);
      sessionStorage.setItem("authRole", userRole);
    } catch {
      /* ignore */
    }
    setIsAuthenticated(true);
    setUsername(user);
    setRole(userRole);
    setAuthVersion((v) => v + 1);
  }, []);

  const logout = useCallback(() => {
    // Fire and forget the server-side logout
    try {
      const token = sessionStorage.getItem("authToken");
      if (token) {
        fetch("/api/auth/logout", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }).catch(() => {});
      }
      sessionStorage.removeItem("authToken");
      sessionStorage.removeItem("authUsername");
      sessionStorage.removeItem("authRole");
    } catch {
      /* ignore */
    }
    setIsAuthenticated(false);
    setUsername(null);
    setRole(null);
    setAuthVersion((v) => v + 1);
  }, []);

  return (
    <AuthContext value={{ isAuthenticated, authVersion, username, role, login, logout }}>
      {children}
    </AuthContext>
  );
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
