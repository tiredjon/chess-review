"use client";

import { createContext, useContext } from "react";
import { api } from "@/lib/api";
import type { Lang } from "@/lib/i18n";
import type { MoveExplanation, Summary } from "@/lib/types";

/**
 * Откуда экран разбора берёт объяснения и итог: своя партия (язык — из профиля) или
 * публичная ссылка `/share/{token}` (без входа, язык — интерфейса гостя).
 */
export type ReviewSource = {
  explainMove: (moveId: number, lang: Lang) => Promise<MoveExplanation>;
  summary: (analysisId: string, lang: Lang) => Promise<Summary>;
};

const OWN: ReviewSource = {
  explainMove: (moveId) => api.explainMove(moveId),
  summary: (analysisId) => api.summary(analysisId),
};

export function sharedSource(token: string): ReviewSource {
  return {
    explainMove: (moveId, lang) => api.shared.explainMove(token, moveId, lang),
    summary: (_analysisId, lang) => api.shared.summary(token, lang),
  };
}

const ReviewSourceContext = createContext<ReviewSource>(OWN);

export const ReviewSourceProvider = ReviewSourceContext.Provider;

export function useReviewSource(): ReviewSource {
  return useContext(ReviewSourceContext);
}
