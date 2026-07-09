import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import * as api from "../api/client";
import { ApiError } from "../api/client";
import type { SubscriptionResponse } from "../api/types";
import { CheckIcon, FlagIcon } from "../components/icons";
import { formatWhen } from "../utils/format";

export function SubscribeCallback() {
  const [searchParams] = useSearchParams();
  const reference = searchParams.get("reference");

  const [result, setResult] = useState<SubscriptionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!reference) {
      setError("No payment reference found in the URL.");
      return;
    }
    api
      .verifySubscription(reference)
      .then(setResult)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't confirm this payment."));
  }, [reference]);

  const isActive = result?.status === "active";

  return (
    <div className="app-shell">
      <div className="app-column">
        {error && (
          <>
            <div className="banner banner-error" style={{ marginTop: "2rem" }}>{error}</div>
            <Link to="/profile" className="btn btn-primary btn-block">Back to profile</Link>
          </>
        )}

        {!error && !result && <p className="text-soft" style={{ marginTop: "2rem" }}>Confirming your payment…</p>}

        {!error && result && (
          <>
            <div
              className="complete-badge"
              style={!isActive ? { background: "color-mix(in srgb, var(--danger) 18%, transparent)", color: "var(--danger)" } : undefined}
            >
              {isActive ? <CheckIcon size={26} /> : <FlagIcon size={26} />}
            </div>
            <h2 style={{ textAlign: "center" }}>{isActive ? "You're subscribed" : "Payment didn't go through"}</h2>
            <p className="text-soft" style={{ textAlign: "center", marginBottom: "1.4rem" }}>
              {isActive
                ? `Active until ${result.expires_at ? formatWhen(result.expires_at) : ""}`
                : "No charge was made. You can try again from your profile."}
            </p>
            <Link to="/profile" className="btn btn-primary btn-block" style={{ marginTop: "auto" }}>
              Back to profile
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
