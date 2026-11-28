import { expect, test } from "@playwright/test";

// Партия с ботом с контролем времени: выбор 1+0, часы обеих сторон, бот укладывается в своё
// время, флаг человека — поражение «по времени». Нужен поднятый стек (`make up`).
const run = `${Date.now().toString(36)}c`;
const email = `e2e-${run}@example.com`;
const password = `e2e-password-${run}`;

test("игра с ботом на время: часы и флаг", async ({ page }) => {
  test.setTimeout(150_000);
  await page.goto("/register");
  await page.locator('input[name="email"]:visible').fill(email);
  await page.locator('input[name="password"]:visible').fill(password);
  await page.getByRole("button", { name: "Зарегистрироваться" }).click();
  await expect(page.getByRole("heading", { name: "Разбор партий" })).toBeVisible();

  await page.goto("/play");
  const time = page.getByRole("radiogroup", { name: "Контроль времени" });
  await expect(time.getByRole("radio", { name: "Без часов" })).toHaveAttribute("aria-checked", "true");
  await time.getByRole("radio", { name: "1+0", exact: true }).click();
  await page.getByRole("radio", { name: "Белые" }).click();
  await page.getByRole("button", { name: "Играть", exact: true }).click();

  const timers = page.getByRole("timer");
  await expect(timers).toHaveCount(2);
  await expect(timers.nth(0)).toHaveText("1:00");
  await expect(timers.nth(1)).toHaveText("1:00");

  // 1. e4 — пошли часы бота; он отвечает, не тратя больше пары секунд, — пошли наши.
  await page.locator('[data-square="e2"]:visible').click();
  await page.locator('[data-square="e4"]:visible').click();
  await expect(page.getByText("Ваш ход")).toBeVisible({ timeout: 20_000 });
  const botLeft = await timers.nth(0).textContent();
  expect(botLeft).toMatch(/^0:5\d$/);
  await expect(timers.nth(1)).toHaveText(/^0:5\d$/, { timeout: 5_000 });

  // Не ходим — флаг через минуту: «Вы проиграли · По времени».
  await expect(page.getByRole("dialog")).toContainText("По времени", { timeout: 75_000 });
  await expect(page.getByRole("dialog")).toContainText("Вы проиграли");
  await expect(timers.nth(1)).toHaveText("0:00.0");
});
