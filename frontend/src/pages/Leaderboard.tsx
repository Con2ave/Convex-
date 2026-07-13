import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import * as api from "../api/client";
import type { PointsLeaderboardEntry, StreakLeaderboardEntry } from "../api/types";
import { BottomNav } from "../components/BottomNav";

type Tab = "points" | "streaks";

export function Leaderboard() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("points");
  const [points, setPoints] = useState<PointsLeaderboardEntry[] | null>(null);
  const [streaks, setStreaks] = useState<StreakLeaderboardEntry[] | null>(null);

  useEffect(() => {
    api.getPointsLeaderboard().then(setPoints).catch(() => setPoints([]));
    api.getStreakLeaderboard().then(setStreaks).catch(() => setStreaks([]));
  }, []);

  const rows =
    tab === "points"
      ? (points ?? []).map((e) => ({ username: e.username, value: `${e.points.toLocaleString()} KP` }))
      : (streaks ?? []).map((e) => ({
          username: e.username,
          value: `${e.streak_days} ${e.streak_days === 1 ? "day" : "days"}`,
        }));
  const loading = tab === "points" ? points === null : streaks === null;

  return (
    <div className="app-shell">
      <div className="app-column has-nav">
        <h1 className="display-heading" style={{ fontSize: "1.7rem", marginBottom: "1.4rem" }}>
          Leaderboard
        </h1>

        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.2rem" }}>
          <button
            type="button"
            className={`chip ${tab === "points" ? "is-selected" : ""}`}
            style={{ flex: 1, textAlign: "center" }}
            onClick={() => setTab("points")}
          >
            Top Points
          </button>
          <button
            type="button"
            className={`chip ${tab === "streaks" ? "is-selected" : ""}`}
            style={{ flex: 1, textAlign: "center" }}
            onClick={() => setTab("streaks")}
          >
            Top Streaks
          </button>
        </div>

        {loading && <p className="text-soft" style={{ fontSize: "0.85rem" }}>Loading…</p>}
        {!loading && rows.length === 0 && (
          <p className="text-soft" style={{ fontSize: "0.85rem" }}>No one's on the board yet — be the first.</p>
        )}
        {!loading && rows.length > 0 && (
          <div className="card" style={{ padding: "0.4rem 1.1rem" }}>
            {rows.map((row, i) => (
              <div
                key={row.username}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "0.7rem 0",
                  borderTop: i === 0 ? "none" : "1px solid var(--border)",
                  fontWeight: row.username === user?.username ? 800 : 400,
                }}
              >
                <span>
                  <span className="text-soft mono" style={{ marginRight: "0.6rem" }}>{i + 1}</span>
                  {row.username}
                </span>
                <span className="mono">{row.value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <BottomNav />
    </div>
  );
}
