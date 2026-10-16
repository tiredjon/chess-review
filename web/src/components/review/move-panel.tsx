"use client";

import type { ReactNode } from "react";
import { CLASS_COLORS, canRetry, classLabel, displayClass, isError } from "@/lib/classes";
import { lineFens, lineLabels, moveNumber, type Ply } from "@/lib/chess";
import type { EngineSource } from "@/lib/engine/preference";
import { evalAfter, formatEval, leader } from "@/lib/eval";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { LineMove } from "@/lib/types";
import { Button } from "../ui";
import { ClassBadge } from "./class-badge";
import { Figurine } from "./move-list";
import { BubbleSkeleton, CoachBubble } from "./summary";
import type { ExploreEval } from "./use-explore-eval";

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
  const { t } = useI18n();
  if (!ply) {
    return <CoachBubble>{t.review.startPosition}</CoachBubble>;
  }
  const move = ply.move;
  if (!move) {
    return (
      <CoachBubble>
        <span className="font-bold">
          {moveNumber(ply)} {ply.san}
        </span>
        . {t.review.moveNotAnalyzed}
      </CoachBubble>
    );
  }

  const value = displayClass(move);
  const color = CLASS_COLORS[value];
  const differsFromBest = move.best_san !== null && move.best_uci !== move.uci;
  const showBest = differsFromBest && !["book", "forced", "brilliant", "great"].includes(move.class);
  const errorLike = isError(move) || move.is_miss;
  const evaluation = evalAfter(move);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2.5">
        <ClassBadge value={value} size={30} />
        <p className="min-w-0 flex-1 text-lg leading-tight font-extrabold" style={{ color }}>
          <span className="whitespace-nowrap">
            {moveNumber(ply)} <Figurine san={ply.san} color={ply.color} />
          </span>{" "}
          {t.review.verdict(value, classLabel(t, value))}
        </p>
        <EvalChip text={formatEval(evaluation)} white={leader(evaluation) === "white"} />
      </div>

      {showBest && (
        <p className="flex items-center gap-2 text-[15px] font-bold text-soft">
          <ClassBadge value="best" size={20} />
          {errorLike ? t.review.betterWas : t.review.bestMove}
          <span style={{ color: CLASS_COLORS.best }}>
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
            {differsFromBest ? t.review.bestLine : t.review.continuation}
          </Button>
        )}
        {errorLike && move.reply_pv && move.reply_pv.length > 0 && (
          <Button variant="raised" size="sm" onClick={() => onShowLine("refutation")}>
            {t.review.refutation}
          </Button>
        )}
        {canRetry(move) && (
          <Button size="sm" onClick={onRetry}>
            {t.review.retry}
          </Button>
        )}
      </div>
    </div>
  );
}

function EvalChip({ text, white }: { text: string; white: boolean }) {
  const { t } = useI18n();
  return (
    <span
      title={t.review.evalAfter}
      className={`shrink-0 rounded-md px-2 py-1 text-sm font-extrabold ${white ? "bg-white text-[#2c2925]" : "bg-sunken text-ink"}`}
    >
      {text}
    </span>
  );
}

