import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import * as api from "../api/client";
import { ApiError } from "../api/client";
import type { SubscriptionPlan, SubscriptionPlanName, SubscriptionResponse, SubscriptionStatus } from "../api/types";
import { ChevronLeftIcon, LockIcon } from "../components/icons";
import { formatWhen } from "../utils/format";

const PLAN_LABELS: Record<SubscriptionPlanName, string> = {
  monthly: "1 month",
  quarterly: "3 months",
  annual: "1 year",
};

const PLAN_BLURBS: Record<SubscriptionPlanName, string> = {
  monthly: "Pay as you go.",
  quarterly: "Save vs. paying monthly.",
  annual: "Best value, one payment a year.",
};

const STATUS_LABELS: Record<SubscriptionResponse["status"], string> = {
  active: "Active",
  pending: "Pending",
  failed: "Didn't go through",
};

export function Subscribe() {
  const navigate = useNavigate();
  const location = useLocation();
  const onboarding = Boolean((location.state as { onboarding?: boolean } | null)?.onboarding);

  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [plans, setPlans] = useState<SubscriptionPlan[] | null>(null);
  const [history, setHistory] = useState<SubscriptionResponse[] | null>(null);
  const [subError, setSubError] = useState<string | null>(null);
  const [subscribing, setSubscribing] = useState<SubscriptionPlanName | null>(null);

  useEffect(() => {
    api.getSubscriptionStatus().then(setStatus).catch(() => undefined);
    api.getSubscriptionPlans().then(setPlans).catch(() => undefined);
    api.getSubscriptionHistory().then(setHistory).catch(() => undefined);
  }, []);

  async function handleSubscribe(plan: SubscriptionPlanName) {
    setSubError(null);
    setSubscribing(plan);

    // iOS Safari blocks window.location changes that happen after an awaited network call -
    // it no longer treats them as a direct result of the tap. Opening the destination tab
    // synchronously, right now, then pointing it at the checkout URL once we have it, sidesteps
    // that (the tab handle itself was opened as a trusted direct user action).
    const checkoutTab = window.open("about:blank", "_blank");

    try {
      const { authorization_url } = await api.initializeSubscription(plan);
      if (checkoutTab) {
        checkoutTab.location.href = authorization_url;
      } else {
        // Popup got blocked anyway (e.g. user has strict pop-up settings) - fall back to an
        // in-place redirect, which at least works on browsers that don't have this quirk.
        window.location.href = authorization_url;
      }
      setSubscribing(null);
    } catch (err) {
      checkoutTab?.close();
      setSubError(err instanceof ApiError ? err.message : "Couldn't start checkout.");
      setSubscribing(null);
    }
  }

  return (
    <div className="app-shell">
      <div className="app-column">
        <div className="topbar" style={{ marginBottom: "0.6rem" }}>
          {onboarding ? (
            <span />
          ) : (
            <button className="topbar-icon-btn" aria-label="Back" onClick={() => navigate(-1)}>
              <ChevronLeftIcon size={18} />
            </button>
          )}
          {onboarding && (
            <button className="btn btn-ghost" style={{ padding: "0.5rem 0.9rem" }} onClick={() => navigate("/")}>
              Skip for now
            </button>
          )}
        </div>

        <h1 className="display-heading" style={{ fontSize: "1.7rem", marginBottom: "0.4rem" }}>
          {onboarding ? "Welcome to ConVex" : "Subscription"}
        </h1>
        <p className="text-soft" style={{ fontSize: "0.85rem", marginBottom: "1.4rem" }}>
          {onboarding
            ? "Studying and earning Knowledge Points is always free. Subscribe now to also cash them out for Mobile Money — or skip and subscribe anytime from your profile."
            : "Subscribing lets you cash your Knowledge Points out for Mobile Money."}
        </p>

        <div className="card" style={{ display: "flex", alignItems: "center", gap: "0.9rem", marginBottom: "1.4rem" }}>
          <span className={`icon-tile ${status?.is_active ? "lime" : ""}`} style={{ width: 48, height: 48 }}>
            <LockIcon size={20} />
          </span>
          <div>
            {status === null && <p className="text-soft" style={{ fontSize: "0.85rem", margin: 0 }}>Loading…</p>}
            {status?.is_active ? (
              <>
                <p style={{ fontWeight: 800, margin: 0 }}>You're subscribed</p>
                <p className="text-soft" style={{ fontSize: "0.8rem", margin: "0.15rem 0 0" }}>
                  Active until {status.expires_at ? formatWhen(status.expires_at) : ""}
                </p>
              </>
            ) : status ? (
              <>
                <p style={{ fontWeight: 800, margin: 0 }}>Not subscribed</p>
                <p className="text-soft" style={{ fontSize: "0.8rem", margin: "0.15rem 0 0" }}>
                  Choose a plan below to unlock cash redemptions.
                </p>
              </>
            ) : null}
          </div>
        </div>

        {subError && <div className="banner banner-error" style={{ marginBottom: "1rem" }}>{subError}</div>}

        <p className="stat-label" style={{ marginBottom: "0.6rem" }}>
          {status?.is_active ? "Extend your subscription" : "Choose a plan"}
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", marginBottom: "1.6rem" }}>
          {plans?.map((p) => (
            <button
              key={p.plan}
              type="button"
              className="list-row"
              disabled={subscribing !== null}
              onClick={() => void handleSubscribe(p.plan)}
              style={{ alignItems: "center", padding: "0.9rem 1rem" }}
            >
              <span className="list-row-main">
                <div className="list-row-title">{PLAN_LABELS[p.plan]}</div>
                <div className="list-row-sub">{PLAN_BLURBS[p.plan]}</div>
              </span>
              <span className="mono" style={{ fontWeight: 800, fontSize: "1.05rem" }}>
                {subscribing === p.plan ? "…" : `GHS ${p.ghs_amount}`}
              </span>
            </button>
          ))}
          {plans === null && <p className="text-soft" style={{ fontSize: "0.85rem" }}>Loading plans…</p>}
        </div>

        {onboarding && (
          <button
            type="button"
            className="btn btn-ghost btn-block"
            style={{ marginBottom: "1.2rem" }}
            onClick={() => navigate("/")}
          >
            Skip for now, take me to the app
          </button>
        )}

        {!onboarding && (
          <>
            <p className="stat-label" style={{ marginBottom: "0.6rem" }}>Payment history</p>
            {history === null && <p className="text-soft" style={{ fontSize: "0.85rem" }}>Loading…</p>}
            {history?.length === 0 && (
              <p className="text-soft" style={{ fontSize: "0.85rem", marginBottom: "1.2rem" }}>
                No payments yet.
              </p>
            )}
          </>
        )}
        {!onboarding && history && history.length > 0 && (
          <div className="card" style={{ marginBottom: "1.2rem", padding: "0.4rem 1.1rem" }}>
            {history.map((h, i) => (
              <div
                key={h.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "0.7rem 0",
                  borderTop: i === 0 ? "none" : "1px solid var(--border)",
                }}
              >
                <div>
                  <div style={{ fontSize: "0.88rem", fontWeight: 700 }}>
                    {PLAN_LABELS[h.plan as SubscriptionPlanName] ?? h.plan} · GHS {h.ghs_amount}
                  </div>
                  <div className="text-soft" style={{ fontSize: "0.74rem" }}>{formatWhen(h.created_at)}</div>
                </div>
                <span className={`pill status-${h.status === "active" ? "completed" : h.status === "pending" ? "paused" : "flagged"}`}>
                  <span className="dot" />
                  {STATUS_LABELS[h.status]}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
