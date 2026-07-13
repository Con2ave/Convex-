import { useNavigate } from "react-router-dom";
import { ChevronRightIcon, HelpIcon, SettingsIcon, TrophyIcon } from "./icons";

interface MenuSheetProps {
  onClose: () => void;
}

export function MenuSheet({ onClose }: MenuSheetProps) {
  const navigate = useNavigate();

  function go(path: string) {
    onClose();
    navigate(path);
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet-panel" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-handle" />

        <button className="list-row" onClick={() => go("/settings")}>
          <span className="icon-tile" style={{ width: 44, height: 44 }}>
            <SettingsIcon size={20} />
          </span>
          <span className="list-row-main">
            <div className="list-row-title">Settings</div>
            <div className="list-row-sub">Appearance and preferences</div>
          </span>
          <ChevronRightIcon size={18} className="list-row-chevron" />
        </button>

        <button className="list-row" onClick={() => go("/faq")}>
          <span className="icon-tile" style={{ width: 44, height: 44 }}>
            <HelpIcon size={20} />
          </span>
          <span className="list-row-main">
            <div className="list-row-title">FAQ</div>
            <div className="list-row-sub">Questions? Get in touch</div>
          </span>
          <ChevronRightIcon size={18} className="list-row-chevron" />
        </button>

        <button className="list-row" onClick={() => go("/leaderboard")}>
          <span className="icon-tile" style={{ width: 44, height: 44 }}>
            <TrophyIcon size={20} />
          </span>
          <span className="list-row-main">
            <div className="list-row-title">Leaderboard</div>
            <div className="list-row-sub">See who's leading the pack</div>
          </span>
          <ChevronRightIcon size={18} className="list-row-chevron" />
        </button>
      </div>
    </div>
  );
}
