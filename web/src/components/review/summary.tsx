"use client";

import { useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n/use-i18n";

/** Реплика «тренера»: значок слева, облачко с текстом справа. */
export function CoachBubble({ children, busy = false }: { children: ReactNode; busy?: boolean }) {
  return (
    <div className="cc-bubble flex items-start gap-3">
      <span
        aria-hidden
        className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-raised text-[30px] leading-none text-green"
      >
        ♞
      </span>
      <div
        aria-busy={busy || undefined}
        className="relative min-w-0 flex-1 rounded-xl bg-white px-4 py-3 text-[15px] font-medium leading-snug text-[#2c2925] before:absolute before:top-4 before:-left-1.5 before:h-3 before:w-3 before:rotate-45 before:bg-white"
      >
        {children}
      </div>
    </div>
  );
}

export function BubbleSkeleton() {
  return (
    <div className="flex flex-col gap-2 py-1">
      <span className="h-3 w-full animate-pulse rounded bg-[#e3ded6]" />
      <span className="h-3 w-2/3 animate-pulse rounded bg-[#e3ded6]" />
    </div>
  );
}

// Пунктов итога в свёрнутом виде; первые — точность и ошибки, дальше — переломы.
const SUMMARY_PREVIEW = 2;

/** Общий разбор партии (§6.3): 3–5 пунктов, строки «- …». */
export function GameSummary({ analysisId }: { analysisId: string }) {
  const { t, lang } = useI18n();
  // Итог приходит на языке профиля: ключ — анализ и язык, после смены языка — запрос заново.
  const key = `${lang}:${analysisId}`;
  const [result, setResult] = useState<{ key: string; points: string[] } | { key: string; error: string } | null>(null);
  const unavailable = t.review.summaryUnavailable;

  useEffect(() => {
    let cancelled = false;
    api
      .summary(analysisId)
      .then((summary) => {
        if (cancelled) return;
        const points = summary.text
          .split("\n")
          .map((line) => line.replace(/^\s*[-•]\s*/, "").trim())
          .filter(Boolean);
        setResult({ key, points });
      })
      .catch((err) => {
        if (!cancelled) setResult({ key, error: err instanceof ApiError ? err.message : unavailable });
      });
    return () => {
      cancelled = true;
    };
  }, [analysisId, key, unavailable]);

  const [expanded, setExpanded] = useState(false);
  const current = result?.key === key ? result : null;
  const points = current && "points" in current ? current.points : [];
  const shown = expanded ? points : points.slice(0, SUMMARY_PREVIEW);
  return (
    <CoachBubble busy={current === null}>
      {current === null && <BubbleSkeleton />}
      {current && "error" in current && <p>{current.error}</p>}
      {points.length > 0 && (
        <>
          <ul className="flex flex-col gap-1.5">
            {shown.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
          {points.length > SUMMARY_PREVIEW && (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              aria-expanded={expanded}
              className="mt-1.5 text-sm font-bold text-[#557a2f] hover:underline"
            >
              {expanded ? t.review.collapse : t.review.more(points.length - SUMMARY_PREVIEW)}
            </button>
          )}
        </>
      )}
    </CoachBubble>
  );
}
