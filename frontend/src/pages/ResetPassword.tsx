import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import * as api from "../api/client";
import { ApiError } from "../api/client";

export function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const navigate = useNavigate();

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.resetPassword({
        token,
        new_password: newPassword,
        new_password_confirm: confirmPassword,
      });
      navigate("/sign-in", { replace: true, state: { passwordReset: true } });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div className="app-shell">
        <div className="app-column">
          <div className="banner banner-error" style={{ marginTop: "2rem" }}>
            This reset link is missing its token. Request a new one.
          </div>
          <Link to="/forgot-password" className="btn btn-primary btn-block" style={{ marginTop: "1rem" }}>
            Request a new link
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <div className="app-column">
        <div className="wordmark" style={{ margin: "2.4rem 0 0.3rem" }}>
          ConVex
        </div>
        <h2 style={{ fontSize: "1.3rem", marginBottom: "1.3rem" }}>Choose a new password</h2>

        {error && <div className="banner banner-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="new_password">New password</label>
            <input
              id="new_password"
              className="input"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            <span className="text-soft" style={{ fontSize: "0.72rem" }}>
              8+ characters, with an uppercase letter, a number, and a symbol (@$!%*?&amp;).
            </span>
          </div>
          <div className="field">
            <label htmlFor="confirm_password">Confirm new password</label>
            <input
              id="confirm_password"
              className="input"
              type="password"
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </div>
          <button
            className="btn btn-primary btn-block"
            type="submit"
            disabled={submitting}
            style={{ marginTop: "0.8rem" }}
          >
            {submitting ? "Resetting…" : "Reset password"}
          </button>
        </form>

        <p className="text-soft" style={{ marginTop: "auto", textAlign: "center", fontSize: "0.8rem", paddingTop: "2rem" }}>
          <Link to="/sign-in">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}
