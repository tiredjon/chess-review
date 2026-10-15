"use client";

import type { ReactNode } from "react";
import { CLASS_META, canRetry, displayClass, isError } from "@/lib/classes";
import { lineLabels, moveNumber, type Ply } from "@/lib/chess";
import { evalAfter, formatEval, leader } from "@/lib/eval";
import type { LineMove } from "@/lib/types";
import { Button } from "../ui";
import { ClassBadge } from "./class-badge";
import { Figurine } from "./move-list";
import { BubbleSkeleton, CoachBubble } from "./summary";

export type LineKind = "best" | "refutation";

export type Explanation = { text: string } | { error: string } | undefined;

/** Панель текущего хода: класс, «лучше было», объяснение в облачке, действия. */
export function MovePanel({
  ply,
  explanation,
  onShowLine,
  onRetry,
}: {
  ply: Ply | null;
  explanation: Explanation;
  onShowLine: (kind: LineKind) => void;
  onRetry: () => void;
}) {
  if (!ply) {
    return <CoachBubble>Начальная позиция. Листайте ходы кнопками внизу или клавишами ← →.</CoachBubble>;
  }
  const move = ply.move;
  if (!move) {
    return (
      <CoachBubble>
        <span className="font-bold">
          {moveNumber(ply)} {ply.san}
        </span>
        . Оценка и объяснение появятся после анализа.
      </CoachBubble>
    );
  }

  const value = displayClass(move);
  const meta = CLASS_META[value];
  const differsFromBest = move.best_san !== null && move.best_uci !== move.uci;
  const showBest = differsFromBest && !["book", "forced", "brilliant", "great"].includes(move.class);
  const errorLike = isError(move) || move.is_miss;
  const evaluation = evalAfter(move);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2.5">
        <ClassBadge value={value} size={30} />
        <p className="min-w-0 flex-1 text-lg leading-tight font-extrabold" style={{ color: meta.color }}>
          <span className="whitespace-nowrap">
            {moveNumber(ply)} <Figurine san={ply.san} color={ply.color} />
          </span>{" "}
          — {meta.label.toLowerCase()}
        </p>
        <EvalChip text={formatEval(evaluation)} white={leader(evaluation) === "white"} />
      </div>

      {showBest && (
        <p className="flex items-center gap-2 text-[15px] font-bold text-soft">
          <ClassBadge value="best" size={20} />
          {errorLike ? "Лучше было" : "Лучший ход"}
          <span style={{ color: CLASS_META.best.color }}>
            <Figurine san={move.best_san!} color={ply.color} />
          </span>
        </p>
      )}

      <CoachBubble busy={explanation === undefined}>
        {explanation === undefined ? <BubbleSkeleton /> : "error" in explanation ? explanation.error : explanation.text}
      </CoachBubble>

      <div className="flex flex-wrap gap-2">
        {move.pv && move.pv.length > 0 && (
          <Button variant="raised" size="sm" onClick={() => onShowLine("best")}>
            {differsFromBest ? "Лучшая линия" : "Продолжение"}
          </Button>
        )}
        {errorLike && move.reply_pv && move.reply_pv.length > 0 && (
          <Button variant="raised" size="sm" onClick={() => onShowLine("refutation")}>
            Чем наказывается
          </Button>
        )}
        {canRetry(move) && (
          <Button size="sm" onClick={onRetry}>
            Найти лучший ход
          </Button>
        )}
      </div>
    </div>
  );
}

function EvalChip({ text, white }: { text: string; white: boolean }) {
  return (
    <span
      title="Оценка после хода, за белых"
      className={`shrink-0 rounded-md px-2 py-1 text-sm font-extrabold ${white ? "bg-white text-[#2c2925]" : "bg-sunken text-ink"}`}
    >
      {text}
    </span>
  );
}

function ModeHeader({ title, onClose }: { title: ReactNode; onClose: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-lg font-extrabold">{title}</p>
      <button type="button" onClick={onClose} className="text-sm font-bold text-green hover:underline">
        Вернуться к партии
      </button>
    </div>
  );
}

export function LinePanel({
  title,
  baseFen,
  line,
  step,
  playing,
  onStep,
  onTogglePlay,
  onClose,
}: {
  title: string;
  baseFen: string;
  line: LineMove[];
  step: number;
  playing: boolean;
  onStep: (step: number) => void;
  onTogglePlay: () => void;
  onClose: () => void;
}) {
  const labels = lineLabels(baseFen, line);
  return (
    <div className="flex flex-col gap-3">
      <ModeHeader title={title} onClose={onClose} />
      <ol className="flex flex-wrap gap-1 text-[15px] font-bold" aria-label="Ходы линии">
        {line.map((move, i) => (
          <li key={`${i}-${move.uci}`}>
            <button
              type="button"
              onClick={() => onStep(i + 1)}
              aria-current={step === i + 1 ? "true" : undefined}
              className={`rounded-md px-1.5 py-0.5 ${
                step === i + 1 ? "bg-raised-hover text-ink" : "text-soft hover:bg-raised/60"
              }`}
            >
              {labels[i]}
            </button>
          </li>
        ))}
      </ol>
      <div className="grid grid-cols-[1fr_2fr_1fr] gap-2">
        <Button variant="raised" aria-label="Ход назад" disabled={step === 0} onClick={() => onStep(step - 1)}>
          ←
        </Button>
        <Button variant="raised" onClick={onTogglePlay}>
          {playing ? "Пауза" : step >= line.length ? "Сначала" : "Проиграть"}
        </Button>
        <Button
          variant="raised"
          aria-label="Ход вперёд"
          disabled={step >= line.length}
          onClick={() => onStep(step + 1)}
        >
          →
        </Button>
      </div>
    </div>
  );
}

export type RetryStatus = "waiting" | "wrong" | "solved";

export function RetryPanel({
  ply,
  status,
  onShowAnswer,
  onShowLine,
  onClose,
}: {
  ply: Ply;
  status: RetryStatus;
  onShowAnswer: () => void;
  onShowLine: () => void;
  onClose: () => void;
}) {
  const side = ply.color === "white" ? "белых" : "чёрных";
  return (
    <div className="flex flex-col gap-3">
      <ModeHeader title="Найдите лучший ход" onClose={onClose} />
      <CoachBubble>
        <span role="status">
          {status === "waiting" && (
            <>Ход {side}. В партии было {ply.san} — найдите сильнее: перетащите фигуру или кликните по клеткам.</>
          )}
          {status === "wrong" && <>Не лучший ход. Попробуйте ещё раз.</>}
          {status === "solved" && (
            <>
              Верно: <span className="font-extrabold">{ply.move?.best_san}</span>.
            </>
          )}
        </span>
      </CoachBubble>
      <div>
        {status === "solved" ? (
          <Button variant="raised" onClick={onShowLine}>
            Показать линию
          </Button>
        ) : (
          <Button variant="raised" onClick={onShowAnswer}>
            Показать ответ
          </Button>
        )}
      </div>
    </div>
  );
}