function ModeHeader({ title, onClose }: { title: ReactNode; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-lg font-extrabold">{title}</p>
      <button type="button" onClick={onClose} className="text-sm font-bold text-green hover:underline">
        {t.review.backToGame}
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
  const { t } = useI18n();
  const labels = lineLabels(baseFen, line);
  return (
    <div className="flex flex-col gap-3">
      <ModeHeader title={title} onClose={onClose} />
      <ol className="flex flex-wrap gap-1 text-[15px] font-bold" aria-label={t.review.lineMoves}>
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
        <Button variant="raised" aria-label={t.review.prevMove} disabled={step === 0} onClick={() => onStep(step - 1)}>
          ←
        </Button>
        <Button variant="raised" onClick={onTogglePlay}>
          {playing ? t.review.pause : step >= line.length ? t.review.replay : t.review.play}
        </Button>
        <Button
          variant="raised"
          aria-label={t.review.nextMove}
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
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-3">
      <ModeHeader title={t.review.findBest} onClose={onClose} />
      <CoachBubble>
        <span role="status">
          {status === "waiting" && t.review.retryWaiting(ply.color, ply.san)}
          {status === "wrong" && t.review.retryWrong}
          {status === "solved" && (
            <>
              {t.review.retrySolved} <span className="font-extrabold">{ply.move?.best_san}</span>.
            </>
          )}
        </span>
      </CoachBubble>
      <div>
        {status === "solved" ? (
          <Button variant="raised" onClick={onShowLine}>
            {t.review.showLine}
          </Button>
        ) : (
          <Button variant="raised" onClick={onShowAnswer}>
            {t.review.showAnswer}
          </Button>
        )}
      </div>
    </div>
  );
}

/** Переключатель «Браузер / Сервер» — где считает движок. */
export function EngineSourceSwitch({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: EngineSource;
  onChange: (value: EngineSource) => void;
  options: Record<EngineSource, string>;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg bg-sunken p-0.5 text-xs font-bold">
      {(["browser", "server"] as const).map((source) => (
        <button
          key={source}
          type="button"
          role="radio"
          aria-checked={value === source}
          onClick={() => onChange(source)}
          className={`rounded-md px-2.5 py-1 ${value === source ? "bg-raised-hover text-ink" : "text-muted hover:text-soft"}`}
        >
          {options[source]}
        </button>
      ))}
    </div>
  );
}

/** Режим исследования: свои ходы от позиции партии, оценка и лучшая линия движка. */
export function ExplorePanel({
  baseFen,
  moves,
  step,
  evaluation,
  source,
  onSource,
  onStep,
  onPlayBest,
  onClose,
}: {
  baseFen: string;
  moves: LineMove[];
  step: number;
  evaluation: ExploreEval;
  source: EngineSource;
  onSource: (source: EngineSource) => void;
  onStep: (step: number) => void;
  onPlayBest: () => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const labels = lineLabels(baseFen, moves);
  const lineBase = positionAfter(baseFen, moves.slice(0, step));
  const best = lineLabels(lineBase, evaluation.line.slice(0, 10));
  return (
    <div className="flex flex-col gap-3">
      <ModeHeader title={t.review.explore} onClose={onClose} />
      <ol className="flex flex-wrap gap-1 text-[15px] font-bold" aria-label={t.review.exploreMoves}>
        {moves.map((move, i) => (
          <li key={`${i}-${move.uci}`}>
            <button
              type="button"
              onClick={() => onStep(i + 1)}
              aria-current={step === i + 1 ? "true" : undefined}
              className={`rounded-md px-1.5 py-0.5 ${step === i + 1 ? "bg-raised-hover text-ink" : "text-soft hover:bg-raised/60"}`}
            >
              {labels[i]}
            </button>
          </li>
        ))}
      </ol>
      <div className="flex flex-col gap-2 rounded-lg bg-sunken/70 p-3" aria-live="polite">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-bold uppercase tracking-wide text-muted">{t.review.exploreEngine}</span>
          <EngineSourceSwitch
            label={t.review.exploreEngine}
            value={source}
            onChange={onSource}
            options={{ browser: t.review.engineBrowser, server: t.review.engineServer }}
          />
        </div>
        {evaluation.error ? (
          <p role="alert" className="text-sm font-semibold text-danger">
            {evaluation.error}
          </p>
        ) : (
          <div className="flex items-baseline gap-2.5">
            <span className="min-w-14 text-lg font-extrabold tabular-nums" data-testid="explore-eval">
              {evaluation.evaluation ? formatEval(evaluation.evaluation) : "…"}
            </span>
            <span className="min-w-0 flex-1 text-sm font-semibold text-soft">
              {best.length > 0 ? best.join(" ") : evaluation.pending ? t.review.exploreThinking : null}
            </span>
          </div>
        )}
        <p className="text-xs font-semibold text-muted">
          {evaluation.depth > 0 && t.review.exploreDepth(evaluation.depth)}
          {evaluation.pending && evaluation.depth > 0 && " …"}
        </p>
      </div>
      <div className="grid grid-cols-[1fr_2fr_1fr] gap-2">
        <Button variant="raised" aria-label={t.review.prevMove} disabled={step === 0} onClick={() => onStep(step - 1)}>
          ←
        </Button>
        <Button variant="raised" disabled={evaluation.line.length === 0} onClick={onPlayBest}>
          {t.review.playBest}
        </Button>
        <Button
          variant="raised"
          aria-label={t.review.nextMove}
          disabled={step >= moves.length}
          onClick={() => onStep(step + 1)}
        >
          →
        </Button>
      </div>
      <p className="text-xs font-semibold text-muted">{t.review.exploreHint}</p>
    </div>
  );
}

function positionAfter(fen: string, moves: LineMove[]): string {
  return lineFens(fen, moves).at(-1) ?? fen;
}
