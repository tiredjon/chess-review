import { expect, test, type Page } from "@playwright/test";

// Дебюты сквозь стек (сессия 13.8): партия в Найдорфе за чёрных → разбор → «Тренировать эту
// линию» → курс; та же линия из «Моего репертуара» и из каталога ведёт в тот же курс → дерево
// и идеи → тренажёр (ход курса и ошибка). Нужен поднятый стек (`make up` / `make app`).
//
// Курс общий для всех пользователей и собирается один раз (~2 мин запросами к Lichess Masters):
// на стеке, где курс Найдорфа за чёрных уже собран, `POST /courses` отдаёт его сразу (200).
// На чистой базе первый прогон ждёт сборку — отсюда запас по времени.
const run = Date.now().toString(36);
const email = `e2e-${run}@example.com`;
const password = `e2e-password-${run}`;
const nick = `e2e_${run}`;

// Линия курса — Найдорф до 5…a6; 6. Qd3 вне книги, так что книжная линия партии — ровно эти 10 полуходов.
const LINE = ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4", "f3d4", "g8f6", "b1c3", "a7a6"];
const pgn = `[Event "E2E"]
[White "Opponent"]
[Black "${nick}"]
[Result "0-1"]

1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Qd3 e5 7. Nf3 Be7 0-1
`;

type Card = { node_id: number; path_uci: string[] };

async function register(page: Page) {
  await page.goto("/register");
  await page.locator('input[name="email"]:visible').fill(email);
  await page.locator('input[name="password"]:visible').fill(password);
  await page.getByRole("button", { name: "Зарегистрироваться" }).click();
  await expect(page.getByRole("heading", { name: "Разбор партий" })).toBeVisible();
  // Ник — по нему во вставленном PGN определяется цвет пользователя (чёрные).
  await page.goto("/profile");
  await page.getByLabel("Ник на Lichess").fill(nick);
  await page.getByRole("button", { name: "Сохранить" }).click();
  await expect(page.getByText("Сохранено")).toBeVisible();
}

/** Курс открыт; если он ещё собирается (чистая база) — ждём сборку. */
async function expectCourseReady(page: Page) {
  await expect(page).toHaveURL(/\/openings\/courses\/[0-9a-f-]+/);
  await expect(page.getByRole("heading", { name: "Идеи позиции" })).toBeVisible({ timeout: 280_000 });
}

/** Ход кликами по клеткам видимой доски. */
async function play(page: Page, uci: string) {
  await page.locator(`[data-square="${uci.slice(0, 2)}"]:visible`).click();
  await page.locator(`[data-square="${uci.slice(2, 4)}"]:visible`).click();
}

test("дебюты: разбор → курс, репертуар и каталог → тот же курс, тренажёр", async ({ page }) => {
  test.setTimeout(480_000);
  await register(page);

  // Партия в Найдорфе за чёрных: вставка PGN, анализ до done.
  await page.getByRole("link", { name: "Главная" }).click();
  await page.getByRole("radio", { name: "PGN" }).click();
  await page.getByLabel("PGN партии").fill(pgn);
  await page.getByRole("button", { name: "Разобрать" }).click();
  await expect(page).toHaveURL(/\/games\/[0-9a-f-]+/);
  await expect(page.getByRole("button", { name: "Начать разбор" })).toBeVisible({ timeout: 150_000 });

  // Обзор партии: дебют и выход из теории ходом соперника (6. Qd3) → «Тренировать эту линию».
  const opening = page.getByRole("region", { name: "Sicilian Defense: Najdorf Variation" });
  await expect(opening).toBeVisible();
  await expect(opening.getByText("Выход из теории на 6-м ходу — ходом соперника.", { exact: false })).toBeVisible();
  const created = page.waitForRequest((r) => r.url().endsWith("/api/v1/courses") && r.method() === "POST");
  await opening.getByRole("button", { name: "Тренировать эту линию" }).click();
  expect((await created).postDataJSON()).toEqual({ line_uci: LINE, color: "black", source: "repertoire" });
  await expectCourseReady(page);
  const coursePath = new URL(page.url()).pathname;

  // «Мой репертуар» за чёрных: дебют партии → «Учить эту линию» → тот же курс.
  await page.goto("/openings");
  await page.getByRole("radio", { name: "Чёрные" }).click();
  await page.getByRole("button", { name: /Sicilian Defense: Najdorf Variation/ }).first().click();
  await page.getByRole("button", { name: "Учить эту линию" }).click();
  await expect(page).toHaveURL(new RegExp(`${coursePath}$`));

  // Каталог: курс в «Моих курсах» (из репертуара), линия Найдорфа за чёрных → «Создать курс» → тот же курс.
  await page.goto("/openings/courses");
  const mine = page.getByRole("article").filter({ has: page.getByRole("link", { name: "Najdorf Variation" }) });
  await expect(mine.getByText("Sicilian Defense · B90 · чёрными · из репертуара")).toBeVisible();
  await page.getByLabel("Поиск дебюта").fill("Najdorf B90");
  await page.getByRole("button").filter({ hasText: /5\. Nc3 a6$/ }).first().click();
  const newCourse = page.getByRole("region", { name: "Новый курс" });
  await newCourse.getByRole("radio", { name: /Учить за чёрных/ }).click();
  await newCourse.getByRole("button", { name: "Создать курс" }).click();
  await expect(page).toHaveURL(new RegExp(`${coursePath}$`));

  // Страница курса: конец линии с идеями, дерево ходов.
  await expectCourseReady(page);
  await expect(page.getByText("Конец линии").first()).toBeVisible();
  // Дерево (на десктопе — рядом с доской, вкладки только на узком экране): ход линии 5…a6
  // и ветка дальше теории — 6. Be3 (фигура в имени кнопки — буквой: «B e3»).
  await expect(page.getByRole("button", { name: /^a6\b/ }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /^B e3/ }).first()).toBeVisible();

  // Тренажёр: новые карточки — по порядку полуходов, сначала позиции исходной линии
  // (после 1. e4, 2. Nf3, …): за чёрных — ходы курса 1…c5 … 5…a6.
  await page.getByRole("button", { name: "Тренировать" }).first().click();
  await expect(page).toHaveURL(/\/openings\/train\?course=/);
  const nextCard = () => page.waitForResponse((r) => r.url().includes("/api/v1/trainer/next"));
  let card = nextCard();
  for (let ply = 1; ply < LINE.length; ply += 2) {
    expect(((await (await card).json()) as Card).path_uci).toEqual(LINE.slice(0, ply));
    await expect(page.getByText("Найдите ход вашей линии.", { exact: false })).toBeVisible();
    await play(page, LINE[ply]);
    await expect(page.getByText("Верно — это ход курса.")).toBeVisible();
    card = nextCard();
    await page.getByRole("button", { name: "Следующая позиция" }).click();
  }

  // Дальше теории — после 6-го хода белых (6. Be3 / Bg5 / Be2): 6…Nxe4?? 7. Nxe4 отдаёт коня —
  // ошибка, ход курса стрелкой и карточка идей (идеи конца линии после 5…a6).
  const beyond = (await (await card).json()) as Card;
  expect(beyond.path_uci.slice(0, LINE.length)).toEqual(LINE);
  expect(beyond.path_uci).toHaveLength(LINE.length + 1);
  await expect(page.getByText("Найдите ход вашей линии.", { exact: false })).toBeVisible();
  await play(page, "f6e4");
  await expect(page.getByText(/Этот ход заметно хуже/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Ход курса:/)).toBeVisible();
  await expect(page.getByText("Вспомните идеи позиции")).toBeVisible();
});
