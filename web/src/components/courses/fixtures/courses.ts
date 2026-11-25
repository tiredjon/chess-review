// Dev-фикстуры «Моих курсов» (сессия 13.7) — только для фейкового API
// (`web/scripts/courses-mock-api.mjs`): в приложение не импортируются. Курс Найдорфа готов,
// остальные показывают сборку, очередь и ошибку.
import type { CourseOut } from "@/lib/courses-api";

export const NAJDORF_ID = "7d3f0a52-6b1e-4c1a-9d1e-0f13a7c00001";

export const fixtureCourses: CourseOut[] = [
  {
    id: NAJDORF_ID,
    name: "Sicilian Defense: Najdorf Variation",
    eco: "B90",
    color: "black",
    line_uci: ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4", "f3d4", "g8f6", "b1c3", "a7a6"],
    line_san: ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"],
    source: "catalog",
    status: "ready",
    progress: 100,
    error_code: null,
    added_at: "2026-11-20T18:12:00Z",
    last_studied_at: "2026-11-24T20:40:00Z",
    built_at: "2026-11-20T18:14:31Z",
  },
  {
    id: "7d3f0a52-6b1e-4c1a-9d1e-0f13a7c00002",
    name: "Sicilian Defense: Nyezhmetdinov-Rossolimo Attack",
    eco: "B31",
    color: "white",
    line_uci: ["e2e4", "c7c5", "g1f3", "b8c6", "f1b5"],
    line_san: ["e4", "c5", "Nf3", "Nc6", "Bb5"],
    source: "catalog",
    status: "building",
    progress: 35,
    error_code: null,
    added_at: "2026-11-25T09:00:00Z",
    last_studied_at: null,
    built_at: null,
  },
  {
    id: "7d3f0a52-6b1e-4c1a-9d1e-0f13a7c00003",
    name: "Queen's Gambit Declined",
    eco: "D30",
    color: "white",
    line_uci: ["d2d4", "d7d5", "c2c4", "e7e6"],
    line_san: ["d4", "d5", "c4", "e6"],
    source: "repertoire",
    status: "failed",
    progress: 40,
    error_code: "explorer_unavailable",
    added_at: "2026-11-23T12:00:00Z",
    last_studied_at: null,
    built_at: null,
  },
];
