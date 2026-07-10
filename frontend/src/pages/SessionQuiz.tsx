import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import * as api from "../api/client";
import { ApiError } from "../api/client";
import type { QuizOut, QuizResultOut } from "../api/types";
import { CheckIcon, ChevronLeftIcon, FlagIcon } from "../components/icons";

const POLL_INTERVAL_MS = 4_000;

export function SessionQuiz() {
  const { id } = useParams<{ id: string }>();
  const sessionId = Number(id);
  const navigate = useNavigate();

  const [quiz, setQuiz] = useState<QuizOut | null>(null);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<QuizResultOut | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await api.getQuiz(sessionId);
        if (cancelled) return;
        setQuiz(data);
        if (data.status === "ready" && data.questions) {
          setAnswers((prev) => (prev.length === data.questions!.length ? prev : new Array(data.questions!.length).fill(null)));
        }
        if (data.status !== "generating" && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Couldn't load this quiz.");
      }
    }

    void load();
    pollRef.current = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [sessionId]);

  function selectAnswer(questionIndex: number, optionIndex: number) {
    setAnswers((prev) => {
      const next = [...prev];
      next[questionIndex] = optionIndex;
      return next;
    });
  }

  async function handleSubmit() {
    if (!quiz?.questions || answers.some((a) => a === null)) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.submitQuiz(sessionId, answers as number[]);
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't submit your answers.");
    } finally {
      setSubmitting(false);
    }
  }

  if (error && !quiz) {
    return (
      <div className="app-shell">
        <div className="app-column">
          <div className="banner banner-error">{error}</div>
          <Link to={`/session/${sessionId}/complete`} className="btn btn-primary btn-block">Back</Link>
        </div>
      </div>
    );
  }

  if (!quiz || quiz.status === "generating") {
    return (
      <div className="app-shell">
        <div className="app-column">
          <p className="text-soft" style={{ marginTop: "2rem" }}>Generating your quiz from the material you uploaded…</p>
        </div>
      </div>
    );
  }

  if (quiz.status === "failed") {
    return (
      <div className="app-shell">
        <div className="app-column">
          <h2 style={{ marginBottom: "0.5rem" }}>Quiz unavailable</h2>
          <p className="text-soft" style={{ marginBottom: "1.4rem" }}>
            We couldn't generate a quiz from your material this time. Your studying and Knowledge Points are unaffected.
          </p>
          <Link to={`/session/${sessionId}/complete`} className="btn btn-primary btn-block">Back to summary</Link>
        </div>
      </div>
    );
  }

  if (result) {
    const isSuccess = result.passed;
    return (
      <div className="app-shell">
        <div className="app-column">
          <div
            className="complete-badge"
            style={
              isSuccess
                ? undefined
                : { background: "color-mix(in srgb, var(--danger) 18%, transparent)", color: "var(--danger)" }
            }
          >
            {isSuccess ? <CheckIcon size={26} /> : <FlagIcon size={26} />}
          </div>
          <h2 style={{ textAlign: "center" }}>{isSuccess ? "Quiz passed" : "Not quite there"}</h2>
          <p className="text-soft" style={{ textAlign: "center", marginBottom: "1.4rem" }}>
            {isSuccess ? "You cleared 70% or better." : "You'll need 70% or better to pass this quiz."}
          </p>

          <div className="complete-row">
            <span>Score</span>
            <span className="mono">{result.score} / {result.total}</span>
          </div>
          {result.is_successful !== null && (
            <div className="complete-row">
              <span>Session marked</span>
              <span className="mono">{result.is_successful ? "Successful" : "Not successful"}</span>
            </div>
          )}

          <Link to={`/session/${sessionId}/complete`} className="btn btn-primary btn-block" style={{ marginTop: "auto" }}>
            Back to summary
          </Link>
        </div>
      </div>
    );
  }

  const allAnswered = answers.length > 0 && answers.every((a) => a !== null);

  return (
    <div className="app-shell">
      <div className="app-column">
        <div className="session-top" style={{ marginBottom: "0.8rem" }}>
          <button className="topbar-icon-btn" aria-label="Back" onClick={() => navigate(-1)}>
            <ChevronLeftIcon size={18} />
          </button>
          <span className="wordmark" style={{ fontSize: "1.05rem" }}>{quiz.subject_tag ?? "Quiz"}</span>
        </div>

        {error && <div className="banner banner-error">{error}</div>}

        {quiz.questions?.map((q, qi) => (
          <div className="card" key={qi} style={{ marginBottom: "1rem" }}>
            <p style={{ fontWeight: 700, marginBottom: "0.8rem" }}>{qi + 1}. {q.question}</p>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {q.options.map((opt, oi) => (
                <button
                  key={oi}
                  type="button"
                  className={`chip ${answers[qi] === oi ? "is-selected" : ""}`}
                  style={{ textAlign: "left" }}
                  onClick={() => selectAnswer(qi, oi)}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
        ))}

        <button
          className="btn btn-primary btn-block"
          style={{ marginTop: "auto" }}
          disabled={!allAnswered || submitting}
          onClick={() => void handleSubmit()}
        >
          {submitting ? "Submitting…" : allAnswered ? "Submit answers" : "Answer every question to submit"}
        </button>
      </div>
    </div>
  );
}
