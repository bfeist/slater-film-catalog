import { useState, useRef, useEffect, type FormEvent, type JSX } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";
import type { UserRole } from "../lib/AuthContext";
import styles from "./LoginPage.module.css";

export default function LoginPage(): JSX.Element {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const usernameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    usernameRef.current?.focus();
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password) return;

    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ error: "Login failed" }));
        setError((body as { error?: string }).error ?? "Login failed");
        return;
      }

      const data = (await res.json()) as { token: string; username: string; role: UserRole };
      login(data.token, data.username, data.role);
      navigate("/", { replace: true });
    } catch {
      setError("Unable to connect to server");
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = username.trim().length > 0 && password.length > 0 && !submitting;

  return (
    <div className={styles.loginPage}>
      <div className={styles.card}>
        <h1 className={styles.heading}>NASA Slater Film Catalog</h1>
        <p className={styles.subtitle}>Sign in to access the catalog</p>
        <form onSubmit={handleSubmit} className={styles.form}>
          <label className={styles.label} htmlFor="login-username">
            Username
          </label>
          <input
            id="login-username"
            ref={usernameRef}
            type="text"
            className={styles.input}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            placeholder="Enter username…"
          />
          <label className={styles.label} htmlFor="login-password">
            Password
          </label>
          <input
            id="login-password"
            type="password"
            className={styles.input}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            placeholder="Enter password…"
          />
          {error && <div className={styles.errorMsg}>{error}</div>}
          <button type="submit" className={styles.submitBtn} disabled={!canSubmit}>
            {submitting ? "Signing in…" : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
