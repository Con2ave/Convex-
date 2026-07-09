import { useNavigate } from "react-router-dom";
import { useTheme, type ThemePreference } from "../context/ThemeContext";
import { ChevronLeftIcon, DeviceIcon, MoonIcon, SunIcon } from "../components/icons";

const OPTIONS: { value: ThemePreference; label: string; icon: typeof SunIcon }[] = [
  { value: "light", label: "Light", icon: SunIcon },
  { value: "dark", label: "Dark", icon: MoonIcon },
  { value: "system", label: "System", icon: DeviceIcon },
];

export function Settings() {
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();

  return (
    <div className="app-shell">
      <div className="app-column">
        <div className="topbar" style={{ marginBottom: "0.6rem" }}>
          <button className="topbar-icon-btn" aria-label="Back" onClick={() => navigate(-1)}>
            <ChevronLeftIcon size={18} />
          </button>
        </div>

        <h1 className="display-heading" style={{ fontSize: "1.7rem", marginBottom: "1.4rem" }}>
          Settings
        </h1>

        <p className="stat-label" style={{ marginBottom: "0.6rem" }}>Appearance</p>
        <div className="card" style={{ marginBottom: "1.2rem" }}>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            {OPTIONS.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                type="button"
                className={`chip ${theme === value ? "is-selected" : ""}`}
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "0.4rem",
                  padding: "0.9rem 0.5rem",
                }}
                onClick={() => setTheme(value)}
              >
                <Icon size={20} />
                {label}
              </button>
            ))}
          </div>
        </div>
        <p className="text-soft" style={{ fontSize: "0.78rem" }}>
          "System" follows your device's light/dark setting automatically.
        </p>
      </div>
    </div>
  );
}
