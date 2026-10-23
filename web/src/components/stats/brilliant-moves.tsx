"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { Chessboard, type SquareRenderer } from "react-chessboard";
import { applyUci, uciSquares } from "@/lib/chess";
import { CLASS_COLORS } from "@/lib/classes";
import { formatDate } from "@/lib/format";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { BrilliantMove, Stats } from "@/lib/types";
import { useBoardTheme } from "../board-theme";
import { ClassBadge } from "../review/class-badge";
import { Panel } from "../ui";

// Досок сначала и за одно «Показать ещё»: сотня Chessboard разом тормозит страницу.
const FIRST = 6;
const STEP = 12;

/** Раздел «Блестящие ходы» (как Brilliant moves у Chess.com): позиция после хода,
 *  клик — разбор партии на этом ходу. */
export function BrilliantMoves({ stats }: { stats: Stats }) {
  const { t } = useI18n();
  const labels = t.stats.brilliant;
  const { count, games, moves } = stats.brilliant;
  const [shown, setShown] = useState(FIRST);
  const rest = Math.min(STEP, moves.length - shown);
  return (
    <Panel
      title={
        <span className="flex items-center gap-2">
          <span aria-hidden className="flex">
            <ClassBadge value="brilliant" size={22} title={false} />
          </span>
          {labels.title}
        </span>
      }
      aside={count > 0 && <span className="text-xs font-semibold text-muted">{labels.summary(count, games)}</span>}
    >
      {moves.length === 0 ? (
        <p className="text-soft">{labels.none}</p>
      ) : (
        <>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {moves.slice(0, shown).map((move) => (
              <li key={move.move_id}>
                <BrilliantCard move={move} />
              </li>
            ))}
          </ul>
          {rest > 0 && (
            <button
              type="button"
              onClick={() => setShown((n) => n + STEP)}
              className="mt-4 flex min-h-11 w-full items-center justify-center rounded-lg bg-raised text-sm font-bold text-soft hover:bg-raised-hover hover:text-ink"
            >
              {labels.more(rest)}
            </button>
          )}
          {count > moves.length && shown >= moves.length && (
            <p className="mt-3 text-xs text-muted">{labels.limited(moves.length)}</p>
          )}
        </>
      )}
    </Panel>
  );
}

function BrilliantCard({ move }: { move: BrilliantMove }) {
  const { t, lang } = useI18n();
  const boardTheme = useBoardTheme();
  const { from, to } = uciSquares(move.uci);
  const label = `${move.fullmove}${move.color === "white" ? "." : "…"} ${move.san}`;
  const highlight = `${CLASS_COLORS.brilliant}99`;

  const squareRenderer = useCallback<SquareRenderer>(
    ({ square, children }) => (
      <div style={{ position: "relative", width: "100%", height: "100%" }}>
        {(square === from || square === to) && (
          <span aria-hidden className="pointer-events-none absolute inset-0" style={{ background: highlight }} />
        )}
        <div style={{ position: "relative", width: "100%", height: "100%" }}>{children}</div>
        {square === to && (
          <span className="pointer-events-none absolute -top-[18%] -right-[18%] z-30 w-[56%] drop-shadow-[0_1px_1px_rgba(0,0,0,0.45)]">
            <ClassBadge value="brilliant" size="100%" title={false} />
          </span>
        )}
      </div>
    ),
    [from, to, highlight],
  );

  return (
    <Link
      href={`/games/${move.game_id}?ply=${move.ply}`}
      aria-label={t.stats.brilliant.open(label, move.opponent)}
      className="group flex flex-col overflow-hidden rounded-lg bg-raised/60 hover:bg-raised"
    >
      <div className="pointer-events-none aspect-square">
        <Chessboard
          options={{
            id: `brilliant-${move.move_id}`,
            position: applyUci(move.fen_before, move.uci) ?? move.fen_before,
            boardOrientation: move.color,
            showNotation: false,
            allowDragging: false,
            showAnimations: false,
            squareRenderer,
            ...boardTheme,
          }}
        />
      </div>
      <div className="flex flex-col gap-0.5 p-2 text-xs">
        <span className="font-extrabold" style={{ color: CLASS_COLORS.brilliant }}>
          {label}
        </span>
        <span className="truncate font-semibold text-soft group-hover:text-ink">{t.stats.versus(move.opponent)}</span>
        <span className="text-muted">
          {[formatDate(move.played_at, lang), move.outcome && t.common.outcome[move.outcome]].filter(Boolean).join(" · ")}
        </span>
      </div>
    </Link>
  );
}
