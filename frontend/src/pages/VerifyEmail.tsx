import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import * as api from "../api/client";
import { ApiError } from "../api/client";
import { CheckIcon, FlagIcon } from "../components/icons";

export function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [status, setStatus] = useState<"verifying" | "success" | "error">("verifying");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setError("This verification link is missing its token.");
      return;
    }
    api
      .verifyEmail(token)
      .then(() => setStatus("success"))
      .catch((err) => {
        setStatus("error");
        setError(err instanceof ApiError ? err.message : "Couldn't verify this email address.");
      });
  }, [token]);

  return (
    <div className="app-shell">
      <div className="app-column" style={{ justifyContent: "center", alignItems: "center", textAlign: "center" }}>
        {status === "verifying" && <p className="text-soft">Verifying your email…</p>}

        {status === "success" && (
          <>
            <div className="complete-badge">
              <CheckIcon size={26} />
            </div>
            <h2>Email verified</h2>
            <p className="text-soft" style={{ marginBottom: "1.4rem" }}>Your email address is confirmed.</p>
            <Link to="/sign-in" className="btn btn-primary btn-block">Sign in</Link>
          </>
        )}

        {status === "error" && (
          <>
            <div
              className="complete-badge"
              style={{ background: "color-mix(in srgb, var(--danger) 18%, transparent)", color: "var(--danger)" }}
            >
              <FlagIcon size={26} />
            </div>
            <h2>Verification failed</h2>
            <p className="text-soft" style={{ marginBottom: "1.4rem" }}>{error}</p>
            <Link to="/sign-in" className="btn btn-primary btn-block">Back to sign in</Link>
          </>
        )}
      </div>
    </div>
  );
}
