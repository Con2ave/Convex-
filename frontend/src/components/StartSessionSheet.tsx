import { useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../api/client";
import { ApiError } from "../api/client";
import { DocumentIcon, UploadIcon } from "./icons";

const MIN_TARGET_MINUTES = 45;
const ACCEPTED_EXTENSIONS = [".pdf", ".txt"];

interface StartSessionSheetProps {
  onClose: () => void;
}

export function StartSessionSheet({ onClose }: StartSessionSheetProps) {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [subject, setSubject] = useState("");
  const [targetMinutes, setTargetMinutes] = useState(String(MIN_TARGET_MINUTES));
  const [material, setMaterial] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  function pickFile(file: File | null) {
    setError(null);
    if (file) {
      const lower = file.name.toLowerCase();
      if (!ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext))) {
        setError("Only PDF and plain text (.txt) files are supported right now.");
        return;
      }
    }
    setMaterial(file);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    const trimmedSubject = subject.trim();
    const minutes = Number(targetMinutes);

    if (!trimmedSubject) {
      setError("Give this session a subject.");
      return;
    }
    if (!Number.isFinite(minutes) || minutes < MIN_TARGET_MINUTES) {
      setError(`Target study time must be at least ${MIN_TARGET_MINUTES} minutes.`);
      return;
    }
    if (!material) {
      setError("Upload your lecture material to generate a quiz from.");
      return;
    }

    setStarting(true);
    try {
      const session = await api.startGuidedSession({
        subject_tag: trimmedSubject,
        target_minutes: minutes,
        material,
      });
      navigate(`/session/${session.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start this session.");
      setStarting(false);
    }
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <form className="sheet-panel" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <div className="sheet-handle" />

        <p style={{ fontWeight: 800, fontSize: "1.05rem", marginBottom: "0.25rem" }}>Start with lecture material</p>
        <p className="text-soft" style={{ fontSize: "0.82rem", marginBottom: "1.1rem" }}>
          Upload what you're studying and we'll quiz you on it once you're done. Score 70%+ and clear
          your target time to mark the session a success.
        </p>

        {error && <div className="banner banner-error">{error}</div>}

        <div className="field">
          <label htmlFor="guided-subject">Subject</label>
          <input
            id="guided-subject"
            className="input"
            placeholder="e.g. Cell biology"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            disabled={starting}
            required
          />
        </div>

        <div className="field">
          <label htmlFor="guided-minutes">Target study time (minutes)</label>
          <input
            id="guided-minutes"
            className="input"
            type="number"
            min={MIN_TARGET_MINUTES}
            step={5}
            value={targetMinutes}
            onChange={(e) => setTargetMinutes(e.target.value)}
            disabled={starting}
            required
          />
        </div>

        <div className="field">
          <label>Lecture material (PDF or .txt)</label>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt"
            className="file-input-hidden"
            onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
            disabled={starting}
          />
          <button
            type="button"
            className="file-picker"
            onClick={() => fileInputRef.current?.click()}
            disabled={starting}
          >
            {material ? <DocumentIcon size={18} /> : <UploadIcon size={18} />}
            <span className="file-picker-label">{material ? material.name : "Choose a file"}</span>
          </button>
        </div>

        <button className="btn btn-primary btn-block" type="submit" disabled={starting}>
          {starting ? "Starting…" : "Start studying"}
        </button>
      </form>
    </div>
  );
}
