"use client";

// Партия с ботом Stockfish (сессия 14.2): доска за цвет человека, ход кликом и перетаскиванием,
// превращение с выбором фигуры, книга соперника (курс), сдача, взять ход назад, просмотр прошлых
// позиций, итог с PGN и «Разобрать партию». Контракт props — `./types` (им пользуется 14.3).
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useEffectEvent, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useUser } from "../auth/auth-provider";
import { createBot, type Bot } from "@/lib/bots";
import { boardMoveUci, pieceOn, sideToMove, uciSquares } from "@/lib/chess";
import { useI18n } from "@/lib/i18n/use-i18n";
import { playMove, playSound, preloadSounds, toggleMuted, useSoundMuted } from "@/lib/sounds";
import type { Color } from "@/lib/types";
import { Board, type BoardMarks } from "../review/board";
import { CoachBubble } from "../review/summary";
import { Button, ErrorText } from "../ui";
import { levelOf } from "./bot-picker";
import {
  buildResult,
  checkedKing,
  isLegal,
  isPromotion,
  material,
  opposite,
  pawnOnTarget,
  replay,
  targets,
} from "./game";
import { IconButton, MoveList, MoveNav, PlayerBar, PromotionPicker, ResultModal, Thinking } from "./parts";
import type { BotGameProps, GameEndReason, GameResult } from "./types";

// Ход книги (линия курса) — с паузой, как будто соперник подумал; бот держит паузу сам.
const BOOK_DELAY_MS = 550;
// Доска и две полосы игроков — в экран (как в разборе).
const BOARD_WIDTH = { maxWidth: "min(100%, calc(100dvh - 8.5rem))" };

const LAST_MOVE = "rgba(247, 214, 92, 0.6)";
const SELECTED = "rgba(127, 176, 74, 0.6)";
const CHECK = "radial-gradient(circle, rgba(255, 0, 0, 0.95) 0%, rgba(231, 0, 0, 0.6) 30%, rgba(169, 0, 0, 0) 68%)";
const DOT = "radial-gradient(circle, rgba(0, 0, 0, 0.16) 21%, transparent 23%)";
const RING = "radial-gradient(circle, transparent 74%, rgba(0, 0, 0, 0.16) 76%, rgba(0, 0, 0, 0.16) 92%, transparent 94%)";

const STORAGE = "chess-review:bot-game";
type Saved = { key: string; elo: number; color: Color; moves: string[] };

function restore(key: string | undefined, elo: number, color: Color): string[] {
  if (!key) return [];
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE) ?? "null") as Saved | null;
    if (!saved || saved.key !== key || saved.elo !== elo || saved.color !== color || !Array.isArray(saved.moves)) return [];
    const game = replay(saved.moves.filter((move) => typeof move === "string"));
    // Законченную партию не восстанавливаем — она уже в итоге.
    return game.end ? [] : game.moves;
  } catch {
    return [];
  }
}

function save(value: Saved | null) {
  try {
    if (value) sessionStorage.setItem(STORAGE, JSON.stringify(value));
    else sessionStorage.removeItem(STORAGE);
  } catch {
    // Хранилище недоступно (приватный режим) — партия просто не переживёт перезагрузку.
  }
}

const wait = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("aborted", "AbortError"));
    });
  });

/** Цвет полуода с номером `index` (партия всегда с начальной позиции). */
const plyColor = (index: number): Color => (index % 2 === 0 ? "white" : "black");

type Engine = { key: string; bot: Bot | null; error: boolean };

