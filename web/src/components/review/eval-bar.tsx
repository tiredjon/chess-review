import { formatEval, formatEvalShort, leader, whiteWinPercent, type WhiteEval } from "@/lib/eval";
import type { Color } from "@/lib/types";

/** Вертикальная шкала оценки: доля белых = win% белых. Белые — со стороны своего края доски. */
export function EvalBar({ evaluation, orientation }: { evaluation: WhiteEval | null; orientation: Color }) {
  const white = evaluation ? whiteWinPercent(evaluation) : 50;
  const ahead = evaluation ? leader(evaluation) : "white";
  const whiteAtBottom = orientation === "white";
  // Подпись — у края стороны, которая лучше.
  const labelAtBottom = (ahead === "white") === whiteAtBottom;
  return (
    <div
      role="meter"
      aria-label="Оценка позиции"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(white)}
      aria-valuetext={evaluation ? formatEval(evaluation) : "нет оценки"}
      className="relative h-full w-full overflow-hidden rounded-[3px] bg-[var(--graph-black)]"
    >
      <div
        className="absolute inset-x-0 bg-[var(--graph-white)] transition-[height] duration-300 ease-out"
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
