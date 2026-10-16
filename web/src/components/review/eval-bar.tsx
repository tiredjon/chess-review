"use client";

import { formatEval, formatEvalShort, leader, whiteWinPercent, type WhiteEval } from "@/lib/eval";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { Color } from "@/lib/types";

/** Вертикальная шкала оценки: доля белых = win% белых. Белые — со стороны своего края доски. */
export function EvalBar({ evaluation, orientation }: { evaluation: WhiteEval | null; orientation: Color }) {
  const { t } = useI18n();
  const white = evaluation ? whiteWinPercent(evaluation) : 50;
  const ahead = evaluation ? leader(evaluation) : "white";
  const whiteAtBottom = orientation === "white";
  // Подпись — у края стороны, которая лучше.
  const labelAtBottom = (ahead === "white") === whiteAtBottom;
  return (
    <div
      role="meter"
      aria-label={t.review.evalLabel}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(white)}
      aria-valuetext={evaluation ? formatEval(evaluation) : t.review.noEval}
      className="relative h-full w-full overflow-hidden rounded-[3px] bg-[var(--graph-black)]"
    >
      <div
        className="absolute inset-x-0 bg-[var(--graph-white)] transition-[height] duration-700 ease-[cubic-bezier(0.4,0,0.2,1)]"
        style={{ height: `${white}%`, [whiteAtBottom ? "bottom" : "top"]: 0 }}
      />
      {evaluation && (
        <span
          className={`absolute inset-x-0 text-center text-[10px] font-extrabold leading-none sm:text-[11px] ${
            labelAtBottom ? "bottom-1.5" : "top-1.5"
          } ${ahead === "white" ? "text-[var(--graph-black)]" : "text-[var(--graph-white)]"}`}
        >
          {formatEvalShort(evaluation)}
        </span>
      )}
    </div>
  );
}
