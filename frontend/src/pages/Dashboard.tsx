import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import * as api from "../api/client";
import { ApiError } from "../api/client";
import type { BalanceResponse, StudySessionResponse } from "../api/types";
import { isWithinLastDays } from "../utils/format";
import { DAILY_CAP_MINUTES, SUBJECTS, WEEKLY_CAP_MINUTES } from "../constants";
import { BottomNav } from "../components/BottomNav";
import { MenuSheet } from "../components/MenuSheet";
import { SessionListRow } from "../components/SessionListRow";
import { StartSessionSheet } from "../components/StartSessionSheet";
import { BellIcon, BookIcon, ChevronRightIcon, MenuIcon, SearchIcon, SlidersIcon } from "../components/icons";

export function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [sessions, setSessions] = useState<StudySessionResponse[] | null>(null);
  const [balance, setBalance] = useState<BalanceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [showPicker, setShowPicker] = useState(false);
  const [subject, setSubject] = useState("");
  const [showMenu, setShowMenu] = useState(false);
  const [showStartSheet, setShowStartSheet] = useState(false);

  useEffect(() => {
    api
      .listSessions()
      .then(setSessions)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load your sessions."));
    api.getBalance().then(setBalance).catch(() => {
      // Non-critical: leave the points card in its loading state rather than surfacing an error banner.
    });
  }, []);

  const openSession = useMemo(
    () => sessions?.find((s) => s.status === "active" || s.status === "paused") ?? null,
    [sessions]
  );

  const weeklyVerifiedMinutes = useMemo(() => {
    if (!sessions) return 0;
    return sessions
      .filter((s) => s.status === "completed" && s.ended_at && isWithinLastDays(s.ended_at, 7))
      .reduce((sum, s) => sum + s.verified_minutes, 0);
  }, [sessions]);

  const streakDays = useMemo(() => {
    if (!sessions) return 0;
    const completedDays = new Set(
      sessions
        .filter((s) => s.status === "completed" && s.ended_at)
        .map((s) => new Date(s.ended_at as string).toDateString())
    );
    let streak = 0;
    const cursor = new Date();
    while (completedDays.has(cursor.toDateString())) {
      streak += 1;
      cursor.setDate(cursor.getDate() - 1);
    }
    return streak;
  }, [sessions]);

  async function handleStart(tag?: string) {
    const finalTag = (tag ?? subject).trim();
    setStarting(true);
    setError(null);
    try {
      const session = await api.startSession(finalTag || null);
      navigate(`/session/${session.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start a session.");
      setStarting(false);
    }
  }

  const recent = sessions?.slice(0, 4) ?? [];

  return (
    <div className="app-shell">
      <div className="app-column has-nav">
        <div className="topbar">
          <button className="topbar-icon-btn" aria-label="Menu" onClick={() => setShowMenu(true)}>
            <MenuIcon size={18} />
          </button>
          <button className="topbar-icon-btn" aria-label="Notifications">
            <BellIcon size={18} />
          </button>
        </div>

        {showMenu && <MenuSheet onClose={() => setShowMenu(false)} />}
        {showStartSheet && <StartSessionSheet onClose={() => setShowStartSheet(false)} />}

        <h1 className="display-heading">
          Hello, {user?.username}
          <br />
          Ready to focus?
        </h1>

        {error && <div className="banner banner-error" style={{ marginTop: "1rem" }}>{error}</div>}

        <form
          className="search-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (!starting && !openSession) void handleStart();
          }}
        >
          <div className="search-input-wrap">
            <SearchIcon size={17} />
            <input
              type="search"
              enterKeyHint="go"
              placeholder={openSession ? "Finish your current session first" : "What are you studying today?"}
              value={subject}
              disabled={!!openSession}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="search-filter-btn"
            aria-label="Subject shortcuts"
            disabled={!!openSession}
            onClick={() => setShowPicker((v) => !v)}
          >
            <SlidersIcon size={18} />
          </button>
        </form>

        {showPicker && !openSession && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginBottom: "1.3rem" }}>
            {SUBJECTS.map((s) => (
              <button key={s} type="button" className="chip" disabled={starting} onClick={() => void handleStart(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        {!openSession && (
          <button
            className="list-row"
            style={{ marginBottom: "1.3rem" }}
            onClick={() => setShowStartSheet(true)}
          >
            <span className="icon-tile lime" style={{ width: 44, height: 44 }}>
              <BookIcon size={20} />
            </span>
            <span className="list-row-main">
              <div className="list-row-title">Start with lecture material</div>
              <div className="list-row-sub">Upload notes, get quizzed when you're done</div>
            </span>
            <ChevronRightIcon size={18} className="list-row-chevron" />
          </button>
        )}

        <div className="stat-row" style={{ marginBottom: "1rem" }}>
          <div className="card">
            <p className="stat-label">Streak</p>
            <p className="stat-value">
              {streakDays} {streakDays === 1 ? "day" : "days"}
            </p>
          </div>
          <button
            className="card"
            style={{ textAlign: "left", cursor: "pointer", font: "inherit", color: "inherit" }}
            onClick={() => navigate("/profile")}
          >
            <p className="stat-label">Knowledge Points</p>
            <p className="stat-value accent">{balance ? balance.points.toLocaleString() : "···"} <span style={{ fontSize: "0.85rem" }}>KP</span></p>
          </button>
        </div>

        <div className="card" style={{ marginBottom: "1.4rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem", color: "var(--text-soft)", marginBottom: "0.5rem" }}>
            <span>Weekly reward budget</span>
            <span className="mono">{weeklyVerifiedMinutes} / {WEEKLY_CAP_MINUTES} min</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${Math.min(100, (weeklyVerifiedMinutes / WEEKLY_CAP_MINUTES) * 100)}%` }} />
          </div>
        </div>

        {openSession && (
          <button className="feature-card" onClick={() => navigate(`/session/${openSession.id}`)}>
            <div>
              <p className="feature-card-title">{openSession.subject_tag ?? "Untitled session"}</p>
              <p className="feature-card-sub">Tap to {openSession.status === "paused" ? "resume" : "open"}</p>
            </div>
            <div className="feature-card-progress">
              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{ width: `${Math.min(100, (openSession.accumulated_seconds / 60 / DAILY_CAP_MINUTES) * 100)}%` }}
                />
              </div>
            </div>
            <div className="feature-card-foot">
              <span className={`pill status-${openSession.status}`}>
                <span className="dot" />
                {openSession.status === "paused" ? "Paused" : "In progress"}
              </span>
              <span className="feature-card-percent">{Math.round(openSession.accumulated_seconds / 60)} min</span>
            </div>
          </button>
        )}

        <div className="section-header">
          <h3>Recent sessions</h3>
          <a href="#" onClick={(e) => { e.preventDefault(); navigate("/history"); }} style={{ fontSize: "0.8rem" }}>
            See all
          </a>
        </div>

        {sessions === null && <p className="text-soft" style={{ fontSize: "0.85rem" }}>Loading…</p>}
        {sessions?.length === 0 && (
          <p className="text-soft" style={{ fontSize: "0.85rem" }}>No sessions yet — search a subject above to start your first one.</p>
        )}
        {recent.map((s) => (
          <SessionListRow key={s.id} session={s} />
        ))}
      </div>
      <BottomNav />
    </div>
  );
}
