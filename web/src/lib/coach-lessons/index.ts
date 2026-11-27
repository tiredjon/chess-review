// Тексты уроков тренера (сессия 17.2): по ключу урока (`GapOut.lesson`, `GET /coach/lessons`)
// — RU и EN. Фундамент: пусто; наполняет 17.2, показывает 17.3.
import type { Lang } from "@/lib/i18n";

export type LessonSection = { heading: string; body: string };
export type LessonText = { title: string; summary: string; sections: LessonSection[] };

export const LESSONS: Record<Lang, Record<string, LessonText>> = { ru: {}, en: {} };

export const lessonText = (lang: Lang, key: string): LessonText | null => LESSONS[lang][key] ?? null;
