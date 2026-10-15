// Собирает набор фигур web/public/pieces/{wK…bP}.svg из набора «Celtic» Маурицио Монге
// (https://github.com/maurimo/chess-art, MIT). Исходники автора одноцветные-«конфигурируемые»:
// цвета градиента, обводки и тени задаются при сборке — как в его configure.html.
//
//   node scripts/build-pieces.mjs [--ref <commit>]
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_REF = "d8705d8bc9879fef44208de19e2a20c937409e1f";
const PIECES = ["k", "q", "r", "b", "n", "p"];

// Тёплое «дерево»: белые — сливочные, чёрные — тёмный графит.
const COLORS = {
  w: { light: "#fffaf0", dark: "#d6bf99", stroke: "#3a2e24" },
  b: { light: "#77706a", dark: "#2a2623", stroke: "#15120f" },
};
const SHADOW = { opacity: 0.3, dx: 14, dy: 22, blur: 28 };

const ref = process.argv.includes("--ref") ? process.argv[process.argv.indexOf("--ref") + 1] : DEFAULT_REF;
const outDir = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "pieces");

function build(source, { light, dark, stroke }) {
  return (
    source
      // Служебное Inkscape: комментарии, namedview, атрибуты inkscape:/sodipodi:.
      .replace(/<\?xml[^>]*>\s*/, "")
      .replace(/<!--[\s\S]*?-->\s*/g, "")
      .replace(/<sodipodi:namedview[\s\S]*?\/>\s*/g, "")
      .replace(/\s(?:inkscape|sodipodi):[\w-]+="[^"]*"/g, "")
      .replace(/\s+xmlns:(?:inkscape|sodipodi)="[^"]*"/g, "")
      // Размер задаёт тот, кто вставляет картинку.
      .replace(/\s(?:width|height)="[\d.]+pt"/g, "")
      .replace("stop-color:#ffffff", `stop-color:${light}`)
      .replace("stop-color:#00ffff", `stop-color:${dark}`)
      .replace(/stroke:#ff0000/g, `stroke:${stroke}`)
      .replace(/stdDeviation="[\d. ]+"/, `stdDeviation="${SHADOW.blur} ${SHADOW.blur}"`)
      .replace(
        /class="base shadow"\s+style="fill:#000000"/,
        `class="base shadow" style="fill:#000000;fill-opacity:${SHADOW.opacity}" transform="translate(${SHADOW.dx} ${SHADOW.dy})"`,
      )
      .replace(/\n\s*\n/g, "\n")
  );
}

await mkdir(outDir, { recursive: true });
for (const piece of PIECES) {
  const url = `https://raw.githubusercontent.com/maurimo/chess-art/${ref}/celtic/${piece}.svg`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  const source = await response.text();
  for (const [color, palette] of Object.entries(COLORS)) {
    const file = join(outDir, `${color}${piece.toUpperCase()}.svg`);
    await writeFile(file, build(source, palette));
    console.log(file);
  }
}
