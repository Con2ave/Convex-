import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <div className="app-shell">
        <div className="app-column" style={{ justifyContent: "center", alignItems: "center" }}>
          <p className="text-soft">Loading…</p>
        </div>
      </div>
    );
  }

  if (status === "signed-out") {
    return <Navigate to="/sign-in" replace />;
  }

  return <>{children}</>;
}
