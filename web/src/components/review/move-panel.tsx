"use client";

import type { ReactNode } from "react";
import { CLASS_COLORS, canRetry, classLabel, displayClass, isError, type ClassKey } from "@/lib/classes";
import { lineLabels, moveNumber, sideToMove, type Ply } from "@/lib/chess";
import type { EngineSource } from "@/lib/engine/preference";
import { evalAfter, formatEval, leader, type WhiteEval } from "@/lib/eval";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { ClassifyOut, LineMove } from "@/lib/types";
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

/** Ход линии с номером: `24.` у белых, `24…` у первого хода чёрных, дальше без номера. */
function lineParts(fen: string, moves: LineMove[]) {
  let color = sideToMove(fen);
  let fullmove = Number(fen.split(" ")[5]) || 1;
  return moves.map((move, i) => {
    const number = color === "white" ? `${fullmove}.` : i === 0 ? `${fullmove}…` : null;
    const part = { number, san: move.san, color, uci: move.uci };
    if (color === "black") fullmove += 1;
    color = color === "white" ? "black" : "white";
    return part;
  });
}

/** Линия в фигурной нотации, как в анализе Chess.com. */
function FigurineLine({ fen, moves }: { fen: string; moves: LineMove[] }) {
  return (
    <>
      {lineParts(fen, moves).map((part, i) => (
        <span key={`${i}-${part.uci}`} className="mr-1.5 whitespace-nowrap">
          {part.number && <span className="mr-0.5">{part.number}</span>}
          <Figurine san={part.san} color={part.color} />
        </span>
      ))}
    </>
  );
}

/** Класс хода исследования для показа: «упущение» — значком вместо класса, кроме ошибок. */
export function exploreClassKey(result: ClassifyOut): ClassKey {
  return result.is_miss && !["mistake", "blunder"].includes(result.class) ? "miss" : result.class;
}

/** Режим исследования: свои ходы от позиции партии, класс каждого хода, оценка и лучшие
 *  линии движка — как анализ Chess.com. */
