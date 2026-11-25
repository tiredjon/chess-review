"use client";

import { ApiError } from "@/lib/api";
import { coursesApi, type CourseOut, type MoveStats, type NodeEval } from "@/lib/courses-api";
import { formatEval, whiteWinPercent, type WhiteEval } from "@/lib/eval";
import type { Dict, Lang } from "@/lib/i18n";
import type { Color } from "@/lib/types";
import { PieceImage } from "../board-theme";
import { moveNo, type OpeningNode } from "../openings/types";

/**
 * Текст ошибки API для курсов и тренажёра. Общий словарь (`errors.codes`) уже подставлен в
 * `ApiError.message`; здесь — уточнения раздела: лимиты `course` / `trainer` и движок
 * тренажёра (общий текст про «Docker / браузер» тут не к месту).
 */
export function errorText(t: Dict, err: unknown, fallback: string): string {
  if (!(err instanceof ApiError)) return fallback;
  const seconds = Number(err.params.retry_after ?? 60);
  if (err.code === "rate_limited" && err.params.scope === "trainer") return t.trainer.errors.rateLimited(seconds);
  if (err.code === "rate_limited" && err.params.scope === "course") return t.trainer.errors.courseLimited(seconds);
  if (err.code === "engine_unavailable") return t.trainer.errors.engine;
  return err.message || fallback;
}

/** Код ошибки сборки курса → текст общего словаря. */
export const buildErrorText = (t: Dict, code: string | null) =>
  code === "engine_unavailable"
    ? t.courses.building.engineFailed
    : ((code ? t.errors.codes[code]?.({}) : null) ?? t.courses.building.failedText);

/** Упавший курс тем же `POST /courses` ставится в очередь заново (13.4). */
export const rebuildCourse = (course: CourseOut) =>
  coursesApi.create({ line_uci: course.line_uci, color: course.color, source: course.source, name: course.name });

/** Ход с номером: «6. Be3», «6…e5». */
export function moveLabel(node: Pick<OpeningNode, "ply" | "san">): string {
  if (!node.san) return "";
  return `${moveNo(node.ply)}${node.ply % 2 === 1 ? "." : "…"}${node.ply % 2 === 1 ? " " : ""}${node.san}`;
}

/** Король цвета курса — значок «за белых / за чёрных». */
export function ColorMark({ color, size = 22 }: { color: Color; size?: number }) {
  return (
    <span aria-hidden className="inline-block shrink-0" style={{ width: size, height: size }}>
      <PieceImage
        code={color === "white" ? "wK" : "bK"}
        style={color === "black" ? { filter: "drop-shadow(0 0 0.8px #e8e3db) drop-shadow(0 0 0.8px #e8e3db)" } : {}}
      />
    </span>
  );
}

export const nodeEval = (value: NodeEval | null): WhiteEval | null => {
  if (!value) return null;
  if (value.mate !== null) return value.mate === 0 ? null : { kind: "mate", moves: value.mate };
  return value.cp === null ? null : { kind: "cp", cp: value.cp };
};

/** Оценка как на шкале Chess.com: белая плашка — лучше белым, тёмная — чёрным. */
export function EvalChip({ value, className = "" }: { value: NodeEval | null; className?: string }) {
  const evaluation = nodeEval(value);
  if (!evaluation) return null;
  const white = whiteWinPercent(evaluation) >= 50;
  return (
    <span
      className={`inline-flex min-w-14 items-center justify-center rounded-md px-2 py-1 text-sm font-extrabold tabular-nums ${
        white ? "bg-white text-[#2c2925]" : "bg-[#403d39] text-white ring-1 ring-white/10"
      } ${className}`}
    >
      {formatEval(evaluation)}
    </span>
  );
}

/** Доли партий мастеров: белые / ничьи / чёрные (как в «Исследовании» Chess.com). */
export function MastersBar({ stats, className = "", showLabels = false }: { stats: MoveStats; className?: string; showLabels?: boolean }) {
  const total = stats.white + stats.draws + stats.black;
  if (total === 0) return null;
  const pct = (n: number) => Math.round((n / total) * 100);
  const parts = [
    { key: "w", value: stats.white, cls: "bg-[#f2efe9] text-[#2c2925]" },
    { key: "d", value: stats.draws, cls: "bg-[#8b8781] text-white" },
    { key: "b", value: stats.black, cls: "bg-[#403d39] text-white" },
  ];
  return (
    <div
      role="img"
      aria-label={`${pct(stats.white)} / ${pct(stats.draws)} / ${pct(stats.black)}`}
      className={`flex overflow-hidden rounded-[4px] bg-sunken ${showLabels ? "h-5" : "h-2"} ${className}`}
    >
      {parts.map((part) => (
        <span
          key={part.key}
          className={`flex items-center justify-center overflow-hidden text-[11px] leading-none font-bold ${part.cls}`}
          style={{ width: `${(part.value / total) * 100}%` }}
        >
          {showLabels && pct(part.value) >= 12 ? `${pct(part.value)}%` : ""}
        </span>
      ))}
    </div>
  );
}

export function ProgressBar({ value, className = "" }: { value: number; className?: string }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={clamped}
      className={`h-2 overflow-hidden rounded-full bg-sunken ${className}`}
    >
      <span className="block h-full rounded-full bg-green transition-[width] duration-500" style={{ width: `${clamped}%` }} />
    </div>
  );
}

const relativeFormats: Partial<Record<Lang, Intl.RelativeTimeFormat>> = {};

/** Когда снова: «через 3 дня» / «in 3 days» (как у пазлов). */
export function whenText(iso: string | null, lang: Lang): string {
  if (!iso) return "";
  const relative = (relativeFormats[lang] ??= new Intl.RelativeTimeFormat(lang, { numeric: "auto" }));
  const minutes = Math.round((new Date(iso).getTime() - Date.now()) / 60000);
  if (minutes < 60) return relative.format(Math.max(1, minutes), "minute");
  const hours = Math.round(minutes / 60);
  if (hours < 24) return relative.format(hours, "hour");
  return relative.format(Math.round(hours / 24), "day");
}
