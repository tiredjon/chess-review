// Stockfish 19 lite single-threaded из `public/engine/` процессом Node — для скриптов
// `bots-*.mjs`. Протокол — как у `Stockfish` в `src/lib/engine/stockfish.ts`.
import { spawn } from "node:child_process";
import { dirname, join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

import { parseBestMove, parseInfo } from "../src/lib/engine/uci.ts";

const ENGINE = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "engine", "stockfish-19-lite-single.js");

/** Тот же протокол, что `Stockfish` в `lib/engine/stockfish.ts`, но процессом Node. */
export class NodeEngine {
  constructor() {
    this.proc = spawn(process.execPath, [ENGINE], { stdio: ["pipe", "pipe", "ignore"] });
    this.listener = null;
    this.multipv = 1;
    createInterface({ input: this.proc.stdout }).on("line", (line) => this.listener?.(line));
  }

  send(cmd) {
    this.proc.stdin.write(cmd + "\n");
  }

  waitFor(token) {
    return new Promise((resolve) => {
      this.listener = (line) => {
        if (line === token) {
          this.listener = null;
          resolve();
        }
      };
    });
  }

  async init() {
    const ok = this.waitFor("uciok");
    this.send("uci");
    await ok;
    this.send("setoption name Hash value 16");
    await this.ready();
  }

  async ready() {
    const ok = this.waitFor("readyok");
    this.send("isready");
    await ok;
  }

  async newGame() {
    this.send("ucinewgame");
    await this.ready();
  }

  search({ fen, depth, multipv = 1, movetime }) {
    return new Promise((resolve) => {
      const lines = new Map();
      let reached = 0;
      this.listener = (text) => {
        const info = parseInfo(text);
        if (info) {
          if (info.bound || info.multipv > multipv) return;
          reached = Math.max(reached, info.depth);
          lines.set(info.multipv, info.line);
          return;
        }
        const best = parseBestMove(text);
        if (best === undefined) return;
        this.listener = null;
        const sorted = [...lines.entries()].sort(([a], [b]) => a - b).map(([, l]) => l);
        resolve({ depth: reached, lines: best === null ? [] : sorted });
      };
      if (multipv !== this.multipv) {
        this.send(`setoption name MultiPV value ${multipv}`);
        this.multipv = multipv;
      }
      this.send(`position fen ${fen}`);
      this.send(`go depth ${depth}${movetime ? ` movetime ${movetime}` : ""}`);
    });
  }

  quit() {
    this.send("quit");
    this.proc.kill();
  }
}
