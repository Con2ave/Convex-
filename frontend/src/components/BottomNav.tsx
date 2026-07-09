import { NavLink } from "react-router-dom";
import { HomeIcon, HistoryIcon, ProfileIcon } from "./icons";

const ITEMS = [
  { to: "/", label: "Home", icon: HomeIcon, end: true },
  { to: "/history", label: "History", icon: HistoryIcon, end: false },
  { to: "/profile", label: "Profile", icon: ProfileIcon, end: false },
];

export function BottomNav() {
  return (
    <nav className="bottom-nav">
      <div className="bottom-nav-inner">
        {ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => `bottom-nav-item${isActive ? " is-active" : ""}`}
          >
            <Icon size={20} />
            {label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
