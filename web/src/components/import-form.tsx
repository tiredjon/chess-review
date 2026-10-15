"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import type { GameOut, ImportJob } from "@/lib/types";
import { Button, Chip, ErrorText } from "./ui";

type Source = "lichess" | "chesscom" | "pgn";

const SOURCE_LABELS: Record<Source, string> = { lichess: "Lichess", chesscom: "Chess.com", pgn: "PGN" };
const COUNTS = [20, 50, 100, 200];
const PERIODS: [number, string][] = [
  [1, "Месяц"],
  [3, "3 мес."],
  [6, "6 мес."],
  [12, "Год"],
];
const POLL_MS = 1000;

const message = (error: unknown) => (error instanceof ApiError ? error.message : "Не удалось выполнить запрос");

const field = "w-full rounded-lg border border-line bg-sunken px-3 py-2.5 text-base text-ink placeholder:text-muted";

/** Загрузка партий: по нику с площадки (фоновая задача) или вставкой PGN. */
export function ImportCard({ onImported }: { onImported?: () => void }) {
  const router = useRouter();
  const [source, setSource] = useState<Source>("lichess");
  const [username, setUsername] = useState("");
  const [count, setCount] = useState(50);
  const [months, setMonths] = useState(3);
  const [pgn, setPgn] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [pasted, setPasted] = useState<GameOut[] | null>(null);

  const active = job !== null && (job.status === "queued" || job.status === "running");
  const jobId = job?.job_id;

  // Прогресс импорта — полингом, пока задача не завершится.
  useEffect(() => {
    if (!active || !jobId) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const next = await api.importJob(jobId);
        if (cancelled) return;
        setJob(next);
        if (next.status === "done") onImported?.();
      } catch (err) {
        if (!cancelled) setError(message(err));
      }
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [active, jobId, job, onImported]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setJob(null);
    setPasted(null);
    try {
      if (source === "pgn") {
        const games = await api.importPgn(pgn);
        if (games.length === 1) {
          // Одна партия — сразу на разбор, анализ стартует сам.
          router.push(`/games/${games[0].id}?analyze=1`);
          return;
        }
        setPasted(games);
        onImported?.();
      } else {
        const name = username.trim();
        setJob(source === "lichess" ? await api.importLichess(name, count) : await api.importChesscom(name, months));
      }
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  const ready = source === "pgn" ? pgn.trim() !== "" : username.trim() !== "";

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <h2 className="text-lg font-bold">Загрузить партии</h2>
      <div role="radiogroup" aria-label="Откуда" className="grid grid-cols-3 gap-2">
        {(Object.keys(SOURCE_LABELS) as Source[]).map((key) => (
          <Chip key={key} role="radio" aria-checked={source === key} active={source === key} onClick={() => setSource(key)}>
            {SOURCE_LABELS[key]}
          </Chip>
        ))}
      </div>

      {source === "pgn" ? (
        <label className="flex flex-col gap-1.5">
          <span className="sr-only">PGN партии</span>
          <textarea
            value={pgn}
            onChange={(event) => setPgn(event.target.value)}
            required
            rows={7}
            spellCheck={false}
            placeholder={'[White "…"]\n[Black "…"]\n\n1. e4 e5 2. Nf3 …'}
            className={`${field} min-h-40 resize-y font-mono text-[13px] leading-relaxed`}
          />
          <span className="text-xs text-muted">Одна партия откроется сразу на разборе.</span>
        </label>
      ) : (
        <>
          <label className="flex flex-col gap-1.5 text-sm font-semibold text-soft">
            Ник на {SOURCE_LABELS[source]}
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              pattern="[A-Za-z0-9_\-]{2,50}"
              autoComplete="off"
              spellCheck={false}
              placeholder="ваш ник"
              className={field}
            />
          </label>
          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-1.5 text-sm font-semibold text-soft">
              {source === "lichess" ? "Последних партий" : "За период"}
            </legend>
            <div className="grid grid-cols-4 gap-2">
              {source === "lichess"
                ? COUNTS.map((value) => (
                    <Chip key={value} active={count === value} aria-pressed={count === value} onClick={() => setCount(value)}>
                      {value}
                    </Chip>
                  ))
                : PERIODS.map(([value, label]) => (
                    <Chip
                      key={value}
                      active={months === value}
                      aria-pressed={months === value}
                      onClick={() => setMonths(value)}
                      className="px-1 text-[13px]"
                    >
                      {label}
                    </Chip>
                  ))}
            </div>
          </fieldset>
        </>
      )}

      <ErrorText>{error}</ErrorText>
      <Button type="submit" size="lg" disabled={busy || active || !ready}>
        {busy || active ? "Загружаю…" : source === "pgn" ? "Разобрать" : "Загрузить"}
      </Button>
      {job && <ImportStatus job={job} />}
      {pasted && (
        <p role="status" className="text-sm text-soft">
          Загружено партий: {pasted.length}.{" "}
          <Link href="/games?source=pgn" className="font-bold text-green hover:underline">
            Открыть список
          </Link>
        </p>
      )}
    </form>
  );
}

function ImportStatus({ job }: { job: ImportJob }) {
  if (job.status === "failed") return <ErrorText>{job.error ?? "Импорт не удался"}</ErrorText>;
  const counts = `получено ${job.fetched}, новых ${job.imported}${job.skipped ? `, пропущено ${job.skipped}` : ""}`;
  if (job.status !== "done") {
    return (
      <p role="status" className="text-sm text-soft">
        {job.status === "queued" ? "В очереди…" : `Загружаю: ${counts}`}
      </p>
    );
  }
  return (
    <p role="status" className="text-sm text-soft">
      Готово: {counts}.{" "}
      <Link href={`/games?source=${job.source}`} className="font-bold text-green hover:underline">
        Открыть партии
      </Link>
    </p>
  );
}
