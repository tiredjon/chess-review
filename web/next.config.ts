import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  // Данные страниц грузятся в браузере, мгновенной навигации тут не бывает: проверку
  // instant (плашка «Insight» и ошибки в консоли на каждой странице) — только где
  // `instant` задан явно. Индикатор dev-режима скрыт; ошибки сборки и рантайма видны.
  experimental: {
    instantInsights: { validationLevel: "manual-warning" },
  },
  devIndicators: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
