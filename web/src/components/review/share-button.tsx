"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Button } from "../ui";

/** «Поделиться»: публичная ссылка на разбор (`/share/{token}`), копирование и отзыв. */
export function ShareButton({ gameId }: { gameId: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch {
      // Буфер обмена недоступен (не HTTPS, запрет) — ссылку видно в поле.
    }
  };

  const toggle = async () => {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    setCopied(false);
    setError(null);
    if (url) return;
    setBusy(true);
    try {
      const share = await api.share(gameId);
      // Адрес — этого же сайта: PUBLIC_WEB_URL нужен боту, а браузер знает свой origin.
      const link = `${window.location.origin}/share/${share.token}`;
      setUrl(link);
      await copy(link);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.errors.generic);
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    setBusy(true);
    try {
      await api.unshare(gameId);
      setUrl(null);
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.errors.generic);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-label={t.review.share.button}
        title={t.review.share.button}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-soft hover:bg-raised hover:text-ink"
      >
        <svg aria-hidden viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="18" cy="5" r="2.6" />
          <circle cx="6" cy="12" r="2.6" />
          <circle cx="18" cy="19" r="2.6" />
          <path d="m8.3 10.8 7.4-4.4M8.3 13.2l7.4 4.4" />
        </svg>
      </button>
      {open && (
        <div
          role="dialog"
          aria-label={t.review.share.title}
          className="absolute top-11 -right-11 z-40 flex w-[min(18rem,calc(100vw-2rem))] flex-col gap-2.5 rounded-xl bg-raised p-3 shadow-[0_8px_24px_rgba(0,0,0,0.45)]"
        >
          <p className="text-sm font-extrabold">{t.review.share.title}</p>
          <p className="text-xs font-semibold text-soft">{t.review.share.hint}</p>
          {error && (
            <p role="alert" className="text-sm font-semibold text-danger">
              {error}
            </p>
          )}
          {url ? (
            <>
              <input
                readOnly
                value={url}
                aria-label={t.review.share.link}
                onFocus={(event) => event.currentTarget.select()}
                className="w-full rounded-lg bg-sunken px-2.5 py-2 text-xs font-semibold text-ink"
              />
              <div className="flex gap-2">
                <Button className="flex-1" onClick={() => copy(url)}>
                  {copied ? t.review.share.copied : t.review.share.copy}
                </Button>
                <Button variant="raised" onClick={revoke} disabled={busy}>
                  {t.review.share.revoke}
                </Button>
              </div>
            </>
          ) : (
            busy && <p className="text-sm text-muted">…</p>
          )}
        </div>
      )}
    </div>
  );
}
