import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import * as api from "../api/client";
import { tokenStore } from "../api/client";
import type { UserResponse } from "../api/types";

interface AuthContextValue {
  user: UserResponse | null;
  status: "loading" | "signed-in" | "signed-out";
  signIn: (username: string, password: string) => Promise<void>;
  signUp: (input: { username: string; email: string; password: string; password_confirm: string }) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [status, setStatus] = useState<AuthContextValue["status"]>("loading");

  useEffect(() => {
    if (!tokenStore.access) {
      setStatus("signed-out");
      return;
    }
    api
      .getCurrentUser()
      .then((u) => {
        setUser(u);
        setStatus("signed-in");
      })
      .catch(() => {
        tokenStore.clear();
        setStatus("signed-out");
      });
  }, []);

  const signIn = useCallback(async (username: string, password: string) => {
    await api.login(username, password);
    const me = await api.getCurrentUser();
    setUser(me);
    setStatus("signed-in");
  }, []);

  const signUp = useCallback(
    async (input: { username: string; email: string; password: string; password_confirm: string }) => {
      await api.register(input);
      await api.login(input.username, input.password);
      const me = await api.getCurrentUser();
      setUser(me);
      setStatus("signed-in");
    },
    []
  );

  const signOut = useCallback(async () => {
    await api.logout();
    setUser(null);
    setStatus("signed-out");
  }, []);

  return (
    <AuthContext.Provider value={{ user, status, signIn, signUp, signOut }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