export function BotGame({
  elo,
  color,
  book,
  onPlayerMove,
  onFinished,
  onNewGame,
  onChangeBot,
  aside,
  pgnHeaders,
  storageKey,
}: BotGameProps) {
  const { t } = useI18n();
  const router = useRouter();
  const user = useUser();
  // Имя в PGN — ник пользователя: по нему бэкенд узнаёт его цвет в импортированной партии.
  const pgnName = user.chesscom_username || user.lichess_username || t.play.you;
  const muted = useSoundMuted();

  const [moves, setMoves] = useState<string[]>(() => restore(storageKey, elo, color));
  /** Показанная позиция (число сыгранных полуходов); null — текущая. */
  const [view, setView] = useState<number | null>(null);
  const [orientation, setOrientation] = useState<Color>(color);
  const [selected, setSelected] = useState<string | null>(null);
  const [promotion, setPromotion] = useState<{ from: string; to: string } | null>(null);
  const [result, setResult] = useState<GameResult | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [confirmResign, setConfirmResign] = useState(false);
  const [review, setReview] = useState<{ busy: boolean; error: string | null }>({ busy: false, error: null });

  // Бот — один на партию: создаётся при монтировании (и по «Повторить»), освобождается при уходе.
  const [attempt, setAttempt] = useState(0);
  const [engine, setEngine] = useState<Engine | null>(null);
  const engineKey = `${elo}:${attempt}`;
  useEffect(() => {
    let cancelled = false;
    let created: Bot | null = null;
    createBot(elo)
      .then((bot) => {
        if (cancelled) {
          bot.dispose();
          return;
        }
        created = bot;
        setEngine({ key: engineKey, bot, error: false });
      })
      .catch(() => {
        if (!cancelled) setEngine({ key: engineKey, bot: null, error: true });
      });
    return () => {
      cancelled = true;
      created?.dispose();
    };
  }, [elo, engineKey]);
  const current = engine?.key === engineKey ? engine : null;
  const bot = current?.bot ?? null;
  const engineError = current?.error ?? false;

  useEffect(preloadSounds, []);

  const game = useMemo(() => replay(moves), [moves]);
  const total = game.moves.length;
  const liveFen = game.fens[total];
  const shown = view === null ? total : Math.min(view, total);
  const live = shown === total;
  const turn = sideToMove(liveFen);
  const over = result !== null || game.end !== null;
  const canMove = live && turn === color && !over && promotion === null;
  const thinking = bot !== null && !engineError && turn !== color && !over;

  // Ходы — в sessionStorage, пока партия идёт.
  useEffect(() => {
    if (!storageKey) return;
    save(result || game.end ? null : { key: storageKey, elo, color, moves: game.moves });
  }, [storageKey, elo, color, game, result]);

  const botName = t.play.botName(elo);

  const finish = useCallback(
    (history: readonly string[], reason: GameEndReason, winner: Color | null) => {
      const finished = buildResult({
        moves: history,
        reason,
        winner,
        color,
        you: pgnName,
        botName,
        elo,
        event: t.play.pgnEvent,
        headers: pgnHeaders,
      });
      setResult(finished);
      setModalOpen(true);
      setConfirmResign(false);
      onFinished?.(finished);
    },
    [botName, color, elo, onFinished, pgnHeaders, pgnName, t.play.pgnEvent],
  );

  /** Сыграть ход (человека или бота) в конце партии `history`. */
  const commit = useCallback(
    (history: readonly string[], uci: string) => {
      const next = [...history, uci];
      const after = replay(next);
      if (after.moves.length !== next.length) return;
      const mover = plyColor(history.length);
      playMove(after.sans[after.sans.length - 1], mover, color, after.end !== null);
      setMoves(next);
      setView(null);
      setSelected(null);
      setPromotion(null);
      if (mover === color) onPlayerMove?.(next);
      if (after.end) finish(next, after.end.reason, after.end.winner);
    },
    [color, finish, onPlayerMove],
  );

  // Ход бота: сначала книга (линия курса), если её ход легален, иначе — сам бот.
  // Любое изменение партии (взять назад, новая позиция) отменяет идущий поиск.
  const bookMove = useEffectEvent((history: readonly string[]) => book?.(history) ?? null);
  const playBotMove = useEffectEvent((history: readonly string[], uci: string) => commit(history, uci));
  useEffect(() => {
    if (!bot || over || turn === color) return;
    const controller = new AbortController();
    const { signal } = controller;
    const history = game.moves;
    const fen = liveFen;
    (async () => {
      let uci = bookMove(history);
      if (uci && isLegal(fen, uci)) await wait(BOOK_DELAY_MS, signal);
      else uci = (await bot.move({ fen, historyUci: history, signal })).uci;
      if (signal.aborted) return;
      if (!isLegal(fen, uci)) throw new Error(`illegal bot move ${uci}`);
      playBotMove(history, uci);
    })().catch((error: unknown) => {
      if (signal.aborted) return;
      console.error("bot move failed", error);
      setEngine({ key: engineKey, bot: null, error: true });
    });
    return () => controller.abort();
  }, [bot, over, turn, color, game, liveFen, engineKey]);

  const tryMove = useCallback(
    (from: string, to: string): boolean => {
      if (!canMove) return false;
      if (isPromotion(liveFen, from, to)) {
        setPromotion({ from, to });
        setSelected(null);
        return true;
      }
      const uci = boardMoveUci(liveFen, from, to);
      if (!uci) {
        playSound("illegal");
        setSelected(null);
        return false;
      }
      commit(game.moves, uci);
      return true;
    },
    [canMove, commit, game.moves, liveFen],
  );

  const selectedTargets = useMemo(() => (selected ? targets(liveFen, selected) : new Map<string, boolean>()), [liveFen, selected]);

  const onSquareClick = useCallback(
    (square: string) => {
      if (!canMove) return;
      if (selected && selectedTargets.has(square)) {
        tryMove(selected, square);
        return;
      }
      const piece = pieceOn(liveFen, square);
      const own = piece !== null && (piece === piece.toUpperCase()) === (color === "white");
      setSelected(own && square !== selected ? square : null);
    },
    [canMove, color, liveFen, selected, selectedTargets, tryMove],
  );

  const choosePromotion = (piece: "q" | "n" | "r" | "b") => {
    if (!promotion) return;
    commit(game.moves, `${promotion.from}${promotion.to}${piece}`);
  };
  const cancelPromotion = useCallback(() => setPromotion(null), []);

  // Взять назад: до последнего хода человека (вместе с ответом бота или его идущим поиском).
  let takebackTo = -1;
  for (let index = total - 1; index >= 0; index -= 1) {
    if (plyColor(index) === color) {
      takebackTo = index;
      break;
    }
  }
  const canTakeback = takebackTo >= 0 && result === null && game.end === null;
  const takeback = () => {
    if (!canTakeback) return;
    setMoves(game.moves.slice(0, takebackTo));
    setView(null);
    setSelected(null);
    setPromotion(null);
  };

  const resign = () => {
    if (over) return;
    playSound("game-end");
    finish(game.moves, "resign", opposite(color));
  };

  const go = useCallback(
    (plies: number) => {
      const target = Math.max(0, Math.min(total, plies));
      setView(target === total ? null : target);
      setSelected(null);
    },
    [total],
  );

  const flip = useCallback(() => setOrientation((side) => opposite(side)), []);

  // Клавиши: ← → — по ходам, Home / End, F — перевернуть, M — звук.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
      if (event.key === "ArrowLeft") go(shown - 1);
      else if (event.key === "ArrowRight") go(shown + 1);
      else if (event.key === "Home") go(0);
      else if (event.key === "End") go(total);
      else if (["f", "F", "а", "А"].includes(event.key)) flip();
      else if (["m", "M", "ь", "Ь"].includes(event.key)) toggleMuted();
      else return;
      event.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [flip, go, shown, total]);

  const analyze = async () => {
    if (!result || review.busy) return;
    setReview({ busy: true, error: null });
    try {
      const games = await api.importPgn(result.pgn);
      if (!games[0]) throw new Error("no game");
      router.push(`/games/${games[0].id}?analyze=1`);
    } catch (error) {
      setReview({ busy: false, error: error instanceof ApiError ? error.message : t.play.analyzeError });
    }
  };

  // Доска: позиция, подсветка последнего хода, шах, выбранная фигура и её ходы.
  const fen = promotion ? pawnOnTarget(liveFen, promotion.from, promotion.to) : game.fens[shown];
  const highlights: Record<string, string> = {};
  const last = promotion ? `${promotion.from}${promotion.to}` : shown > 0 ? game.moves[shown - 1] : null;
  if (last) {
    const { from, to } = uciSquares(last);
    highlights[from] = LAST_MOVE;
    highlights[to] = LAST_MOVE;
  }
  const king = promotion ? null : checkedKing(fen);
  if (king) highlights[king] = highlights[king] ? `${CHECK}, ${highlights[king]}` : CHECK;
  if (selected && live) {
    highlights[selected] = SELECTED;
    for (const [square, capture] of selectedTargets) {
      const mark = capture ? RING : DOT;
      highlights[square] = highlights[square] ? `${mark}, ${highlights[square]}` : mark;
    }
  }
  const marks: BoardMarks = {
    key: `${shown}-${last ?? ""}`,
    arrows: [],
    highlights,
    badge: null,
  };

  const materials = material(game.fens[shown]);
  const bar = (side: Color) =>
    side === color ? (
      <PlayerBar name={t.play.you} color={side} captured={materials[side].captured} advantage={materials[side].advantage} />
    ) : (
      <PlayerBar
        name={botName}
        elo={elo}
        color={side}
        captured={materials[side].captured}
        advantage={materials[side].advantage}
        status={
          thinking ? (
            <Thinking label={t.play.thinking} />
          ) : !bot && !engineError && !over ? (
            <span className="text-xs font-semibold text-muted">{t.play.loadingEngine}</span>
          ) : null
        }
      />
    );

  const soundLabel = muted ? t.play.soundOn : t.play.soundOff;
  const outcome = result ? (result.winner === null ? "draw" : result.winner === color ? "win" : "loss") : null;

  const resultActions = (
    <>
      <Button size="lg" onClick={analyze} disabled={review.busy} autoFocus>
        {review.busy ? t.play.analyzing : t.play.analyze}
      </Button>
      <ErrorText>{review.error}</ErrorText>
      {(onNewGame || onChangeBot) && (
        <div className={`grid gap-2 ${onNewGame && onChangeBot ? "grid-cols-2" : ""}`}>
          {onNewGame && (
            <Button variant="raised" onClick={onNewGame}>
              {t.play.newGame}
            </Button>
          )}
          {onChangeBot && (
            <Button variant="raised" onClick={onChangeBot}>
              {t.play.otherBot}
            </Button>
          )}
        </div>
      )}
    </>
  );

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
      <div className="mx-auto flex w-full flex-col gap-2" style={BOARD_WIDTH}>
        {bar(opposite(orientation))}
        <div className="relative">
          <Board
            fen={fen}
            orientation={orientation}
            marks={marks}
            interactive={canMove}
            onMove={tryMove}
            onSquareClick={onSquareClick}
          />
          {promotion && (
            <PromotionPicker
              square={promotion.to}
              color={color}
              orientation={orientation}
              onChoose={choosePromotion}
              onCancel={cancelPromotion}
            />
          )}
        </div>
        {bar(orientation)}
      </div>

      <section aria-label={t.play.title} className="flex min-w-0 flex-col rounded-xl bg-panel lg:h-0 lg:min-h-[max(100%,calc(100dvh-2rem))]">
        <header className="flex items-center gap-2 rounded-t-xl border-b border-line bg-sunken/60 px-4 py-3">
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-lg font-extrabold">{botName}</h2>
            <p className="text-xs font-semibold text-muted">{t.play.levels[levelOf(elo).key]}</p>
          </div>
          <IconButton label={t.play.flip} onClick={flip}>
            <svg aria-hidden viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M7 4v16M7 4 3.5 7.5M7 4l3.5 3.5M17 20V4m0 16-3.5-3.5M17 20l3.5-3.5" />
            </svg>
          </IconButton>
          <IconButton label={soundLabel} onClick={toggleMuted} pressed={muted}>
            <svg aria-hidden viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" fill="currentColor" />
              {muted ? <path d="m16 9.5 5 5m0-5-5 5" /> : <path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11" />}
            </svg>
          </IconButton>
        </header>

        <div className="flex flex-col gap-3 p-4">
          <StatusBanner
            outcome={outcome}
            text={
              result
                ? `${t.play.result[outcome!]} · ${t.play.result.reasons[result.reason]}`
                : turn === color
                  ? t.play.yourMove
                  : t.play.botMove
            }
            side={turn}
          />
          {engineError && (
            <div role="alert" className="flex flex-col gap-2 rounded-lg bg-danger/15 p-3">
              <p className="text-sm font-bold text-ink">{t.play.engineError}</p>
              <p className="text-sm text-soft">{t.play.engineErrorHint}</p>
              <Button variant="raised" size="sm" className="self-start" onClick={() => setAttempt((n) => n + 1)}>
                {t.play.retry}
              </Button>
            </div>
          )}
          {!live && !over && (
            <CoachBubble>
              {t.play.viewingPast}{" "}
              <button type="button" onClick={() => go(total)} className="font-bold text-green hover:underline">
                {t.play.toLive}
              </button>
            </CoachBubble>
          )}
          {aside}
        </div>

        <div className="flex min-h-0 flex-1 flex-col border-t border-line">
          <p className="px-4 pt-2.5 pb-1 text-xs font-bold tracking-wide text-muted uppercase">{t.play.moves}</p>
          <MoveList sans={game.sans} current={shown} onSelect={go} empty={color === "white" ? t.play.noMoves : t.play.noMovesBot} />
        </div>

        {/* На телефоне действия липнут к низу экрана, как в пазлах. */}
        <div className={`flex flex-col gap-2 rounded-b-xl border-t border-line bg-panel p-4 lg:static ${result ? "" : "sticky bottom-0"}`}>
          <MoveNav current={shown} total={total} onGo={go} />
          {result ? (
            resultActions
          ) : confirmResign ? (
            <div className="flex flex-col gap-2">
              <p className="text-center text-sm font-bold">{t.play.resignConfirm}</p>
              <div className="grid grid-cols-2 gap-2">
                <Button variant="raised" onClick={() => setConfirmResign(false)} autoFocus>
                  {t.play.cancel}
                </Button>
                <Button className="bg-danger! shadow-[0_4px_0_0_rgba(0,0,0,0.35)]! hover:brightness-110" onClick={resign}>
                  {t.play.resignYes}
                </Button>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <Button variant="raised" onClick={takeback} disabled={!canTakeback}>
                <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 14 4 9l5-5" />
                  <path d="M4 9h10a6 6 0 0 1 0 12h-3" />
                </svg>
                {t.play.takeback}
              </Button>
              <Button variant="raised" onClick={() => setConfirmResign(true)} disabled={over}>
                <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
                  <path d="M5 3h2v18H5zM8 4h11l-2.5 4L19 12H8z" />
                </svg>
                {t.play.resign}
              </Button>
            </div>
          )}
        </div>
      </section>

      {result && modalOpen && (
        <ResultModal result={result} color={color} elo={elo} onClose={() => setModalOpen(false)} actions={resultActions} />
      )}
    </div>
  );
}

function StatusBanner({ outcome, text, side }: { outcome: "win" | "loss" | "draw" | null; text: string; side: Color }) {
  const tone =
    outcome === "win"
      ? "bg-green text-white"
      : outcome === "loss"
        ? "bg-danger/90 text-white"
        : outcome === "draw"
          ? "bg-raised text-ink"
          : side === "white"
            ? "bg-white text-[#2c2925]"
            : "bg-sunken text-ink";
  return <div className={`rounded-lg px-4 py-3 text-lg font-extrabold ${tone}`}>{text}</div>;
}
