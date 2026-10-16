"use client";

import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { auth } from "@/lib/api";
import { setLang } from "@/lib/i18n/use-i18n";
import { onSessionChange, refreshSession } from "@/lib/session";
import type { ProfileUpdate, User } from "@/lib/types";

export type AuthStatus = "loading" | "guest" | "authed" | "offline";

type AuthContextValue = {
  status: AuthStatus;
  user: User | null;
  /** Гость после явного «Выйти» в этой вкладке: на вход без `?next=`. */
  loggedOut: boolean;
  /** Перепроверить сессию (после «нет связи с API»). */
  retry: () => void;
  logout: () => Promise<void>;
  updateProfile: (update: ProfileUpdate) => Promise<User>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Сессия на клиенте: при открытии страницы — обновление по refresh-cookie (access-токен
 * только в памяти), затем события входа / выхода из lib/session.ts (в том числе из других
 * вкладок). Язык интерфейса — из профиля вошедшего пользователя.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<User | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [loggedOut, setLoggedOut] = useState(false);

  useEffect(() => {
    const off = onSessionChange((event) => {
      if (event.type === "login") {
        setUser(event.user);
        setStatus("authed");
        setLoggedOut(false);
        setLang(event.user.lang);
      } else {
        setUser(null);
        setStatus("guest");
      }
    });
    refreshSession()
      .then((session) => {
        if (session === null) setStatus("guest");
      })
      .catch(() => setStatus("offline"));
    return off;
  }, [attempt]);

  const retry = useCallback(() => {
    setStatus("loading");
    setAttempt((n) => n + 1);
  }, []);

  const logout = useCallback(() => {
    setLoggedOut(true);
    return auth.logout();
  }, []);

  const updateProfile = useCallback(async (update: ProfileUpdate) => {
    const updated = await auth.updateMe(update);
    setUser(updated);
    if (update.lang) setLang(updated.lang);
    return updated;
  }, []);

  const value = useMemo(
    () => ({ status, user, loggedOut, retry, logout, updateProfile }),
    [status, user, loggedOut, retry, logout, updateProfile],
  );
  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) throw new Error("useAuth вне AuthProvider");
  return value;
}

/** Пользователь на страницах за входом (RequireAuth гарантирует, что он есть). */
export function useUser(): User {
  const { user } = useAuth();
  if (user === null) throw new Error("useUser без входа");
  return user;
}
