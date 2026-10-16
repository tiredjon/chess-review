// Кладёт браузерный движок в web/public/engine/: Stockfish.js (Nathan Rugg / Chess.com,
// GPL-3.0) — сборка «lite single-threaded» (≈1.8 МБ, без SharedArrayBuffer, поэтому не нужны
// заголовки COOP/COEP). Берётся из npm-пакета `stockfish` закреплённой версии, архив
// сверяется по sha512 из реестра npm.
//
//   node scripts/fetch-engine.mjs [--version 19.0.0]
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { gunzipSync } from "node:zlib";

const DEFAULT_VERSION = "19.0.0";
const FLAVOR = "lite-single";

const version = process.argv.includes("--version")
  ? process.argv[process.argv.indexOf("--version") + 1]
  : DEFAULT_VERSION;
const outDir = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "engine");

/** Файлы из tar (ustar): имя → содержимое. */
function untar(buffer) {
  const files = new Map();
  for (let offset = 0; offset + 512 <= buffer.length; ) {
    const header = buffer.subarray(offset, offset + 512);
    const name = header.subarray(0, 100).toString("utf8").replace(/\0.*$/s, "");
    if (!name) break;
    const prefix = header.subarray(345, 500).toString("utf8").replace(/\0.*$/s, "");
    const size = parseInt(header.subarray(124, 136).toString("utf8").trim() || "0", 8);
    const body = buffer.subarray(offset + 512, offset + 512 + size);
    files.set(prefix ? `${prefix}/${name}` : name, Buffer.from(body));
    offset += 512 + Math.ceil(size / 512) * 512;
  }
  return files;
}

const meta = await (await fetch(`https://registry.npmjs.org/stockfish/${version}`)).json();
const { tarball, integrity } = meta.dist;
const archive = Buffer.from(await (await fetch(tarball)).arrayBuffer());
const digest = `sha512-${createHash("sha512").update(archive).digest("base64")}`;
if (digest !== integrity) throw new Error(`Контрольная сумма не совпала: ${digest} ≠ ${integrity}`);

const files = untar(gunzipSync(archive));
const build = meta.buildVersion ?? version.split(".")[0];
// Имена — как в пакете: в них версия, кэш браузера не отдаст старый движок после обновления
// (`.wasm` воркер ищет рядом с `.js`, по тому же имени).
const engine = `stockfish-${build}-${FLAVOR}`;
const wanted = {
  [`package/bin/${engine}.js`]: `${engine}.js`,
  [`package/bin/${engine}.wasm`]: `${engine}.wasm`,
  "package/Copying.txt": "COPYING.txt",
};
await mkdir(outDir, { recursive: true });
for (const [source, target] of Object.entries(wanted)) {
  const body = files.get(source);
  if (!body) throw new Error(`В пакете нет ${source}`);
  await writeFile(join(outDir, target), body);
}
await writeFile(
  join(outDir, "README.md"),
  `# Браузерный движок

Stockfish.js ${version} (сборка \`${FLAVOR}\`) — https://github.com/nmrugg/stockfish.js,
npm-пакет \`stockfish@${version}\`. Лицензия — GPL-3.0 (\`COPYING.txt\`); исходный код —
в репозитории проекта по ссылке выше. Файлы не изменены, собираются
\`node scripts/fetch-engine.mjs --version ${version}\`.
`,
);
console.log(`stockfish@${version} (${FLAVOR}) → ${outDir}`);
