// Словари тренажёра эндшпиля покрывают каталог бэкенда (сессия 16.3):
//   cd web && node --test src/components/endgames/dictionary.test.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { endgames as en } from "../../lib/i18n/en/endgames.ts";
import { endgames as ru } from "../../lib/i18n/ru/endgames.ts";

const catalog = readFileSync(new URL("../../../../backend/app/endgames/catalog.py", import.meta.url), "utf8");
const ids = [...catalog.matchAll(/CatalogPosition\(\s*"(\w+)"/g)].map((match) => match[1]);

test("в каталоге бэкенда ≥ 20 позиций", () => {
  assert.ok(ids.length >= 20, `позиций: ${ids.length}`);
});

for (const [lang, dict] of [
  ["ru", ru],
  ["en", en],
]) {
  test(`${lang}: название и подсказка у каждой позиции каталога, лишних нет`, () => {
    assert.deepEqual(Object.keys(dict.positions).sort(), [...ids].sort());
    for (const id of ids) {
      assert.ok(dict.positions[id].name.length > 3, `${lang} ${id} name`);
      assert.ok(dict.positions[id].hint.length > 10, `${lang} ${id} hint`);
    }
  });
}
