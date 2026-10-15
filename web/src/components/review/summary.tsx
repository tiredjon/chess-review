"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";

/** Общий разбор партии (§6.3): 3–5 пунктов, строки «- …». */
export function GameSummary({ analysisId }: { analysisId: string }) {
  const [result, setResult] = useState<{ id: string; points: string[] } | { id: string; error: string } | null>(null);

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
        setResult({ id: analysisId, points });
      })
      .catch((err) => {
        if (!cancelled) setResult({ id: analysisId, error: err instanceof ApiError ? err.message : "Итог недоступен" });
      });
    return () => {
      cancelled = true;
    };
  }, [analysisId]);

  const current = result?.id === analysisId ? result : null;
  return (
    <section aria-label="Итог партии" className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-4">
      <h2 className="font-semibold">Итог партии</h2>
      {current === null && (
        <div aria-busy className="flex flex-col gap-2">
          <span className="h-3 w-full animate-pulse rounded bg-sunken" />
          <span className="h-3 w-5/6 animate-pulse rounded bg-sunken" />
          <span className="h-3 w-2/3 animate-pulse rounded bg-sunken" />
        </div>
      )}
      {current && "error" in current && <p className="text-sm text-muted">{current.error}</p>}
      {current && "points" in current && (
        <ul className="flex list-disc flex-col gap-1.5 pl-5 text-[15px] leading-relaxed marker:text-muted">
          {current.points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
