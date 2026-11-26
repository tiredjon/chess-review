"use client";

import { Chess } from "chess.js";
import Link from "next/link";
import { useCallback, useMemo } from "react";
import { Chessboard, type Arrow, type SquareRenderer } from "react-chessboard";
import { sideToMove } from "@/lib/chess";
import { CLASS_COLORS } from "@/lib/classes";
import { formatDate } from "@/lib/format";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { FindingExample } from "@/lib/insights-api";
import { useBoardTheme } from "../board-theme";
import { ClassBadge } from "../review/class-badge";

// Лучший ход — как на доске разбора (`review.tsx`).
const BEST_ARROW = "rgba(92, 168, 222, 0.85)";

function squares(fen: string, san: string | null): { from: string; to: string } | null {
  if (!san) return null;
  try {
    const move = new Chess(fen).move(san);
    return { from: move.from, to: move.to };
  } catch {
    return null;
  }
}

/** Миниатюра примера (как «Блестящие ходы» в /stats): позиция до хода, сыгранный ход — цветом
 *  класса, лучший — стрелкой; клик — разбор партии на этом ходу. */
export function ExampleBoard({ example }: { example: FindingExample }) {
  const { t, lang } = useI18n();
  const boardTheme = useBoardTheme();
  const color = sideToMove(example.fen_before);
  const fullmove = Number(example.fen_before.split(" ")[5] ?? 1);
  const label = `${fullmove}${color === "white" ? "." : "…"} ${example.san}`;
  const classColor = CLASS_COLORS[example.move_class] ?? CLASS_COLORS.mistake;
  const played = useMemo(() => squares(example.fen_before, example.san), [example.fen_before, example.san]);
  const best = useMemo(() => squares(example.fen_before, example.best_san), [example.fen_before, example.best_san]);

  const arrows = useMemo(() => {
    const list: Arrow[] = [];
    if (best && (best.from !== played?.from || best.to !== played?.to)) {
      list.push({ startSquare: best.from, endSquare: best.to, color: BEST_ARROW });
    }
    return list;
  }, [best, played]);

  const squareRenderer = useCallback<SquareRenderer>(
    ({ square, children }) => (
      <div style={{ position: "relative", width: "100%", height: "100%" }}>
        {played && (square === played.from || square === played.to) && (
          <span aria-hidden className="pointer-events-none absolute inset-0" style={{ background: `${classColor}99` }} />
        )}
        <div style={{ position: "relative", width: "100%", height: "100%" }}>{children}</div>
        {played && square === played.to && (
          <span className="pointer-events-none absolute -top-[18%] -right-[18%] z-30 w-[56%] drop-shadow-[0_1px_1px_rgba(0,0,0,0.45)]">
            <ClassBadge value={example.move_class} size="100%" title={false} />
          </span>
        )}
      </div>
    ),
    [played, classColor, example.move_class],
  );

  return (
    <Link
      href={`/games/${example.game_id}?ply=${example.ply}`}
      aria-label={t.insights.open(label, example.opponent)}
      className="group flex min-w-0 flex-col overflow-hidden rounded-lg bg-raised/60 hover:bg-raised"
    >
      <div className="pointer-events-none aspect-square">
        <Chessboard
          options={{
            id: `insight-${example.game_id}-${example.ply}`,
            position: example.fen_before,
            boardOrientation: color,
            showNotation: false,
            allowDragging: false,
            showAnimations: false,
            arrows,
            squareRenderer,
            ...boardTheme,
          }}
        />
      </div>
      <div className="flex min-w-0 flex-col gap-0.5 p-2 text-xs">
        <span className="truncate font-extrabold" style={{ color: classColor }}>
          {label}
          {example.best_san && example.best_san !== example.san && (
            <span className="font-semibold text-soft"> · {t.insights.best(example.best_san)}</span>
          )}
        </span>
        <span className="truncate font-semibold text-soft group-hover:text-ink">{t.stats.versus(example.opponent)}</span>
        <span className="text-muted">{formatDate(example.played_at, lang)}</span>
      </div>
    </Link>
  );
}
