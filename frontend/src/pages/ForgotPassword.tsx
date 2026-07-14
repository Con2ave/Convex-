import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import * as api from "../api/client";
import { ApiError } from "../api/client";

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.forgotPassword(email.trim());
      setSent(true);
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
        <h2 style={{ fontSize: "1.3rem", marginBottom: "0.5rem" }}>Reset your password</h2>
        <p className="text-soft" style={{ marginBottom: "1.5rem", fontSize: "0.85rem" }}>
          Enter the email on your account and we'll send you a link to reset your password.
        </p>

        {error && <div className="banner banner-error">{error}</div>}

        {sent ? (
          <div className="banner banner-info">
            If that email is registered, a reset link is on its way. Check your inbox.
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                className="input"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <button
              className="btn btn-primary btn-block"
              type="submit"
              disabled={submitting}
              style={{ marginTop: "0.8rem" }}
            >
              {submitting ? "Sending…" : "Send reset link"}
            </button>
          </form>
        )}

        <p className="text-soft" style={{ marginTop: "auto", textAlign: "center", fontSize: "0.8rem", paddingTop: "2rem" }}>
          <Link to="/sign-in">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}
