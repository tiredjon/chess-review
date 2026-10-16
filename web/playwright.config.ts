import { defineConfig } from "@playwright/test";

// Smoke-тест сквозь весь стек (e2e/smoke.spec.ts): нужен поднятый `make up` — web, API,
// воркер со Stockfish. Тест не поднимает серверы сам. Браузер — установленный Google Chrome
// (E2E_CHANNEL=chrome); пустой E2E_CHANNEL — Chromium Playwright (`npx playwright install chromium`).
export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  outputDir: "./e2e/.results",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    channel: process.env.E2E_CHANNEL ?? "chrome",
    locale: "ru-RU",
    viewport: { width: 1280, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
