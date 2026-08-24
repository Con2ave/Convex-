import { useEffect, useRef } from "react";
import { useTheme } from "../context/ThemeContext";
import "../lib/google-identity.d.ts";

const GIS_SCRIPT_SRC = "https://accounts.google.com/gsi/client";
let gisScriptPromise: Promise<void> | null = null;

function loadGisScript(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!gisScriptPromise) {
    gisScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = GIS_SCRIPT_SRC;
      script.async = true;
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Failed to load Google Identity Services."));
      document.head.appendChild(script);
    });
  }
  return gisScriptPromise;
}

function prefersDark(theme: "light" | "dark" | "system"): boolean {
  if (theme === "dark") return true;
  if (theme === "light") return false;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

interface GoogleSignInButtonProps {
  onCredential: (credential: string) => void;
  text?: "signin_with" | "signup_with" | "continue_with";
}

export function GoogleSignInButton({ onCredential, text = "continue_with" }: GoogleSignInButtonProps) {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
  const containerRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (!clientId || !containerRef.current) return;
    let cancelled = false;

    loadGisScript().then(() => {
      if (cancelled || !window.google || !containerRef.current) return;
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: (response) => onCredential(response.credential),
        use_fedcm_for_button: true,
        itp_support: true,
      });
      // GIS doesn't support live theme swapping on an already-rendered button - clear and
      // re-render from scratch whenever the app's theme changes.
      containerRef.current.innerHTML = "";
      window.google.accounts.id.renderButton(containerRef.current, {
        type: "standard",
        theme: prefersDark(theme) ? "filled_black" : "outline",
        size: "large",
        text,
        shape: "rectangular",
        width: 320,
      });
    });

    return () => {
      cancelled = true;
    };
  }, [clientId, theme, text, onCredential]);

  if (!clientId) return null;
  return <div ref={containerRef} style={{ display: "flex", justifyContent: "center" }} />;
}
