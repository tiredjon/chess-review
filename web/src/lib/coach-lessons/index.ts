// Тексты уроков тренера (сессия 17.1): по ключу урока (`GapOut.lesson`, `GET /coach/lessons`)
// — RU и EN. Ключи — `LESSONS` из `backend/app/coach/lessons.py`: мотивы (`MotifType`), фазы и
// навыки, статьи по книгам Ласкера и Капабланки (`book_*`, позиции — `app/books/lessons.py`).
// `Record<LessonKey, …>` — компилятор не даст забыть урок на одном из языков.
import type { Lang } from "@/lib/i18n";

import { EN } from "./en";
import { RU } from "./ru";

export type LessonSection = { heading: string; body: string };
/** Источник статьи по книге и короткая цитата автора (в оригинале, книги — общественное достояние). */
export type LessonSource = { ref: string; quote?: { text: string; author: string } };
export type LessonText = { title: string; summary: string; sections: LessonSection[]; source?: LessonSource };

export const MOTIF_LESSONS = [
  "hanging_piece",
  "fork",
  "pin",
  "skewer",
  "discovered_attack",
  "discovered_check",
  "double_check",
  "mate_in_n",
  "mate_threat",
  "back_rank",
  "trapped_piece",
  "removing_defender",
  "overload",
  "promotion",
  "promotion_threat",
] as const;
export const PHASE_LESSONS = ["opening_principles", "middlegame_plans", "endgame_technique"] as const;
export const SKILL_LESSONS = [
  "blunder_check",
  "tactical_vision",
  "converting_advantage",
  "defense",
  "time_management",
  "opening_repertoire",
] as const;

export const BOOK_LESSONS = [
  "book_attack_targets",
  "book_king_pawns",
  "book_open_files",
  "book_pawn_weaknesses",
  "book_initiative",
  "book_cut_off_pieces",
  "book_endgame_king",
  "book_rook_endings",
] as const;

export type LessonKey =
  | (typeof MOTIF_LESSONS)[number]
  | (typeof PHASE_LESSONS)[number]
  | (typeof SKILL_LESSONS)[number]
  | (typeof BOOK_LESSONS)[number];

/** Идея позиции курса (`app/plans/ideas.py`) → статья по книге на эту тему. */
export const IDEA_LESSONS: Record<string, (typeof BOOK_LESSONS)[number]> = {
  king_holes: "book_king_pawns",
  trade_king_bishop: "book_king_pawns",
  pawn_hook: "book_king_pawns",
  opposite_castling: "book_king_pawns",
  rook_seventh: "book_open_files",
  rook_to_seventh: "book_open_files",
  rook_open_file: "book_open_files",
  rook_open_files: "book_open_files",
  rook_half_open: "book_open_files",
  target_backward: "book_attack_targets",
  target_isolated: "book_attack_targets",
  outpost: "book_attack_targets",
  outpost_knight: "book_attack_targets",
  blockade: "book_attack_targets",
  target_doubled: "book_pawn_weaknesses",
  majority: "book_pawn_weaknesses",
  knight_rim: "book_cut_off_pieces",
  bad_bishop: "book_cut_off_pieces",
  passed_pawn: "book_endgame_king",
};

export type LessonTexts = Record<LessonKey, LessonText>;

export const LESSONS: Record<Lang, LessonTexts> = { ru: RU, en: EN };

export const lessonText = (lang: Lang, key: string): LessonText | null =>
  (LESSONS[lang] as Record<string, LessonText>)[key] ?? null;
