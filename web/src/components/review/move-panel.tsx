"use client";

import { CLASS_META, canRetry, displayClass, isError } from "@/lib/classes";
import { lineLabels, moveNumber, type Ply } from "@/lib/chess";
import { evalAfter, formatEval } from "@/lib/eval";
import type { LineMove } from "@/lib/types";
import { Button } from "../ui";
import { ClassBadge } from "./class-badge";

export type LineKind = "best" | "refutation";

export type Explanation = { text: string } | { error: string } | undefined;

/** Панель текущего хода: класс, «лучше было», объяснение, действия. */
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
    return (
      <PanelShell>
        <p className="font-medium">Начальная позиция</p>
        <p className="text-sm text-muted">
          Листайте ходы кнопками под доской или клавишами ← →, переходите к ходу кликом по списку
          или графику.
        </p>
      </PanelShell>
    );
  }
  const move = ply.move;
  if (!move) {
    return (
      <PanelShell>
        <p className="font-medium">
          {moveNumber(ply)} {ply.san}
        </p>
        <p className="text-sm text-muted">Оценка и объяснение появятся после анализа.</p>
      </PanelShell>
    );
  }

  const value = displayClass(move);
  const meta = CLASS_META[value];
  const differsFromBest = move.best_san !== null && move.best_uci !== move.uci;
  const showBest = differsFromBest && !["book", "forced", "brilliant", "great"].includes(move.class);
  const errorLike = isError(move) || move.is_miss;

  return (
    <PanelShell accent={meta.color}>
      <div className="flex items-center gap-2.5">
        <ClassBadge value={value} size={26} />
        <p className="min-w-0 flex-1 text-[17px] leading-tight">
          <span className="font-semibold">
            {moveNumber(ply)} {ply.san}
          </span>{" "}
          <span style={{ color: meta.color }} className="font-medium">
            {meta.label.toLowerCase()}
          </span>
        </p>
        <span className="text-sm font-medium text-muted" title="Оценка после хода, за белых">
          {formatEval(evalAfter(move))}
        </span>
      </div>

      {showBest && (
        <p className="text-sm">
          {errorLike ? "Лучше было" : "Лучший ход"}{" "}
          <span className="font-semibold">
            {moveNumber(ply)} {move.best_san}
          </span>
        </p>
      )}

      <ExplanationText explanation={explanation} />

      <div className="flex flex-wrap gap-2 pt-1">
        {move.pv && move.pv.length > 0 && (
          <Button variant="quiet" onClick={() => onShowLine("best")}>
            {differsFromBest ? "Лучшая линия" : "Продолжение"}
          </Button>
        )}
        {errorLike && move.reply_pv && move.reply_pv.length > 0 && (
          <Button variant="quiet" onClick={() => onShowLine("refutation")}>
            Чем наказывается
          </Button>
        )}
        {canRetry(move) && <Button onClick={onRetry}>Найти лучший ход</Button>}
      </div>
    </PanelShell>
  );
}

function ExplanationText({ explanation }: { explanation: Explanation }) {
  if (explanation === undefined) {
    return (
      <div aria-busy className="flex flex-col gap-1.5 py-1">
        <span className="h-3 w-full animate-pulse rounded bg-sunken" />
        <span className="h-3 w-2/3 animate-pulse rounded bg-sunken" />
      </div>
    );
  }
  if ("error" in explanation) return <p className="text-sm text-muted">{explanation.error}</p>;
  return <p className="text-[15px] leading-relaxed">{explanation.text}</p>;
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
    <PanelShell accent="var(--accent)">
      <div className="flex items-center justify-between gap-3">
        <p className="font-semibold">{title}</p>
        <button type="button" onClick={onClose} className="text-sm text-accent hover:underline">
          Вернуться к партии
        </button>
      </div>
      <ol className="flex flex-wrap gap-1 text-[15px]" aria-label="Ходы линии">
        {line.map((move, i) => (
          <li key={`${i}-${move.uci}`}>
            <button
              type="button"
              onClick={() => onStep(i + 1)}
              aria-current={step === i + 1 ? "true" : undefined}
              className={`rounded px-1.5 py-0.5 ${step === i + 1 ? "bg-accent text-accent-ink" : "hover:bg-sunken"}`}
            >
              {labels[i]}
            </button>
          </li>
        ))}
      </ol>
      <div className="flex gap-2">
        <Button variant="quiet" aria-label="Ход назад" disabled={step === 0} onClick={() => onStep(step - 1)}>
          ←
        </Button>
        <Button variant="quiet" onClick={onTogglePlay}>
          {playing ? "Пауза" : step >= line.length ? "Сначала" : "Проиграть"}
        </Button>
        <Button
          variant="quiet"
          aria-label="Ход вперёд"
          disabled={step >= line.length}
          onClick={() => onStep(step + 1)}
        >
          →
        </Button>
      </div>
    </PanelShell>
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
    <PanelShell accent={status === "solved" ? CLASS_META.best.color : "var(--accent)"}>
      <div className="flex items-center justify-between gap-3">
        <p className="font-semibold">Повтори лучший ход</p>
        <button type="button" onClick={onClose} className="text-sm text-accent hover:underline">
          Вернуться к партии
        </button>
      </div>
      <p role="status" className="text-[15px] leading-relaxed">
        {status === "waiting" && <>Ход {side}. Найдите ход сильнее, чем {ply.san}: перетащите фигуру или кликните по клеткам.</>}
        {status === "wrong" && <>Не лучший ход. Попробуйте ещё раз.</>}
        {status === "solved" && (
          <>
            Верно: <span className="font-semibold">{ply.move?.best_san}</span>.
          </>
        )}
      </p>
      <div className="flex flex-wrap gap-2">
        {status === "solved" ? (
          <Button variant="quiet" onClick={onShowLine}>
            Показать линию
          </Button>
        ) : (
          <Button variant="quiet" onClick={onShowAnswer}>
            Показать ответ
          </Button>
        )}
      </div>
    </PanelShell>
  );
}

function PanelShell({ children, accent }: { children: React.ReactNode; accent?: string }) {
  return (
    <section
      aria-live="polite"
      className="flex flex-col gap-2.5 rounded-lg border border-line bg-surface p-4"
      style={accent ? { borderTop: `3px solid ${accent}` } : undefined}
    >
      {children}
    </section>
  );
}
