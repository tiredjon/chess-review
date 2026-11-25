"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { START_FEN } from "@/lib/chess";
import { coursesApi } from "@/lib/courses-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { AnalysisOut, Color, GameDetail, MoveOut } from "@/lib/types";
import { Button, ErrorText } from "../ui";
import { ClassBadge } from "./class-badge";
import { Figurine } from "./move-list";

/** Линия дебюта партии: первые подряд книжные ходы (`book` ставится до 15-го хода,
 * как `OpeningsDB.book_plies` в фазах). Переход обратно в книгу после выхода не считается —
 * курс учит позицию, где партия ушла из теории. */
export function bookLine(moves: MoveOut[]): MoveOut[] {
  const end = moves.findIndex((move) => move.class !== "book");
  return end === -1 ? moves : moves.slice(0, end);
}

/** Карточка обзора «Дебют партии»: линия до выхода из книги и «Тренировать эту линию» —
 * курс (как «Учить эту линию» в репертуаре) за цвет пользователя в партии. */
export function TrainLine({ game, analysis }: { game: GameDetail; analysis: AnalysisOut }) {
  const { t } = useI18n();
  const router = useRouter();
  const [busy, setBusy] = useState<Color | null>(null);
  const [error, setError] = useState<string | null>(null);

  const line = bookLine(analysis.moves);
  // Партия не из начальной позиции (Chess960, FEN) — курс не построить.
  if (line.length === 0 || line[0].fen_before !== START_FEN) return null;

  const train = async (color: Color) => {
    setBusy(color);
    setError(null);
    try {
      // Имя не передаём: сервер берёт самую глубокую названную позицию линии, а
      // `opening_name` партии могло прийти и после выхода из книги (переход в теорию).
      const course = await coursesApi.create({ line_uci: line.map((move) => move.uci), color, source: "repertoire" });
      router.push(`/openings/courses/${course.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.review.train.error);
      setBusy(null);
    }
  };

  // Цвет пользователя неизвестен (вставленный PGN без ника) — выбор стороны.
  const colors: Color[] = game.user_color ? [game.user_color] : ["white", "black"];
  const exit = analysis.moves.at(line.length);
  const exitBy = !exit || !game.user_color ? null : exit.color === game.user_color ? "you" : "opponent";

  return (
    <section aria-labelledby="train-line-title" className="flex flex-col gap-2.5 rounded-xl bg-sunken/60 p-3">
      <div className="flex items-center gap-2">
        <ClassBadge value="book" size={22} />
        <h2 id="train-line-title" className="min-w-0 flex-1 truncate text-[15px] font-extrabold">
          {game.opening_name ?? t.review.train.title}
        </h2>
      </div>
      {/* Перенос — между ходами, номер хода не отрывается от хода белых. */}
      <p className="flex flex-wrap gap-x-1.5 gap-y-0.5 text-sm font-semibold text-soft">
        {line.map((move) => (
          <span key={move.ply} className="whitespace-nowrap">
            {move.color === "white" && <span className="text-muted">{move.fullmove}. </span>}
            <Figurine san={move.san} color={move.color} />
          </span>
        ))}
      </p>
      <p className="text-xs font-semibold text-muted">
        {exit ? t.review.train.exit(exit.fullmove, exitBy) : t.review.train.allBook}{" "}
        {t.review.train.hint}
      </p>
      <div className="flex gap-2">
        {colors.map((color) => (
          <Button key={color} onClick={() => void train(color)} disabled={busy !== null} className="flex-1">
            {busy === color
              ? t.review.train.busy
              : game.user_color
                ? t.review.train.button
                : t.review.train.forColor[color]}
          </Button>
        ))}
      </div>
      <ErrorText>{error}</ErrorText>
    </section>
  );
}
