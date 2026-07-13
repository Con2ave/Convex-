import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../api/client";

export function SignIn() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signIn(username, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="app-shell">
      <div className="app-column">
        <div className="wordmark" style={{ margin: "2.4rem 0 0.3rem" }}>
          ConVex
        </div>
        <p className="text-soft" style={{ margin: "0 0 2rem", fontSize: "0.85rem" }}>
          Study time, verified and rewarded.
        </p>

        <h2 style={{ fontSize: "1.3rem", marginBottom: "1.3rem" }}>Welcome back</h2>

        {error && <div className="banner banner-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="username">Username or email</label>
            <input
              id="username"
              className="input"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              className="input"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button
            className="btn btn-primary btn-block"
            type="submit"
            disabled={submitting}
            style={{ marginTop: "0.8rem" }}
          >
            {submitting ? "Signing in…" : "Continue"}
          </button>
        </form>

        <p className="text-soft" style={{ marginTop: "auto", textAlign: "center", fontSize: "0.8rem", paddingTop: "2rem" }}>
          New here? <Link to="/register">Create account</Link>
        </p>
      </div>
    </div>
  );
}
