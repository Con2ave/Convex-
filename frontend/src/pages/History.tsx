import { useEffect, useMemo, useState } from "react";
import * as api from "../api/client";
import { ApiError } from "../api/client";
import type { StudySessionResponse } from "../api/types";
import { BottomNav } from "../components/BottomNav";
import { SessionListRow } from "../components/SessionListRow";

type Filter = "all" | "completed" | "flagged";

export function History() {
  const [sessions, setSessions] = useState<StudySessionResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    api
      .listSessions()
      .then(setSessions)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load your sessions."));
  }, []);

  const filtered = useMemo(() => {
    if (!sessions) return [];
    if (filter === "all") return sessions;
    return sessions.filter((s) => s.status === filter);
  }, [sessions, filter]);

  return (
    <div className="app-shell">
      <div className="app-column has-nav">
        <h1 className="display-heading" style={{ fontSize: "1.7rem", marginBottom: "1.2rem" }}>
          Session history
        </h1>

        {error && <div className="banner banner-error">{error}</div>}

        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.2rem" }}>
          {(["all", "completed", "flagged"] as Filter[]).map((f) => (
            <button
              key={f}
              type="button"
              className={`chip ${filter === f ? "is-selected" : ""}`}
              onClick={() => setFilter(f)}
            >
              {f === "all" ? "All" : f === "completed" ? "Completed" : "Flagged"}
            </button>
          ))}
        </div>

        {sessions === null && <p className="text-soft" style={{ fontSize: "0.85rem" }}>Loading…</p>}
        {sessions && filtered.length === 0 && (
          <p className="text-soft" style={{ fontSize: "0.85rem" }}>Nothing here yet.</p>
        )}
        {filtered.map((s) => (
          <SessionListRow key={s.id} session={s} />
        ))}
      </div>
      <BottomNav />
    </div>
  );
}
