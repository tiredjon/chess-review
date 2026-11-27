// Тексты уроков тренера (сессия 17.1): по ключу урока (`GapOut.lesson`, `GET /coach/lessons`)
// — RU и EN. Ключи — `LESSONS` из `backend/app/coach/lessons.py`: мотивы (`MotifType`), фазы и
// навыки. `Record<LessonKey, …>` — компилятор не даст забыть урок на одном из языков.
import type { Lang } from "@/lib/i18n";

import { EN } from "./en";
import { RU } from "./ru";

export type LessonSection = { heading: string; body: string };
export type LessonText = { title: string; summary: string; sections: LessonSection[] };

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

export type LessonKey =
  | (typeof MOTIF_LESSONS)[number]
  | (typeof PHASE_LESSONS)[number]
  | (typeof SKILL_LESSONS)[number];

export type LessonTexts = Record<LessonKey, LessonText>;

export const LESSONS: Record<Lang, LessonTexts> = { ru: RU, en: EN };

export const lessonText = (lang: Lang, key: string): LessonText | null =>
  (LESSONS[lang] as Record<string, LessonText>)[key] ?? null;
