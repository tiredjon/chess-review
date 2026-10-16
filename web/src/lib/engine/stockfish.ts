// Stockfish WASM в Web Worker (`public/engine/`, сборка lite single-threaded — без
// SharedArrayBuffer и заголовков COOP/COEP). Один воркер — один поиск за раз; параллельно —
// пулом из нескольких воркеров, как пул процессов на сервере.
import { parseBestMove, parseInfo, type EngineLine } from "./uci";

export const ENGINE_URL = "/engine/stockfish-19-lite-single.js";
// Хеш на воркер: пул из 4 воркеров — 128 МБ, столько же, сколько один процесс на сервере.
const HASH_MB = 32;

export type SearchResult = {
  /** Достигнутая глубина. */
  depth: number;
  /** Линии по порядку MultiPV; пусто — у стороны на ходу нет ходов. */
  lines: EngineLine[];
};

export type SearchOptions = {
  fen: string;
  depth: number;
  multipv?: number;
  /** Искать только среди этих ходов (UCI `searchmoves`). */
  searchmoves?: string[];
  /** Предел времени, мс: поиск кончается на глубине или по времени — что раньше. */
  movetime?: number;
  /** Промежуточные линии по мере углубления (режим исследования). */
  onUpdate?: (result: SearchResult) => void;
  signal?: AbortSignal;
};

export class EngineLoadError extends Error {}

export function engineSupported(): boolean {
  return typeof Worker !== "undefined" && typeof WebAssembly === "object";
}

export class Stockfish {
  /** `id name` движка, например «Stockfish 19 Lite WASM». */
  name = "Stockfish";
  private readonly worker: Worker;
  private listener: ((line: string) => void) | null = null;
  private queue: Promise<unknown> = Promise.resolve();
  private multipv = 1;

  private constructor(worker: Worker) {
    this.worker = worker;
    worker.onmessage = (event: MessageEvent<string>) => {
      if (typeof event.data === "string") this.listener?.(event.data);
    };
  }

  static async create(): Promise<Stockfish> {
    if (!engineSupported()) throw new EngineLoadError("WebAssembly недоступен");
    const engine = new Stockfish(new Worker(ENGINE_URL));
    try {
      await engine.handshake();
    } catch (err) {
      engine.terminate();
      throw err instanceof EngineLoadError ? err : new EngineLoadError(String(err));
    }
    return engine;
  }

  private handshake(): Promise<void> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new EngineLoadError("движок не ответил")), 20_000);
      this.worker.onerror = (event) => {
        clearTimeout(timer);
        reject(new EngineLoadError(event.message || "ошибка загрузки движка"));
      };
      this.listener = (line) => {
        if (line.startsWith("id name ")) this.name = line.slice(8).trim();
        if (line === "uciok") {
          this.send(`setoption name Hash value ${HASH_MB}`);
          this.send("isready");
        }
        if (line === "readyok") {
          clearTimeout(timer);
          this.listener = null;
          resolve();
        }
      };
      this.send("uci");
    });
  }

  private send(command: string) {
    this.worker.postMessage(command);
  }

  /** Поиск до глубины; поиски одного воркера идут по очереди. Отмена — `stop`, затем
   *  отклонение с AbortError (движок к этому времени уже свободен). */
  search(options: SearchOptions): Promise<SearchResult> {
    const run = this.queue.then(() => this.run(options));
    this.queue = run.catch(() => undefined);
    return run;
  }

  private run({ fen, depth, multipv = 1, searchmoves, movetime, onUpdate, signal }: SearchOptions): Promise<SearchResult> {
    return new Promise((resolve, reject) => {
      if (signal?.aborted) {
        reject(new DOMException("aborted", "AbortError"));
        return;
      }
      const lines = new Map<number, EngineLine>();
      let reached = 0;
      const snapshot = (): SearchResult => ({
        depth: reached,
        lines: [...lines.entries()].sort(([a], [b]) => a - b).map(([, line]) => line),
      });
      const onAbort = () => this.send("stop");
      signal?.addEventListener("abort", onAbort, { once: true });

      this.listener = (text) => {
        const info = parseInfo(text);
        if (info) {
          // Границы окна — не оценка позиции; строки старших линий MultiPV приходят следом.
          if (info.bound || info.multipv > multipv) return;
          reached = Math.max(reached, info.depth);
          lines.set(info.multipv, info.line);
          if (onUpdate && info.multipv === multipv) onUpdate(snapshot());
          return;
        }
        const best = parseBestMove(text);
        if (best === undefined) return;
        this.listener = null;
        signal?.removeEventListener("abort", onAbort);
        if (signal?.aborted) reject(new DOMException("aborted", "AbortError"));
        else resolve(best === null ? { depth: reached, lines: [] } : snapshot());
      };

      if (multipv !== this.multipv) {
        this.send(`setoption name MultiPV value ${multipv}`);
        this.multipv = multipv;
      }
      this.send(`position fen ${fen}`);
      const limits = [`depth ${depth}`, movetime ? `movetime ${movetime}` : "", searchmoves?.length ? `searchmoves ${searchmoves.join(" ")}` : ""];
      this.send(`go ${limits.filter(Boolean).join(" ")}`);
    });
  }

  terminate() {
    this.listener = null;
    this.worker.terminate();
  }
}

/** Несколько воркеров: каждая задача берёт свободный. */
export class StockfishPool {
  private readonly idle: Stockfish[];
  private readonly waiting: ((engine: Stockfish) => void)[] = [];

  private constructor(readonly engines: Stockfish[]) {
    this.idle = [...engines];
  }

  /** Размер по умолчанию — ядра минус одно (интерфейсу), не больше 4. */
  static async create(size = Math.max(1, Math.min(4, (navigator.hardwareConcurrency || 2) - 1))) {
    const engines = await Promise.all(Array.from({ length: size }, () => Stockfish.create()));
    return new StockfishPool(engines);
  }

  get name() {
    return this.engines[0]?.name ?? "Stockfish";
  }

  async run<T>(task: (engine: Stockfish) => Promise<T>): Promise<T> {
    const engine = this.idle.pop() ?? (await new Promise<Stockfish>((resolve) => this.waiting.push(resolve)));
    try {
      return await task(engine);
    } finally {
      const next = this.waiting.shift();
      if (next) next(engine);
      else this.idle.push(engine);
    }
  }

  terminate() {
    this.engines.forEach((engine) => engine.terminate());
  }
}
