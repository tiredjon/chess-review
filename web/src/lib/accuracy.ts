// Какую точность показывать: официальную Chess.com (есть у партий, разобранных там) или нашу
// «как у Chess.com» (приближение их формулы); формула Lichess — если старый анализ без неё.
import type { AnalysisSummary, Color, GameOut } from "./types";

export type ShownAccuracy = { value: number; official: boolean };

type WithAccuracy = Pick<GameOut, "source_white_accuracy" | "source_black_accuracy"> & {
  analysis: AnalysisSummary | null;
};

export function shownAccuracy(game: WithAccuracy, color: Color): ShownAccuracy | null {
  const official = color === "white" ? game.source_white_accuracy : game.source_black_accuracy;
  if (official != null) return { value: official, official: true };
  const analysis = game.analysis;
  if (analysis?.status !== "done") return null;
  const ours =
    (color === "white" ? analysis.cc_white_accuracy : analysis.cc_black_accuracy) ??
    (color === "white" ? analysis.white_accuracy : analysis.black_accuracy);
  return ours == null ? null : { value: ours, official: false };
}
