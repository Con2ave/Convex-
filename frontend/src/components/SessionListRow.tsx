import { useNavigate } from "react-router-dom";
import type { StudySessionResponse } from "../api/types";
import { formatWhen } from "../utils/format";
import { CheckIcon, ChevronRightIcon, ClockIcon, FlagIcon } from "./icons";

export function SessionListRow({ session }: { session: StudySessionResponse }) {
  const navigate = useNavigate();
  const isOpen = session.status === "active" || session.status === "paused";
  const target = isOpen ? `/session/${session.id}` : `/session/${session.id}/complete`;

  const tileClass = session.status === "flagged" ? "icon-tile coral" : session.status === "completed" ? "icon-tile lime" : "icon-tile";
  const Icon = session.status === "flagged" ? FlagIcon : session.status === "completed" ? CheckIcon : ClockIcon;

  const subParts = [formatWhen(session.started_at)];
  if (session.status === "flagged" && session.flag_reason) subParts.push(session.flag_reason);
  else if (isOpen) subParts.push(session.status);
  else subParts.push(`${session.verified_minutes} min verified`);

  return (
    <button className="list-row" onClick={() => navigate(target)}>
      <span className={tileClass}>
        <Icon size={20} />
      </span>
      <span className="list-row-main">
        <div className="list-row-title">{session.subject_tag ?? "Untitled session"}</div>
        <div className="list-row-sub">{subParts.join(" · ")}</div>
      </span>
      <ChevronRightIcon size={18} className="list-row-chevron" />
    </button>
  );
}
