import { expect, test } from "@playwright/test";

// Smoke сквозь весь стек: регистрация → выход → вход → ник в профиле → вставка PGN →
// анализ (SSE до done) → разбор → статистика → пазл → выход. Нужен поднятый стек
// (`make up`): API, воркер со Stockfish. Каждый прогон — новый пользователь.
//
// Партия: белые (наш игрок) на 4-м ходу пропускают мат в один ход Qxf7# и играют 4. d3 —
// из этой ошибки воркер делает пазл с решением Qxf7#.
const run = Date.now().toString(36);
const email = `e2e-${run}@example.com`;
const password = `e2e-password-${run}`;
const nick = `e2e_${run}`;
// Next держит ушедшие страницы скрытыми в <Activity>: форма входа остаётся в DOM рядом с
// формой регистрации, поэтому поля — только видимые.
const pgn = `[Event "E2E"]
[White "${nick}"]
[Black "Opponent"]
[Result "0-1"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. d3 Nxh5 0-1
`;

test("регистрация, разбор партии, статистика, пазл, выход", async ({ page }) => {
  // Гость без сессии попадает на вход; язык переключается до входа.
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
  await page.getByRole("radio", { name: "English" }).click();
  await expect(page.getByRole("heading", { name: "Log in to Chess Review" })).toBeVisible();
  await page.getByRole("radio", { name: "Русский" }).click();
  await expect(page.getByRole("heading", { name: "Войти в Chess Review" })).toBeVisible();

  // Регистрация.
  await page.getByRole("link", { name: "Зарегистрироваться" }).click();
  await expect(page.getByRole("heading", { name: "Создать аккаунт" })).toBeVisible();
  await page.locator('input[name="email"]:visible').fill(email);
  await page.locator('input[name="password"]:visible').fill(password);
  await page.getByRole("button", { name: "Зарегистрироваться" }).click();
  await expect(page.getByRole("heading", { name: "Разбор партий" })).toBeVisible();

  // Выход и вход заново.
  await page.goto("/profile");
  await page.getByRole("button", { name: "Выйти из аккаунта" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Войти в Chess Review" })).toBeVisible();
  await page.locator('input[name="email"]:visible').fill(email);
  await page.locator('input[name="password"]:visible').fill(password);
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByRole("heading", { name: "Разбор партий" })).toBeVisible();

  // Ник в профиле — по нему определяется цвет во вставленном PGN (нужен для пазлов).
  await page.goto("/profile");
  await page.getByLabel("Ник на Lichess").fill(nick);
  await page.getByRole("button", { name: "Сохранить" }).click();
  await expect(page.getByText("Сохранено")).toBeVisible();

  // Вставка PGN: одна партия открывается на разборе, анализ стартует сам.
  await page.getByRole("link", { name: "Главная" }).click();
  await page.getByRole("radio", { name: "PGN" }).click();
  await page.getByLabel("PGN партии").fill(pgn);
  await page.getByRole("button", { name: "Разобрать" }).click();
  await expect(page).toHaveURL(/\/games\/[0-9a-f-]+/);

  // Прогресс по SSE до done → обзор партии.
  const startReview = page.getByRole("button", { name: "Начать разбор" });
  await expect(startReview).toBeVisible({ timeout: 150_000 });
  await expect(page.getByText("Точность").first()).toBeVisible();

  // Разбор по ходам: 4. d3 — ошибка с объяснением.
  await startReview.click();
  await page.getByRole("button", { name: /d3$/ }).click();
  await expect(page.getByText(/d3 — (зевок|ошибка|упущение)/)).toBeVisible();
  await expect(page.getByText(/Лучше было/)).toBeVisible();

  // Статистика: одна партия.
  await page.getByRole("link", { name: "Статистика" }).click();
  await expect(page.getByRole("heading", { name: "Статистика" })).toBeVisible();
  await expect(page.getByText("Точность по фазам")).toBeVisible();

  // Пазл из ошибки: решение — мат Qxf7#. Ход кликами по клеткам.
  await page.getByRole("link", { name: "Пазлы" }).click();
  await expect(page.getByText(/Найдите лучший ход/)).toBeVisible({ timeout: 30_000 });
  await page.locator('[data-square="h5"]:visible').click();
  await page.locator('[data-square="f7"]:visible').click();
  await expect(page.getByText("Верно!")).toBeVisible();

  // Выход.
  await page.goto("/profile");
  await page.getByRole("button", { name: "Выйти из аккаунта" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/stats");
  await expect(page).toHaveURL(/\/login\?next=%2Fstats/);
});
