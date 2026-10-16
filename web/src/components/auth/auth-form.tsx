"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";
import { DocumentTitle } from "@/components/document-title";
import { Button, ErrorText, fieldClass } from "@/components/ui";
import { auth, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n/use-i18n";

const MIN_PASSWORD = 8;

/**
 * Вход и регистрация — одна форма. После успеха редирект делает GuestOnly (по событию
 * входа), туда, откуда отправили на вход (`?next=`).
 */
export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { t, lang } = useI18n();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const copy = mode === "login" ? t.auth.login : t.auth.register;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (mode === "register" && password.length < MIN_PASSWORD) {
      setError(t.auth.passwordTooShort);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await auth.login(email.trim(), password);
      else await auth.register(email.trim(), password, lang);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.errors.generic);
      setBusy(false);
    }
  }

  // Ссылка на соседнюю форму сохраняет `?next=`.
  const next = typeof window === "undefined" ? "" : window.location.search;
  const other = mode === "login" ? `/register${next}` : `/login${next}`;

  return (
    <div className="flex flex-col gap-5">
      <DocumentTitle page={mode} />
      <div className="text-center">
        <h1 className="text-2xl font-extrabold sm:text-3xl">{copy.heading}</h1>
        <p className="mt-2 text-sm text-muted">{t.auth.tagline}</p>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-4 rounded-xl bg-panel p-5 sm:p-6">
        <label className="flex flex-col gap-1.5 text-sm font-semibold text-soft">
          {t.auth.fields.email}
          <input
            type="email"
            name="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            autoComplete="email"
            inputMode="email"
            autoCapitalize="none"
            spellCheck={false}
            className={fieldClass}
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-semibold text-soft">
          {t.auth.fields.password}
          <span className="relative">
            <input
              type={visible ? "text" : "password"}
              name="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={mode === "register" ? MIN_PASSWORD : undefined}
              maxLength={128}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className={`${fieldClass} pr-12`}
            />
            <button
              type="button"
              onClick={() => setVisible((v) => !v)}
              aria-label={visible ? t.auth.fields.hidePassword : t.auth.fields.showPassword}
              aria-pressed={visible}
              className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-muted hover:text-ink"
            >
              <EyeIcon open={visible} />
            </button>
          </span>
          {mode === "register" && <span className="text-xs font-normal text-muted">{t.auth.register.passwordHint}</span>}
        </label>
        <ErrorText>{error}</ErrorText>
        <Button type="submit" size="lg" disabled={busy || !email.trim() || !password}>
          {copy.submit}
        </Button>
      </form>
      <p className="text-center text-sm text-soft">
        {mode === "login" ? t.auth.login.noAccount : t.auth.register.haveAccount}{" "}
        <Link href={other} className="font-bold text-green hover:underline">
          {mode === "login" ? t.auth.login.toRegister : t.auth.register.toLogin}
        </Link>
      </p>
    </div>
  );
}

function EyeIcon({ open }: { open: boolean }) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2" strokeLinecap="round">
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
      {!open && <path d="M4 20 20 4" />}
    </svg>
  );
}