export function ExplorePanel({
  baseFen,
  fens,
  moves,
  step,
  classes,
  current,
  before,
  result,
  source,
  onSource,
  onStep,
  onPlayMove,
  onClose,
}: {
  baseFen: string;
  /** Позиции линии: [0] — исходная, [i] — после i-го хода. */
  fens: string[];
  moves: LineMove[];
  step: number;
  /** Класс каждого хода линии, если уже посчитан. */
  classes: (ClassifyOut | null)[];
  /** Оценка позиции на доске и позиции до последнего хода. */
  current: ExploreEval;
  before: ExploreEval | null;
  /** Класс последнего хода (на доске). */
  result: ClassifyOut | null;
  source: EngineSource;
  onSource: (source: EngineSource) => void;
  onStep: (step: number) => void;
  onPlayMove: (uci: string) => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const parts = lineParts(baseFen, moves);
  const fen = fens[step];
  const last = step > 0 ? parts[step - 1] : null;
  const value = result && exploreClassKey(result);
  const showBest =
    result !== null &&
    result.best_san !== null &&
    result.best_uci !== moves[step - 1]?.uci &&
    !["book", "forced", "brilliant", "great"].includes(result.class);
  const bestLine = before?.lines[0];
  const best = current.lines[0]?.moves[0];

  return (
    <div className="flex flex-col gap-3">
      <ModeHeader title={t.review.explore} onClose={onClose} />
      <ol className="flex flex-wrap gap-1 text-[15px] font-bold" aria-label={t.review.exploreMoves}>
        {parts.map((part, i) => {
          const done = classes[i];
          const key = done && exploreClassKey(done);
          const significant = key !== null && SIGNIFICANT.has(key);
          return (
            <li key={`${i}-${part.uci}`}>
              <button
                type="button"
                onClick={() => onStep(i + 1)}
                aria-current={step === i + 1 ? "true" : undefined}
                className={`flex items-center gap-1 rounded-md px-1.5 py-0.5 ${
                  step === i + 1 ? "bg-raised-hover text-ink" : "text-soft hover:bg-raised/60"
                }`}
                style={significant ? { color: CLASS_COLORS[key] } : undefined}
              >
                {part.number}
                {significant && <ClassBadge value={key} size={16} />}
                <Figurine san={part.san} color={part.color} />
              </button>
            </li>
          );
        })}
      </ol>

      <div className="flex flex-col gap-2.5 rounded-lg bg-sunken/70 p-3" aria-live="polite">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-bold tracking-wide text-muted uppercase">
            {t.review.exploreEngine}
            {current.depth > 0 && (
              <span className="ml-2 font-semibold normal-case">
                {t.review.exploreDepth(current.depth)}
                {current.pending && " …"}
              </span>
            )}
          </span>
          <EngineSourceSwitch
            label={t.review.exploreEngine}
            value={source}
            onChange={onSource}
            options={{ browser: t.review.engineBrowser, server: t.review.engineServer }}
          />
        </div>

        {last && (
          <div className="flex items-center gap-2" data-testid="explore-verdict">
            <LineEvalChip evaluation={current.evaluation} />
            {value ? (
              <>
                <ClassBadge value={value} size={22} />
                <p className="min-w-0 flex-1 leading-tight font-extrabold" style={{ color: CLASS_COLORS[value] }}>
                  <span className="whitespace-nowrap">
                    {last.number ?? `${moveNumberOf(fens[step - 1])}`} <Figurine san={last.san} color={last.color} />
                  </span>{" "}
                  {t.review.verdict(value, classLabel(t, value))}
                </p>
              </>
            ) : (
              <p className="flex-1 text-sm font-semibold text-muted">{t.review.exploreThinking}</p>
            )}
          </div>
        )}
        {showBest && bestLine && result && (
          <div className="flex items-start gap-2">
            <LineEvalChip evaluation={bestLine.evaluation} />
            <ClassBadge value="best" size={22} />
            <p className="min-w-0 flex-1 text-sm leading-snug font-bold text-soft">
              <span className="mr-1.5 font-extrabold whitespace-nowrap" style={{ color: CLASS_COLORS.best }}>
                <Figurine san={result.best_san!} color={last!.color} /> {t.review.verdict("best", classLabel(t, "best"))}
              </span>
              <FigurineLine fen={fens[step - 1]} moves={bestLine.moves.slice(1, 8)} />
            </p>
          </div>
        )}
        {last && <hr className="border-line" />}

        {current.error ? (
          <p role="alert" className="text-sm font-semibold text-danger">
            {current.error}
          </p>
        ) : current.lines.length === 0 ? (
          <p className="text-sm font-semibold text-muted">
            {current.pending ? t.review.exploreThinking : current.evaluation ? formatEval(current.evaluation) : null}
          </p>
        ) : (
          <ul className="flex flex-col gap-1.5" aria-label={t.review.exploreLines}>
            {current.lines.map((line, i) => (
              <li key={`${i}-${line.moves[0]?.uci}`}>
                <button
                  type="button"
                  onClick={() => line.moves[0] && onPlayMove(line.moves[0].uci)}
                  className="flex w-full items-start gap-2 rounded-md p-0.5 text-left hover:bg-raised/60"
                >
                  <LineEvalChip evaluation={line.evaluation} testId={i === 0 ? "explore-eval" : undefined} />
                  <span className="min-w-0 flex-1 truncate text-sm leading-6 font-bold text-soft">
                    <FigurineLine fen={fen} moves={line.moves.slice(0, 8)} />
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="grid grid-cols-[1fr_2fr_1fr] gap-2">
        <Button variant="raised" aria-label={t.review.prevMove} disabled={step === 0} onClick={() => onStep(step - 1)}>
          ←
        </Button>
        <Button variant="raised" disabled={!best} onClick={() => best && onPlayMove(best.uci)}>
          {t.review.playBest}
        </Button>
        <Button variant="raised" aria-label={t.review.nextMove} disabled={step >= moves.length} onClick={() => onStep(step + 1)}>
          →
        </Button>
      </div>
      <p className="text-xs font-semibold text-muted">{t.review.exploreHint}</p>
    </div>
  );
}

// Классы, которые в списке ходов выделяются значком и цветом (как в основном списке).
const SIGNIFICANT = new Set<ClassKey>(["brilliant", "great", "inaccuracy", "mistake", "miss", "blunder"]);

const moveNumberOf = (fen: string) =>
  `${Number(fen.split(" ")[5]) || 1}${sideToMove(fen) === "white" ? "." : "…"}`;

/** Оценка за белых плашкой: белая — перевес белых, тёмная — чёрных. */
function LineEvalChip({ evaluation, testId }: { evaluation: WhiteEval | null; testId?: string }) {
  const white = evaluation !== null && leader(evaluation) === "white";
  return (
    <span
      data-testid={testId}
      className={`min-w-14 shrink-0 rounded-md px-1.5 py-0.5 text-center text-sm font-extrabold tabular-nums ${
        white ? "bg-white text-[#2c2925]" : "bg-raised text-ink"
      }`}
    >
      {evaluation ? formatEval(evaluation) : "…"}
    </span>
  );
}
