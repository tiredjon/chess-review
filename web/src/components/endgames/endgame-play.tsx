"use client";

// Доигрывание позиции тренажёра эндшпиля (сессия 16.3): BotGame с `startFen`; соперник при ≤ 7
// фигурах — лучший ход по таблицам Syzygy (самая упорная защита, книга `OpponentBook`), иначе —
// Stockfish 2800. После каждого хода человека — плашка таблиц; цель и её выполнение — `./goal`;
// при провале — момент, где упущен результат, и ходы, которые его сохраняли. Попытка пишется
// в `POST /endgames/attempts` один раз.
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Arrow } from "react-chessboard";
import { ApiError } from "@/lib/api";
import { endgamesApi, type EndgameSource, type Progress, type Tablebase } from "@/lib/endgames-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { Color } from "@/lib/types";
import { CoachBubble } from "../review/summary";
import { BotGame } from "../play/bot-game";
import { replay, startOf } from "../play/game";
import type { BotGameVerdict, GameResult } from "../play/types";
import { Button } from "../ui";
import {
  bestMoves,
  bookMoveFrom,
  DRAW_HOLD_MOVES,
  effectiveGoal,
  evaluateGoal,
  flipWdl,
  humanPlies,
  pieceCount,
  TB_MAX_PIECES,
  wdlOf,
  type Goal,
  type HumanTb,
  type RulesEnd,
  type Wdl,
} from "./goal";

export type PlayTarget = {
  source: EndgameSource;
  key: string;
  fen: string;
  goal: Goal;
  name: string;
  hint: string | null;
  /** Позиция из партии: ссылка на разбор. */
  game?: { id: string; ply: number };
};

/** Соперник — сильнейший бот, когда таблиц нет (больше 7 фигур) или они не ответили. */
const BOT_ELO = 2800;
const BEST_ARROW = "rgba(129, 182, 76, 0.85)";
const ATTEMPT_STORAGE = "chess-review:endgames:attempt";

type TbState = { status: "ok"; data: Tablebase } | { status: "none" } | { status: "error" };

/** Ключ таблиц — расстановка, очередь, рокировки, en passant (счётчики ответа не меняют). */
const tbKey = (fen: string) => fen.split(" ").slice(0, 4).join(" ");

const newAttemptId = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

function readAttempt(storage: string): string {
  try {
    const saved = sessionStorage.getItem(storage);
    if (saved) return saved;
  } catch {
    // Хранилище недоступно — новая попытка.
  }
  return newAttemptId();
}

function writeAttempt(storage: string, id: string) {
  try {
    sessionStorage.setItem(storage, id);
  } catch {
    // Хранилище недоступно — партия не переживёт перезагрузку.
  }
}

/** Запросы к таблицам с общим кэшем на позицию (ответ бота и плашка — один запрос). */
function useTablebase() {
  const cache = useRef(new Map<string, Promise<Tablebase | null>>());
  const [states, setStates] = useState<Record<string, TbState>>({});

  const probe = useCallback((fen: string): Promise<Tablebase | null> => {
    const key = tbKey(fen);
    if (pieceCount(fen) > TB_MAX_PIECES) {
      setStates((prev) => (prev[key] ? prev : { ...prev, [key]: { status: "none" } }));
      return Promise.resolve(null);
    }
    const known = cache.current.get(key);
    if (known) return known;
    const request = endgamesApi
      .tablebase(fen)
      .then((data) => {
        setStates((prev) => ({ ...prev, [key]: { status: "ok", data } }));
        return data;
      })
      .catch((error: unknown) => {
        console.warn("tablebase failed", error);
        // Следующий запрос той же позиции спросит заново.
        cache.current.delete(key);
        setStates((prev) => ({ ...prev, [key]: { status: "error" } }));
        return null;
      });
    cache.current.set(key, request);
    return request;
  }, []);

  const stateOf = useCallback((fen: string): TbState | undefined => states[tbKey(fen)], [states]);
  return { probe, stateOf };
}

export function EndgamePlay({
  target,
  onBack,
  onNext,
  onRecorded,
}: {
  target: PlayTarget;
  onBack: () => void;
  /** Следующая позиция списка; null — её нет. */
  onNext: (() => void) | null;
  onRecorded?: (progress: Progress) => void;
}) {
  const storage = `${ATTEMPT_STORAGE}:${target.source}:${target.key}`;
  const [attempt, setAttempt] = useState(() => readAttempt(storage));
  useEffect(() => writeAttempt(storage, attempt), [storage, attempt]);
  const tablebase = useTablebase();

  const again = () => setAttempt(newAttemptId());
  return (
    <Attempt
      key={attempt}
      attempt={attempt}
      target={target}
      tablebase={tablebase}
      onBack={onBack}
      onNext={onNext}
      onAgain={again}
      onRecorded={onRecorded}
    />
  );
}

