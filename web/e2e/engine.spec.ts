import { expect, test } from "@playwright/test";

// Сессия 11 сквозь стек: анализ движком в браузере (Stockfish WASM) → разбор на сервере →
// пазл по пробам браузера → режим исследования (браузер и сервер) → публичная ссылка.
// Нужен поднятый стек (`make up`).
const run = `${Date.now().toString(36)}b`;
const email = `e2e-${run}@example.com`;
const password = `e2e-password-${run}`;
const nick = `e2e_${run}`;
// Белые (наш игрок) на 4-м ходу пропускают мат Qxf7# — пазл гарантирован.
const pgn = `[Event "E2E"]
[White "${nick}"]
[Black "Opponent"]
[Result "0-1"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. d3 Nxh5 0-1
`;
const EVAL = /^([+−]\d+\.\d\d|0\.00|#−?\d+)$/;

test("анализ в браузере, пазл, исследование, публичная ссылка", async ({ page, browser }) => {
  // Анализ и исследование — движком в браузере (выбор хранится в localStorage).
  await page.addInitScript(() => {
    localStorage.setItem("cr.analysis-engine", "browser");
    localStorage.setItem("cr.explore-engine", "browser");
  });

  await page.goto("/register");
  await expect(page.getByRole("heading", { name: "Создать аккаунт" })).toBeVisible();
  await page.locator('input[name="email"]:visible').fill(email);
  await page.locator('input[name="password"]:visible').fill(password);
  await page.getByRole("button", { name: "Зарегистрироваться" }).click();
  await expect(page.getByRole("heading", { name: "Разбор партий" })).toBeVisible();

  await page.goto("/profile");
  await page.getByLabel("Ник на Lichess").fill(nick);
  await page.getByRole("button", { name: "Сохранить" }).click();
  await expect(page.getByText("Сохранено")).toBeVisible();

  // Вставка PGN → анализ стартует сам, в браузере.
  await page.getByRole("link", { name: "Главная" }).click();
  await page.getByRole("radio", { name: "PGN" }).click();
  await page.getByLabel("PGN партии").fill(pgn);
  await page.getByRole("button", { name: "Разобрать" }).click();
  await expect(page).toHaveURL(/\/games\/[0-9a-f-]+/);
  const gameUrl = page.url().replace(/\?.*$/, "");
  await expect(page.getByText("Stockfish считает в вашем браузере")).toBeVisible();

  const startReview = page.getByRole("button", { name: "Начать разбор" });
  await expect(startReview).toBeVisible({ timeout: 150_000 });
  await expect(page.getByText(/Stockfish 19 Lite WASM · в браузере · глубина \d+/)).toBeVisible();

  // Исследование: после 1. e4 чёрные идут 1… d5 вместо e5 (ход кликами по клеткам).
  await startReview.click();
  await page.locator('[data-square="d7"]:visible').click();
  await page.locator('[data-square="d5"]:visible').click();
  await expect(page.getByText("Исследование позиции")).toBeVisible();
  const evaluation = page.getByTestId("explore-eval");
  await expect(evaluation).toHaveText(EVAL, { timeout: 30_000 });
  await expect(page.getByText(/^глубина \d+/)).toBeVisible();
  // Тот же расчёт движком сервера.
  await page.getByRole("radio", { name: "Сервер" }).click();
  await expect(evaluation).toHaveText(EVAL, { timeout: 30_000 });
  await page.getByRole("button", { name: "Сделать лучший ход" }).click();
  await expect(page.getByRole("button", { name: /^2\./ })).toBeVisible();
  // Ход линии получил класс (как в анализе Chess.com) — по той же логике, что разбор партии.
  await expect(page.getByTestId("explore-verdict")).toContainText(/лучш|отличн|хорош|теори/i, { timeout: 30_000 });
  await page.getByRole("button", { name: "Вернуться к партии" }).click();
  await expect(page.getByText("Исследование позиции")).toBeHidden();

  // Пазл из ошибки: вторые линии для него посчитал браузер.
  await page.getByRole("link", { name: "Пазлы" }).click();
  await expect(page.getByText(/Найдите лучший ход/)).toBeVisible({ timeout: 30_000 });
  await page.locator('[data-square="h5"]:visible').click();
  await page.locator('[data-square="f7"]:visible').click();
  await expect(page.getByText("Верно!")).toBeVisible();

  // Публичная ссылка открывается без входа; после «Закрыть доступ» — нет.
  await page.goto(gameUrl);
  await page.getByRole("button", { name: "Поделиться" }).click();
  const link = page.getByRole("textbox", { name: "Ссылка" });
  await expect(link).toHaveValue(/\/share\/[\w-]+$/);
  const url = await link.inputValue();

  const guest = await browser.newContext({ locale: "ru-RU" });
  const shared = await guest.newPage();
  await shared.goto(url);
  await expect(shared.getByRole("link", { name: "Разобрать свои партии" })).toBeVisible();
  await expect(shared.getByRole("button", { name: "Начать разбор" })).toBeVisible();
  await expect(shared.getByText("Opponent").first()).toBeVisible();

  await page.getByRole("button", { name: "Закрыть доступ" }).click();
  await expect(link).toBeHidden();
  await shared.reload();
  await expect(shared.getByText("Ссылка недействительна")).toBeVisible();
  await guest.close();
});
