import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import * as api from "../api/client";
import { ApiError } from "../api/client";
import type { SessionCheckResponse, SessionStatus, StudySessionDetail } from "../api/types";
import { formatClock } from "../utils/format";

const HEARTBEAT_INTERVAL_MS = 20_000; // must stay under the backend's grace window (default 45s)
const RING_CIRCUMFERENCE = 2 * Math.PI * 18;

export function ActiveSession() {
  const { id } = useParams<{ id: string }>();
  const sessionId = Number(id);
  const navigate = useNavigate();

  const [session, setSession] = useState<StudySessionDetail | null>(null);
  const [status, setStatus] = useState<SessionStatus>("active");
  const [displaySeconds, setDisplaySeconds] = useState(0);
  const [pendingCheck, setPendingCheck] = useState<SessionCheckResponse | null>(null);
  const [checkAnswer, setCheckAnswer] = useState("");
  const [checkSubmitting, setCheckSubmitting] = useState(false);
  const [showEndForm, setShowEndForm] = useState(false);
  const [summaryText, setSummaryText] = useState("");
  const [ending, setEnding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ringNow, setRingNow] = useState(Date.now());

  const baseline = useRef({ seconds: 0, at: Date.now() });

  const applyServerState = useCallback((accumulated_seconds: number, nextStatus: SessionStatus) => {
    baseline.current = { seconds: accumulated_seconds, at: Date.now() };
    setDisplaySeconds(accumulated_seconds);
    setStatus(nextStatus);
  }, []);

  // Initial load
  useEffect(() => {
    api
      .getSession(sessionId)
      .then((detail) => {
        setSession(detail);
        applyServerState(detail.accumulated_seconds, detail.status);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load this session."));
  }, [sessionId, applyServerState]);

  // Smooth client-side tick while active (server remains the source of truth on each heartbeat)
  useEffect(() => {
    if (status !== "active") return;
    const tick = setInterval(() => {
      const elapsed = (Date.now() - baseline.current.at) / 1000;
      setDisplaySeconds(Math.floor(baseline.current.seconds + elapsed));
    }, 1000);
    return () => clearInterval(tick);
  }, [status]);

  // Heartbeat loop
  useEffect(() => {
    if (status !== "active") return;

    let cancelled = false;
    async function beat() {
      try {
        const res = await api.sendHeartbeat(sessionId);
        if (cancelled) return;
        applyServerState(res.accumulated_seconds, res.status);
        setPendingCheck(res.pending_check);
        if (res.status === "flagged") {
          setError("This session was flagged for missed anti-cheat checks.");
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Lost connection to the server.");
      }
    }

    void beat();
    const interval = setInterval(beat, HEARTBEAT_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [status, sessionId, applyServerState]);

  // Countdown ring redraw
  useEffect(() => {
    if (!pendingCheck) return;
    const t = setInterval(() => setRingNow(Date.now()), 500);
    return () => clearInterval(t);
  }, [pendingCheck]);

  async function handlePause() {
    try {
      const res = await api.pauseSession(sessionId);
      applyServerState(res.accumulated_seconds, res.status);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't pause this session.");
    }
  }

  async function handleResume() {
    try {
      const res = await api.resumeSession(sessionId);
      applyServerState(res.accumulated_seconds, res.status);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't resume this session.");
    }
  }

  async function handleRespond() {
    if (!pendingCheck) return;
    const answer = pendingCheck.check_type === "attention" ? "ok" : checkAnswer.trim();
    if (!answer) return;
    setCheckSubmitting(true);
    try {
      await api.respondToCheck(sessionId, pendingCheck.id, answer);
      setPendingCheck(null);
      setCheckAnswer("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't submit your response.");
    } finally {
      setCheckSubmitting(false);
    }
  }

  async function handleEnd() {
    setEnding(true);
    setError(null);
    try {
      const detail = await api.endSession(sessionId, summaryText.trim());
      navigate(`/session/${sessionId}/complete`, { state: { detail } });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't end this session.");
      setEnding(false);
    }
  }

  if (!session) {
    return (
      <div className="app-shell">
        <div className="session-screen">
          <div className="app-column">
            {error ? <div className="banner banner-error">{error}</div> : <p className="text-soft">Loading…</p>}
          </div>
        </div>
      </div>
    );
  }

  let ringFraction = 0;
  if (pendingCheck) {
    const total = new Date(pendingCheck.expires_at).getTime() - new Date(pendingCheck.triggered_at).getTime();
    const remaining = new Date(pendingCheck.expires_at).getTime() - ringNow;
    ringFraction = Math.max(0, Math.min(1, remaining / total));
  }

  return (
    <div className="app-shell">
      <div className="session-screen" style={{ flex: 1, width: "100%" }}>
        <div className="session-vignette" />
        <div className="app-column">
          <div className="session-top">
            <span className="wordmark" style={{ fontSize: "1.05rem" }}>{session.subject_tag ?? "Untitled session"}</span>
            <span className={`pill status-${status}`}>
              <span className="dot" />
              {status === "active" ? "Recording" : status}
            </span>
          </div>

          {error && <div className="banner banner-error">{error}</div>}

          <div className="timer">{formatClock(displaySeconds)}</div>
          <p className="timer-caption">Verified minutes — server clock, not yours</p>

          {pendingCheck && status === "active" && (
            <div className="check-card">
              <div className="check-ring-row">
                <svg className="ring" viewBox="0 0 44 44">
                  <circle className="track" cx="22" cy="22" r="18" fill="none" strokeWidth="4" />
                  <circle
                    className="progress"
                    cx="22"
                    cy="22"
                    r="18"
                    fill="none"
                    strokeWidth="4"
                    strokeDasharray={RING_CIRCUMFERENCE}
                    strokeDashoffset={RING_CIRCUMFERENCE * (1 - ringFraction)}
                  />
                </svg>
                <div style={{ flex: 1 }}>
                  <p>{pendingCheck.prompt}</p>
                  {pendingCheck.check_type === "attention" ? (
                    <button className="btn btn-primary" disabled={checkSubmitting} onClick={() => void handleRespond()}>
                      I'm here
                    </button>
                  ) : (
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      <input
                        className="input"
                        value={checkAnswer}
                        onChange={(e) => setCheckAnswer(e.target.value)}
                        placeholder="Type your answer"
                        style={{ flex: 1 }}
                      />
                      <button className="btn btn-primary" disabled={checkSubmitting || !checkAnswer.trim()} onClick={() => void handleRespond()}>
                        Send
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {showEndForm ? (
            <div className="check-card">
              <p>What did you study? (required to close out the session)</p>
              <textarea
                className="input"
                value={summaryText}
                onChange={(e) => setSummaryText(e.target.value)}
                minLength={20}
                placeholder="e.g. Reviewed mitosis stages and did the end-of-chapter practice questions."
                style={{ marginBottom: "0.7rem" }}
              />
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => setShowEndForm(false)} disabled={ending}>
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  style={{ flex: 1 }}
                  disabled={ending || summaryText.trim().length < 20}
                  onClick={() => void handleEnd()}
                >
                  {ending ? "Ending…" : "Finish"}
                </button>
              </div>
            </div>
          ) : (
            <div className="session-controls">
              {status === "active" ? (
                <button className="btn btn-ghost" onClick={() => void handlePause()}>Pause</button>
              ) : status === "paused" ? (
                <button className="btn btn-ghost" onClick={() => void handleResume()}>Resume</button>
              ) : null}
              <button className="btn btn-danger" onClick={() => setShowEndForm(true)}>End session</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
