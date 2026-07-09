import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import * as api from "../api/client";
import { ApiError } from "../api/client";
import type {
  BalanceResponse,
  LedgerEntryResponse,
  MobileNetwork,
  RedemptionTier,
  SubscriptionStatus,
} from "../api/types";
import { BottomNav } from "../components/BottomNav";
import { ChevronRightIcon, LogoutIcon, ProfileIcon } from "../components/icons";
import { formatLedgerReason, formatWhen } from "../utils/format";

export function Profile() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [balance, setBalance] = useState<BalanceResponse | null>(null);
  const [ledger, setLedger] = useState<LedgerEntryResponse[] | null>(null);
  const [tiers, setTiers] = useState<RedemptionTier[] | null>(null);

  const [showRedeem, setShowRedeem] = useState(false);
  const [showSubscribePrompt, setShowSubscribePrompt] = useState(false);
  const [selectedTier, setSelectedTier] = useState<RedemptionTier | null>(null);
  const [network, setNetwork] = useState<MobileNetwork | null>(null);
  const [phone, setPhone] = useState("");
  const [redeemError, setRedeemError] = useState<string | null>(null);
  const [redeemSuccess, setRedeemSuccess] = useState<string | null>(null);
  const [redeeming, setRedeeming] = useState(false);

  const [subStatus, setSubStatus] = useState<SubscriptionStatus | null>(null);

  function refresh() {
    api.getBalance().then(setBalance).catch(() => undefined);
    api.getLedger().then(setLedger).catch(() => undefined);
    api.getSubscriptionStatus().then(setSubStatus).catch(() => undefined);
  }

  useEffect(refresh, []);
  useEffect(() => {
    api.getRedemptionTiers().then(setTiers).catch(() => undefined);
  }, []);

  const canRedeem = user?.role === "admin" || subStatus?.is_active === true;

  function handleRedeemClick() {
    if (!canRedeem) {
      setShowRedeem(false);
      setShowSubscribePrompt((v) => !v);
      return;
    }
    setShowSubscribePrompt(false);
    setShowRedeem((v) => !v);
  }

  async function handleRedeem(e: FormEvent) {
    e.preventDefault();
    setRedeemError(null);
    setRedeemSuccess(null);

    if (!selectedTier) {
      setRedeemError("Choose an amount.");
      return;
    }
    if (!network) {
      setRedeemError("Choose which network the number is on.");
      return;
    }

    setRedeeming(true);
    try {
      const redemption = await api.redeemPoints({
        ghs_amount: selectedTier.ghs_amount,
        recipient_phone: phone.trim(),
        network,
      });
      setRedeemSuccess(`GHS ${redemption.ghs_amount} sent to ${redemption.recipient_phone} via Mobile Money.`);
      setSelectedTier(null);
      setNetwork(null);
      setPhone("");
      setShowRedeem(false);
      refresh();
    } catch (err) {
      setRedeemError(err instanceof ApiError ? err.message : "Couldn't process this redemption.");
    } finally {
      setRedeeming(false);
    }
  }

  return (
    <div className="app-shell">
      <div className="app-column has-nav">
        <h1 className="display-heading" style={{ fontSize: "1.7rem", marginBottom: "1.4rem" }}>
          Profile
        </h1>

        <div className="card" style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.2rem" }}>
          <span className="icon-tile lime" style={{ width: 56, height: 56 }}>
            <ProfileIcon size={26} />
          </span>
          <div>
            <p style={{ fontWeight: 800, fontSize: "1.05rem", margin: 0 }}>{user?.username}</p>
            <p className="text-soft" style={{ fontSize: "0.82rem", margin: "0.15rem 0 0" }}>{user?.email}</p>
          </div>
        </div>

        <button
          className="list-row"
          style={{ marginBottom: "1.2rem", padding: "1rem 1.1rem" }}
          onClick={() => navigate("/subscribe")}
        >
          <span className="list-row-main">
            <div className="list-row-title">Subscription</div>
            <div style={{ marginTop: "0.35rem" }}>
              {subStatus?.is_active ? (
                <span className="pill status-completed">
                  <span className="dot" />
                  Active until {subStatus.expires_at ? formatWhen(subStatus.expires_at) : ""}
                </span>
              ) : (
                <span className="pill status-paused">
                  <span className="dot" />
                  Free
                </span>
              )}
            </div>
          </span>
          <ChevronRightIcon size={18} className="list-row-chevron" />
        </button>

        <div className="feature-card" style={{ marginBottom: "1.2rem" }}>
          <div>
            <p className="feature-card-sub" style={{ marginBottom: "0.2rem" }}>Knowledge Points</p>
            <p className="feature-card-title" style={{ fontSize: "2rem" }}>
              {balance ? balance.points.toLocaleString() : "···"} <span style={{ fontSize: "1rem", fontWeight: 700 }}>KP</span>
            </p>
          </div>
          <div className="feature-card-foot">
            <span className="text-soft" style={{ fontSize: "0.75rem" }}>
              {canRedeem ? "Trade KP for Mobile Money" : "Subscribe to trade KP for Mobile Money"}
            </span>
            <button className="btn btn-primary" style={{ padding: "0.55rem 1rem" }} onClick={handleRedeemClick}>
              Redeem
            </button>
          </div>
        </div>

        {redeemSuccess && <div className="banner banner-info">{redeemSuccess}</div>}

        {showSubscribePrompt && (
          <div className="card" style={{ marginBottom: "1.2rem" }}>
            <p style={{ fontWeight: 800, marginBottom: "0.3rem" }}>Subscribe to redeem your KP</p>
            <p className="text-soft" style={{ fontSize: "0.85rem", marginBottom: "1rem" }}>
              Studying and earning Knowledge Points is always free. Subscribing unlocks cashing them
              out for Mobile Money — your balance is safe and waiting either way.
            </p>
            <button className="btn btn-dark btn-block" onClick={() => navigate("/subscribe")}>
              View plans
            </button>
          </div>
        )}

        {showRedeem && (
          <form className="card" style={{ marginBottom: "1.2rem" }} onSubmit={handleRedeem}>
            <p className="stat-label" style={{ marginBottom: "0.7rem" }}>Redeem for Mobile Money</p>
            {redeemError && <div className="banner banner-error">{redeemError}</div>}

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem", marginBottom: "1rem" }}>
              {tiers?.map((tier) => {
                const affordable = !balance || balance.points >= tier.kp_cost;
                const isSelected = selectedTier?.ghs_amount === tier.ghs_amount;
                return (
                  <button
                    type="button"
                    key={tier.ghs_amount}
                    className={`chip ${isSelected ? "is-selected" : ""}`}
                    style={{
                      padding: "0.8rem",
                      textAlign: "center",
                      opacity: affordable ? 1 : 0.45,
                      cursor: affordable ? "pointer" : "not-allowed",
                    }}
                    disabled={!affordable}
                    onClick={() => setSelectedTier(tier)}
                  >
                    <div style={{ fontWeight: 800, fontSize: "1.05rem" }}>GHS {tier.ghs_amount}</div>
                    <div style={{ fontSize: "0.72rem" }}>{tier.kp_cost.toLocaleString()} KP</div>
                  </button>
                );
              })}
              {tiers === null && <p className="text-soft" style={{ fontSize: "0.85rem" }}>Loading tiers…</p>}
            </div>

            <div className="field">
              <label>Network</label>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                {([
                  { value: "mtn", label: "MTN" },
                  { value: "telecel", label: "Telecel" },
                  { value: "airteltigo", label: "AirtelTigo" },
                ] as { value: MobileNetwork; label: string }[]).map((option) => (
                  <button
                    type="button"
                    key={option.value}
                    className={`chip ${network === option.value ? "is-selected" : ""}`}
                    style={{ flex: 1, textAlign: "center" }}
                    onClick={() => setNetwork(option.value)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="field">
              <label htmlFor="redeem-phone">MoMo number to send to</label>
              <input
                id="redeem-phone"
                className="input"
                type="tel"
                placeholder="024 XXX XXXX"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
              />
            </div>
            <button className="btn btn-dark btn-block" type="submit" disabled={redeeming || !selectedTier || !network}>
              {redeeming ? "Processing…" : selectedTier ? `Redeem ${selectedTier.kp_cost.toLocaleString()} KP` : "Choose an amount"}
            </button>
          </form>
        )}

        <p className="stat-label" style={{ marginBottom: "0.6rem" }}>Activity</p>
        {ledger === null && <p className="text-soft" style={{ fontSize: "0.85rem" }}>Loading…</p>}
        {ledger?.length === 0 && (
          <p className="text-soft" style={{ fontSize: "0.85rem", marginBottom: "1.2rem" }}>
            No activity yet — finish a study session to earn your first Knowledge Points.
          </p>
        )}
        {ledger && ledger.length > 0 && (
          <div className="card" style={{ marginBottom: "1.2rem", padding: "0.4rem 1.1rem" }}>
            {ledger.map((entry, i) => (
              <div
                key={entry.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "0.7rem 0",
                  borderTop: i === 0 ? "none" : "1px solid var(--border)",
                }}
              >
                <div>
                  <div style={{ fontSize: "0.88rem", fontWeight: 700 }}>{formatLedgerReason(entry.reason)}</div>
                  <div className="text-soft" style={{ fontSize: "0.74rem" }}>{formatWhen(entry.created_at)}</div>
                </div>
                <div
                  className="mono"
                  style={{ fontWeight: 800, color: entry.points >= 0 ? "color-mix(in srgb, var(--lime) 55%, var(--text) 45%)" : "var(--danger)" }}
                >
                  {entry.points >= 0 ? "+" : ""}
                  {entry.points} KP
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="card" style={{ marginBottom: "1.2rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "0.4rem 0" }}>
            <span className="text-soft" style={{ fontSize: "0.85rem" }}>Role</span>
            <span style={{ fontWeight: 700, fontSize: "0.85rem", textTransform: "capitalize" }}>{user?.role}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "0.4rem 0" }}>
            <span className="text-soft" style={{ fontSize: "0.85rem" }}>Email verified</span>
            <span style={{ fontWeight: 700, fontSize: "0.85rem" }}>{user?.is_verified ? "Yes" : "Not yet"}</span>
          </div>
        </div>

        <button className="btn btn-ghost btn-block" style={{ marginTop: "auto" }} onClick={() => void signOut()}>
          <LogoutIcon size={18} />
          Sign out
        </button>
      </div>
      <BottomNav />
    </div>
  );
}
