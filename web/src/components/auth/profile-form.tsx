"use client";

import { type FormEvent, useState } from "react";
import { DocumentTitle } from "@/components/document-title";
import { LanguageSwitch } from "@/components/language-switch";
import { Button, ErrorText, fieldClass, Panel } from "@/components/ui";
import { ApiError } from "@/lib/api";
import type { Lang } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/use-i18n";
import { useAuth, useUser } from "./auth-provider";

const USERNAME = "[A-Za-z0-9_\\-]{2,50}";

/** Профиль: язык (сохраняется сразу), ники Lichess / Chess.com, выход. */
export function ProfileForm() {
  const user = useUser();
  const { updateProfile, logout } = useAuth();
  const { t, lang } = useI18n();
  const [lichess, setLichess] = useState(user.lichess_username ?? "");
  const [chesscom, setChesscom] = useState(user.chesscom_username ?? "");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [langBusy, setLangBusy] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const p = t.auth.profile;

  const failed = (err: unknown) => setError(err instanceof ApiError ? err.message : t.errors.generic);

  async function changeLang(next: Lang) {
    if (next === lang) return;
    setLangBusy(true);
    setError(null);
    try {
      await updateProfile({ lang: next });
    } catch (err) {
      failed(err);
    } finally {
      setLangBusy(false);
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await updateProfile({
        lichess_username: lichess.trim() || null,
        chesscom_username: chesscom.trim() || null,
      });
      setLichess(updated.lichess_username ?? "");
      setChesscom(updated.chesscom_username ?? "");
      setSaved(true);
    } catch (err) {
      failed(err);
    } finally {
      setBusy(false);
    }
  }

  async function leave() {
    setLeaving(true);
    try {
      await logout();
    } catch {
      // Сессия на клиенте закрыта в любом случае (session.endSession).
    }
  }

  const since = new Intl.DateTimeFormat(lang, { day: "numeric", month: "long", year: "numeric" }).format(
    new Date(user.created_at),
  );
  const dirty = lichess.trim() !== (user.lichess_username ?? "") || chesscom.trim() !== (user.chesscom_username ?? "");

  return (
    <>
      <DocumentTitle page="profile" />
      <h1 className="text-2xl font-extrabold sm:text-3xl">{p.title}</h1>

      <Panel>
        <div className="flex min-w-0 items-center gap-3">
          <span
            aria-hidden
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-green text-xl font-extrabold text-white"
          >
            {user.email.charAt(0).toUpperCase()}
          </span>
          <div className="min-w-0">
            <p className="truncate font-bold">{user.email}</p>
            <p className="text-sm text-muted">{p.since(since)}</p>
          </div>
        </div>
      </Panel>

      <Panel title={p.language}>
        <div className="flex flex-col gap-2">
          <LanguageSwitch onChange={changeLang} disabled={langBusy} className="self-start" />
          <p className="text-sm text-muted">{p.languageHint}</p>
        </div>
      </Panel>

      <Panel title={p.usernames}>
        <form onSubmit={save} className="flex flex-col gap-4">
          <p className="text-sm text-muted">{p.usernamesHint}</p>
          <div className="grid gap-4 sm:grid-cols-2">
            {(
              [
                [p.lichess, lichess, setLichess, "lichess"],
                [p.chesscom, chesscom, setChesscom, "chesscom"],
              ] as const
            ).map(([label, value, set, name]) => (
              <label key={name} className="flex flex-col gap-1.5 text-sm font-semibold text-soft">
                {label}
                <input
                  name={name}
                  value={value}
                  onChange={(event) => {
                    set(event.target.value);
                    setSaved(false);
                  }}
                  pattern={USERNAME}
                  title={p.usernameInvalid}
                  autoComplete="off"
                  autoCapitalize="none"
                  spellCheck={false}
                  className={fieldClass}
                />
              </label>
            ))}
          </div>
          <ErrorText>{error}</ErrorText>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={busy || !dirty}>
              {t.common.actions.save}
            </Button>
            {saved && (
              <span role="status" className="text-sm font-semibold text-green">
                {t.common.actions.saved}
              </span>
            )}
          </div>
        </form>
      </Panel>

      <Button variant="raised" onClick={leave} disabled={leaving} className="self-start">
        <LogoutIcon />
        {p.logout}
      </Button>
    </>
  );
}

export function LogoutIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className={`${className} fill-none stroke-current`} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3M15 8l4 4-4 4M19 12H9" />
    </svg>
  );
}
