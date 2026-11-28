// Тесты часов партии с ботом. Запуск из `web/`: node --test src/components/play/clock.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import { clkComment, formatClock, presetControl, remainingAt } from "./clock.ts";

test("formatClock: минуты, десятые в цейтноте, часы", () => {
  assert.equal(formatClock(180_000), "3:00");
  assert.equal(formatClock(59_999), "0:59");
  assert.equal(formatClock(9_450), "0:09.4");
  assert.equal(formatClock(-5), "0:00.0");
  assert.equal(formatClock(3_600_000), "1:00:00");
});

test("clkComment: формат %clk", () => {
  assert.equal(clkComment(175_400), "[%clk 0:02:55.4]");
});

test("presetControl и remainingAt", () => {
  assert.deepEqual(presetControl("3+2"), { initial: 180, increment: 2 });
  assert.equal(presetControl("none"), null);
  const clock = { white: 10_000, black: 8_000, turnStart: 1_000 };
  assert.equal(remainingAt(clock, "white", "white", 4_000), 7_000);
  assert.equal(remainingAt(clock, "black", "white", 4_000), 8_000);
  assert.equal(remainingAt({ ...clock, turnStart: null }, "white", "white", 4_000), 10_000);
});
