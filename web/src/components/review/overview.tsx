"use client";

import { useEffect, useState } from "react";
import { shownAccuracy } from "@/lib/accuracy";
import { CLASS_COLORS, CLASS_ORDER, classPlural, displayClass, phaseClass, type ClassKey } from "@/lib/classes";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { AnalysisOut, Color, GameDetail, Phase } from "@/lib/types";
import { PlayerAvatar } from "../player-avatar";
import { ClassBadge } from "./class-badge";

const COLORS: Color[] = ["white", "black"];
const PHASES: Phase[] = ["opening", "middlegame", "endgame"];
const ROW = "grid grid-cols-[minmax(0,1fr)_5.5rem_2rem_5.5rem] items-center gap-x-2";

/** Обзор партии: игроки, точность, ходы по классам, фазы. */
export function Overview({ game, analysis }: { game: GameDetail; analysis: AnalysisOut }) {
  const { t } = useI18n();
  const counts: Record<Color, Map<ClassKey, number>> = { white: new Map(), black: new Map() };
  for (const move of analysis.moves) {
    const value = displayClass(move);
    counts[move.color].set(value, (counts[move.color].get(value) ?? 0) + 1);
  }
  const accuracy = { white: shownAccuracy(game, "white"), black: shownAccuracy(game, "black") };
  const official = accuracy.white?.official && accuracy.black?.official;
  const name = { white: game.white, black: game.black };

  return (
    <div className="flex flex-col text-[15px] font-bold">
      <div className={`${ROW} pb-2`}>
        <span className="text-soft">{t.review.players}</span>
        {COLORS.map((color) => (
          <span key={color} className={`flex flex-col items-center gap-1.5 ${color === "black" ? "col-start-4" : ""}`}>
            <span className="max-w-full truncate text-xs text-soft">{name[color]}</span>
            <span className={game.user_color === color ? "rounded-lg ring-3 ring-green" : ""}>
              <PlayerAvatar name={name[color]} color={color} size={48} />
            </span>
          </span>
        ))}
      </div>

      <div className={`${ROW} pb-3`}>
        <span className="text-soft">{t.review.accuracy}</span>
        {COLORS.map((color) => (
          <span
            key={color}
            className={`justify-self-center rounded-lg px-3 py-2 text-lg font-extrabold ${
              color === "white" ? "bg-white text-[#2c2925]" : "col-start-4 bg-raised text-ink"
            }`}
          >
            {accuracy[color] == null ? "—" : <CountUp value={accuracy[color].value} />}
          </span>
        ))}
        {accuracy.white && (
          <span className="col-span-4 pt-1.5 text-xs font-semibold text-muted">
            {official ? t.review.accuracyOfficialNote : t.review.accuracyFormulaNote}
          </span>
        )}
      </div>

      {game.group_accuracy && (
        <div className={`${ROW} pb-3`}>
          <span className="text-soft">{t.review.groupAccuracy}</span>
          {COLORS.map((color) => {
            const value = game.group_accuracy?.[color];
            const elo = color === "white" ? game.white_elo : game.black_elo;
            return (
              <span
                key={color}
                title={elo ? t.review.groupAccuracyHint(elo) : undefined}
                className={`justify-self-center text-base font-extrabold text-soft ${color === "black" ? "col-start-4" : ""}`}
              >
                {value == null ? "—" : value.toFixed(1)}
              </span>
            );
          })}
        </div>
      )}

      <hr className="my-2 border-line" />

      <ul aria-label={t.review.movesByClass}>
        {CLASS_ORDER.map((key, i) => {
          const color = CLASS_COLORS[key];
          return (
            <li key={key} className={`${ROW} cc-rise py-1.5`} style={{ animationDelay: `${150 + i * 45}ms` }}>
              <span className="text-soft">{classPlural(t, key)}</span>
              <span className="text-center" style={{ color }}>
                {counts.white.get(key) ?? 0}
              </span>
              <span className="flex justify-center">
                <ClassBadge value={key} size={26} />
              </span>
              <span className="text-center" style={{ color }}>
                {counts.black.get(key) ?? 0}
              </span>
            </li>
          );
        })}
      </ul>

      <hr className="my-2 border-line" />

      {game.game_rating && (
        <div className={`${ROW} py-1.5`} title={t.review.gameRatingHint}>
          <span className="text-soft">{t.review.gameRating}</span>
          {COLORS.map((color) => (
            <span
              key={color}
              className={`justify-self-center rounded-lg px-3 py-2 text-lg font-extrabold ${
                color === "white" ? "bg-white text-[#2c2925]" : "col-start-4 bg-raised text-ink"
              }`}
            >
              {game.game_rating?.[color] ?? "—"}
            </span>
          ))}
        </div>
      )}


      <dl>
        {PHASES.map((phase) => (
          <div key={phase} className={`${ROW} py-1.5`}>
            <dt className="text-soft">{t.common.phases[phase]}</dt>
            {COLORS.map((color) => {
              const value = analysis.phase_accuracy?.[color]?.[phase];
              return (
                <dd
                  key={color}
                  className={`flex items-center justify-center gap-1.5 ${color === "black" ? "col-start-4" : ""}`}
                >
                  {value == null ? (
                    <span className="text-muted">—</span>
                  ) : (
                    <>
                      <ClassBadge value={phaseClass(value)} size={22} />
                      <span className="text-sm text-soft">{value.toFixed(0)}</span>
                    </>
                  )}
                </dd>
              );
            })}
          </div>
        ))}
      </dl>
      {analysis.engine_version && (
        <p className="pt-2 text-xs font-semibold text-muted">
          {t.review.engineNote(analysis.engine_version, analysis.runner, analysis.depth)}
        </p>
      )}
    </div>
  );
}

const COUNT_MS = 900;

const reducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Число, «набегающее» от 0 до значения (как точность в обзоре Chess.com). */
function CountUp({ value }: { value: number }) {
  const [shown, setShown] = useState(() => (reducedMotion() ? value : 0));
  useEffect(() => {
    if (reducedMotion()) return;
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / COUNT_MS);
      setShown(value * (1 - (1 - t) ** 3));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return <>{shown.toFixed(1)}</>;
}
