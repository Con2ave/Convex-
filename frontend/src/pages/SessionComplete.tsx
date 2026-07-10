import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import * as api from "../api/client";
import { ApiError } from "../api/client";
import type { StudySessionDetail } from "../api/types";
import { CheckIcon, FlagIcon } from "../components/icons";

export function SessionComplete() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const stateDetail = (location.state as { detail?: StudySessionDetail } | null)?.detail;

  const [detail, setDetail] = useState<StudySessionDetail | null>(stateDetail ?? null);
  const [error, setError] = useState<string | null>(null);
  const [kpEarned, setKpEarned] = useState<number | null>(null);

  useEffect(() => {
    if (stateDetail) return;
    api
      .getSession(Number(id))
      .then(setDetail)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load this session."));
  }, [id, stateDetail]);

  useEffect(() => {
    // KP earned isn't returned by the end-session response - the formula (study blocks +
    // bonuses x streak multiplier) lives entirely server-side, so look up the exact ledger
    // entry this session produced rather than guess at it client-side.
    api
      .getLedger()
      .then((entries) => {
        const match = entries.find((e) => e.session_id === Number(id) && e.reason === "session_verified");
        setKpEarned(match?.points ?? 0);
      })
      .catch(() => setKpEarned(null));
  }, [id]);

  if (error) {
    return (
      <div className="app-shell">
        <div className="app-column">
          <div className="banner banner-error">{error}</div>
          <Link to="/" className="btn btn-primary btn-block">Back to home</Link>
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="app-shell">
        <div className="app-column">
          <p className="text-soft">Loading…</p>
        </div>
      </div>
    );
  }

  const isFlagged = detail.status === "flagged";
  const passedChecks = detail.checks.filter((c) => c.passed).length;
  const totalChecks = detail.checks.length;

  return (
    <div className="app-shell">
      <div className="app-column">
        <div
          className="complete-badge"
          style={
            isFlagged
              ? { background: "color-mix(in srgb, var(--danger) 18%, transparent)", color: "var(--danger)" }
              : undefined
          }
        >
          {isFlagged ? <FlagIcon size={26} /> : <CheckIcon size={26} />}
        </div>

        <h2 style={{ textAlign: "center" }}>{isFlagged ? "Session flagged" : "Nice work"}</h2>
        <p className="text-soft" style={{ textAlign: "center", marginBottom: "1.4rem" }}>
          {isFlagged ? detail.flag_reason ?? "This session didn't pass anti-cheat checks." : "Session logged and verified"}
        </p>

        <div className="complete-row">
          <span>Verified minutes</span>
          <span className="mono">{detail.verified_minutes} min</span>
        </div>
        <div className="complete-row">
          <span>Knowledge Points earned</span>
          <span className="mono" style={{ color: "color-mix(in srgb, var(--lime) 55%, var(--text) 45%)", fontWeight: 800 }}>
            {kpEarned === null ? "···" : `+${kpEarned} KP`}
          </span>
        </div>
        {totalChecks > 0 && (
          <div className="complete-row">
            <span>Checks passed</span>
            <span className="mono">{passedChecks} / {totalChecks}</span>
          </div>
        )}

        {detail.target_minutes !== null && (
          <>
            <div className="complete-row">
              <span>Target time ({detail.target_minutes} min)</span>
              <span className="mono">{detail.target_time_met ? "Cleared (+2 KP)" : "Not reached"}</span>
            </div>

            {detail.quiz?.status === "generating" && (
              <div className="banner banner-info">Your quiz is still being generated — check back in a moment.</div>
            )}
            {detail.quiz?.status === "failed" && (
              <div className="banner banner-info">
                We couldn't generate a quiz from your material this time. Your studying and Knowledge Points are unaffected.
              </div>
            )}
            {detail.quiz?.status === "ready" && detail.quiz.submitted_at === null && (
              <button
                className="btn btn-dark btn-block"
                style={{ marginTop: "0.4rem", marginBottom: "1rem" }}
                onClick={() => navigate(`/session/${id}/quiz`)}
              >
                Take the quiz
              </button>
            )}
            {detail.quiz?.status === "ready" && detail.quiz.submitted_at !== null && (
              <div className="complete-row">
                <span>Quiz score</span>
                <span className="mono">{detail.quiz.score} / 10 ({detail.quiz.passed ? "Passed" : "Failed"})</span>
              </div>
            )}
            {detail.is_successful !== null && (
              <div className="complete-row">
                <span>Session marked</span>
                <span className="mono">{detail.is_successful ? "Successful" : "Not successful"}</span>
              </div>
            )}
          </>
        )}

        {detail.summary_text && <div className="complete-summary">&ldquo;{detail.summary_text}&rdquo;</div>}

        <Link to="/" className="btn btn-primary btn-block" style={{ marginTop: "auto" }}>
          Back to home
        </Link>
      </div>
    </div>
  );
}