function Attempt({
  attempt,
  target,
  tablebase,
  onBack,
  onNext,
  onAgain,
  onRecorded,
}: {
  attempt: string;
  target: PlayTarget;
  tablebase: ReturnType<typeof useTablebase>;
  onBack: () => void;
  onNext: (() => void) | null;
  onAgain: () => void;
  onRecorded?: (progress: Progress) => void;
}) {
  const { t } = useI18n();
  const g = t.endgames.game;
  const { probe, stateOf } = tablebase;
  const start = useMemo(() => startOf(target.fen), [target.fen]);
  const human: Color = start.turn;

  const [history, setHistory] = useState<readonly string[]>([]);
  const [end, setEnd] = useState<RulesEnd | null>(null);
  const [focus, setFocus] = useState<{ ply: number; key: number } | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const game = useMemo(() => replay(history, target.fen), [history, target.fen]);
  const fens = game.fens;
  const humanMoves = useMemo(() => humanPlies(human, start.turn, game.moves.length), [human, start.turn, game.moves.length]);

  // Таблицы: начальная позиция и позиция после каждого хода человека (тот же ответ даёт ход бота).
  useEffect(() => {
    void probe(target.fen);
  }, [probe, target.fen]);
  useEffect(() => {
    for (const after of humanMoves) void probe(fens[after]);
  }, [fens, humanMoves, probe]);

  // Цель: у позиций из партий — с поправкой на таблицы начальной позиции.
  const startState = stateOf(target.fen);
  const startWdl: Wdl | null | undefined =
    startState === undefined ? undefined : startState.status === "ok" ? wdlOf(startState.data.category) : null;
  const goal: Goal | null =
    target.source === "catalog" || startWdl === undefined ? target.goal : effectiveGoal(target.goal, startWdl);

  const humanTb = useCallback(
    (fen: string): HumanTb => {
      const state = stateOf(fen);
      if (state === undefined) return undefined;
      if (state.status !== "ok") return null;
      const wdl = wdlOf(state.data.category);
      // Позиция после хода человека — глазами соперника (он на ходу).
      return wdl === null ? null : flipWdl(wdl);
    },
    [stateOf],
  );

  const tbAfter = useMemo(() => new Map(humanMoves.map((after) => [after, humanTb(fens[after])])), [fens, humanMoves, humanTb]);
  const status = goal
    ? evaluateGoal({ goal, human, firstMover: start.turn, plies: game.moves.length, tbAfter, end })
    : null;
  const finished = goal === null || (status !== null && status.state !== "playing");

  // Провал по таблицам: позиция до ошибки — какие ходы сохраняли результат.
  const missedAt = status?.state === "failure" ? status.missedAt : null;
  const beforeMiss = missedAt !== null ? fens[missedAt - 1] : null;
  useEffect(() => {
    if (beforeMiss) void probe(beforeMiss);
  }, [beforeMiss, probe]);
  const beforeState = beforeMiss ? stateOf(beforeMiss) : undefined;
  const saving = beforeState?.status === "ok" ? bestMoves(beforeState.data.moves) : [];
  const arrows: Record<number, Arrow[]> =
    missedAt === null || saving.length === 0
      ? {}
      : {
          [missedAt - 1]: saving.map((move) => ({
            startSquare: move.uci.slice(0, 2),
            endSquare: move.uci.slice(2, 4),
            color: BEST_ARROW,
          })),
        };

  // Попытка — один раз, когда цель выполнена или провалена.
  const recorded = useRef(false);
  const success = status?.state === "success";
  const plies = game.moves.length;
  useEffect(() => {
    if (!finished || goal === null || recorded.current) return;
    recorded.current = true;
    endgamesApi
      .attempt({ source: target.source, key: target.key, goal, success, plies })
      .then((progress) => onRecorded?.(progress))
      .catch((error: unknown) => setSaveError(error instanceof ApiError ? error.message : g.saveError));
  }, [finished, goal, success, plies, target.source, target.key, onRecorded, g.saveError]);

  // Тренажёр играет без часов — флага («timeout») здесь не бывает.
  const onFinished = useCallback((result: GameResult) => {
    if (result.reason !== "timeout") setEnd({ reason: result.reason, winner: result.winner });
  }, []);

  const book = useCallback(
    async (moves: readonly string[]) => {
      const fen = replay(moves, target.fen).fens[moves.length];
      if (!fen || pieceCount(fen) > TB_MAX_PIECES) return null;
      const data = await probe(fen);
      return data ? bookMoveFrom(data.moves) : null;
    },
    [probe, target.fen],
  );

  const moveLabel = (after: number) => {
    const index = after - 1;
    const offset = start.turn === "black" ? 1 : 0;
    const number = start.fullmove + Math.floor((index + offset) / 2);
    const white = (index + offset) % 2 === 0;
    return `${number}${white ? "." : "…"} ${game.sans[index] ?? ""}`;
  };

  const actions = (
    <div className="flex flex-col gap-2">
      <div className={`grid gap-2 ${onNext ? "grid-cols-2" : ""}`}>
        <Button onClick={onAgain} autoFocus>
          {g.again}
        </Button>
        {onNext && (
          <Button variant="raised" onClick={onNext}>
            {g.next}
          </Button>
        )}
      </div>
      <Button variant="raised" size="sm" onClick={onBack}>
        {g.back}
      </Button>
    </div>
  );

  let verdict: BotGameVerdict | null = null;
  if (goal === null) verdict = { tone: "neutral", text: g.nothingToTrain, actions };
  else if (status?.state === "success") verdict = { tone: "success", text: g.success[status.reason], actions };
  else if (status?.state === "failure") verdict = { tone: "failure", text: g.failure[status.reason], actions };

  // Плашка таблиц: после последнего хода человека, до первого — начальная позиция.
  const lastHuman = humanMoves.at(-1);
  const barFen = lastHuman !== undefined ? fens[lastHuman] : target.fen;
  const barState = stateOf(barFen);
  const barWdl = lastHuman !== undefined ? humanTb(barFen) : startWdl;
  const tbText =
    pieceCount(barFen) > TB_MAX_PIECES
      ? g.tb.none
      : barState === undefined
        ? g.tb.pending
        : barState.status === "error"
          ? g.tb.error
          : barWdl
            ? g.tb[barWdl]
            : g.tb.pending;
  const bigPosition = pieceCount(fens[game.moves.length]) > TB_MAX_PIECES;

  const aside = (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg bg-sunken/60 p-3">
        <p className="text-[15px] font-extrabold">{target.name}</p>
        <p className="mt-0.5 text-sm font-semibold text-soft">
          {goal === "draw" ? t.endgames.goalLong.draw(DRAW_HOLD_MOVES) : t.endgames.goalLong.win} · {t.endgames.side[human]}
        </p>
        <p className="mt-1.5 text-xs text-muted">{bigPosition ? g.opponentBot : g.opponentTb}</p>
        {target.hint && (
          <div className="mt-2">
            {showHint && <p className="text-sm text-soft">{target.hint}</p>}
            <button
              type="button"
              onClick={() => setShowHint((shown) => !shown)}
              className="mt-1 text-sm font-bold text-green hover:underline"
              aria-expanded={showHint}
            >
              {showHint ? g.hideHint : g.hint}
            </button>
          </div>
        )}
        {target.game && (
          <Link
            href={`/games/${target.game.id}?ply=${target.game.ply}`}
            className="mt-2 inline-block text-sm font-bold text-green hover:underline"
          >
            {g.openReview}
          </Link>
        )}
      </div>

      {goal !== null && goal !== target.goal && <CoachBubble>{g.goalAdjusted[goal]}</CoachBubble>}

      <TbBar title={lastHuman !== undefined ? g.tb.title : g.tb.start} text={tbText} wdl={barState?.status === "ok" ? (barWdl ?? null) : null} />

      {goal === "draw" && status?.state === "playing" && (
        <p className="text-sm font-semibold text-soft">{g.held(status.held, DRAW_HOLD_MOVES)}</p>
      )}

      {missedAt !== null && (
        <div role="note" className="flex flex-col gap-2 rounded-lg bg-danger/15 p-3">
          <p className="text-sm font-bold text-ink">{g.missed(moveLabel(missedAt), goal === "draw" ? "draw" : "win")}</p>
          {saving.length > 0 && <p className="text-sm text-soft">{g.better(saving.map((move) => move.san).join(", "))}</p>}
          <Button variant="raised" size="sm" className="self-start" onClick={() => setFocus({ ply: missedAt - 1, key: Date.now() })}>
            {g.showMoment}
          </Button>
        </div>
      )}
      {saveError && (
        <p role="alert" className="text-sm font-medium text-danger">
          {saveError}
        </p>
      )}
    </div>
  );

  return (
    <BotGame
      startFen={target.fen}
      elo={BOT_ELO}
      color={human}
      book={book}
      onHistoryChange={setHistory}
      onFinished={onFinished}
      storageKey={`endgame:${target.source}:${target.key}:${attempt}`}
      verdict={finished ? verdict : null}
      arrows={arrows}
      focus={focus}
      hideAnalyze
      aside={aside}
      pgnHeaders={{ Event: target.name }}
    />
  );
}

function TbBar({ title, text, wdl }: { title: string; text: string; wdl: Wdl | null }) {
  const tone =
    wdl === "win" ? "bg-green text-white" : wdl === "loss" ? "bg-danger/90 text-white" : wdl === "draw" ? "bg-raised text-ink" : "bg-sunken text-soft";
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg bg-sunken/60 px-3 py-2" aria-live="polite">
      <span className="text-xs font-bold tracking-wide text-muted uppercase">{title}</span>
      <span className={`rounded-md px-2.5 py-1 text-sm font-extrabold ${tone}`}>{text}</span>
    </div>
  );
}
