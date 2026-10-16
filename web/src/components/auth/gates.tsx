"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";
import { Button } from "@/components/ui";
import { useI18n } from "@/lib/i18n/use-i18n";
import { useAuth } from "./auth-provider";

/** Куда вернуться после входа: только свои пути (не `//evil.example`). */
export function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

/** Страницы приложения: без входа — на /login с возвратом сюда же. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, loggedOut } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status !== "guest") return;
    // URL — из window: usePathname / useSearchParams потребовали бы Suspense (Cache Components).
    const here = `${window.location.pathname}${window.location.search}`;
    router.replace(loggedOut || here === "/" ? "/login" : `/login?next=${encodeURIComponent(here)}`);
  }, [status, loggedOut, router]);

  if (status === "authed") return children;
  return <Splash />;
}

/** Вход и регистрация: уже вошедшего — сразу туда, откуда его отправили на вход. */
export function GuestOnly({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status !== "authed") return;
    router.replace(safeNext(new URLSearchParams(window.location.search).get("next")));
  }, [status, router]);

  if (status === "guest") return children;
  return <Splash />;
}

/** Заставка на время проверки входа; «нет связи с API» — с кнопкой повтора. */
function Splash() {
  const { status, retry } = useAuth();
  const { t } = useI18n();
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
      <span aria-hidden className={`text-6xl text-green ${status === "offline" ? "" : "cc-splash"}`}>
        ♞
      </span>
      {status === "offline" ? (
        <>
          <p role="alert" className="max-w-sm text-sm font-medium text-danger">
            {t.errors.server}
          </p>
          <Button onClick={retry}>{t.common.actions.retry}</Button>
        </>
      ) : (
        <p className="sr-only" role="status">
          {t.auth.checking}
        </p>
      )}
    </div>
  );
}
