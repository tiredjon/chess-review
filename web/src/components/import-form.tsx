"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import type { GameOut, ImportJob } from "@/lib/types";
import { Button, ErrorText } from "./ui";

type Platform = "lichess" | "chesscom";

const PLATFORM_NAMES: Record<Platform, string> = { lichess: "Lichess", chesscom: "Chess.com" };
const POLL_MS = 1000;

const message = (error: unknown) =>
  error instanceof ApiError ? error.message : "Не удалось выполнить запрос";

export function ImportForm() {
  return (
    <div className="grid gap-5 lg:grid-cols-[1.2fr_1fr]">
      <PgnImport />
      <AccountImport />
    </div>
  );
}

function PgnImport() {
  const router = useRouter();
  const [pgn, setPgn] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [imported, setImported] = useState<GameOut[] | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setImported(null);
    try {
      const games = await api.importPgn(pgn);
      if (games.length === 1) {
        // Одна партия — сразу на разбор, анализ стартует сам.
        router.push(`/games/${games[0].id}?analyze=1`);
        return;
      }
      setImported(games);
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-5">
      <div>
        <h2 className="text-lg font-semibold">Вставить PGN</h2>
        <p className="mt-1 text-sm text-muted">
          Одна партия откроется сразу на разборе. Можно вставить несколько подряд.
        </p>
      </div>
      <label htmlFor="pgn" className="sr-only">
        PGN партии
      </label>
      <textarea
        id="pgn"
        value={pgn}
        onChange={(event) => setPgn(event.target.value)}
        required
        rows={11}
        spellCheck={false}
        placeholder={'[Event "Casual game"]\n[White "…"]\n[Black "…"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 …'}
        className="min-h-48 w-full resize-y rounded-lg border border-line bg-paper px-3 py-2 font-mono text-[13px] leading-relaxed placeholder:text-muted/70"
      />
      <ErrorText>{error}</ErrorText>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={busy || !pgn.trim()}>
          {busy ? "Загружаю…" : "Разобрать партию"}
        </Button>
        {imported && (
          <p className="text-sm text-muted" role="status">
            Загружено партий: {imported.length}.{" "}
            <Link href="/games?source=pgn" className="font-medium text-accent underline-offset-2 hover:underline">
              Открыть список
            </Link>
          </p>
        )}
      </div>
    </form>
  );
}

function AccountImport() {
  const [platform, setPlatform] = useState<Platform>("lichess");
  const [username, setUsername] = useState("");
  const [count, setCount] = useState(50);
  const [months, setMonths] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<ImportJob | null>(null);

  const active = job !== null && (job.status === "queued" || job.status === "running");
  const jobId = job?.job_id;

  // Прогресс импорта — полингом, пока задача не завершится.
  useEffect(() => {
    if (!active || !jobId) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const next = await api.importJob(jobId);
        if (!cancelled) setJob(next);
      } catch (err) {
        if (!cancelled) setError(message(err));
      }
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [active, jobId, job]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setJob(null);
    try {
      const name = username.trim();
      setJob(
        platform === "lichess"
          ? await api.importLichess(name, count)
          : await api.importChesscom(name, months),
      );
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-5">
      <div>
        <h2 className="text-lg font-semibold">Загрузить по нику</h2>
        <p className="mt-1 text-sm text-muted">Последние партии с площадки, без вариантов шахмат.</p>
      </div>

      <div role="radiogroup" aria-label="Площадка" className="grid grid-cols-2 rounded-lg bg-sunken p-1 text-sm">
        {(Object.keys(PLATFORM_NAMES) as Platform[]).map((key) => (
          <button
            key={key}
            type="button"
            role="radio"
            aria-checked={platform === key}
            onClick={() => setPlatform(key)}
            className={`rounded-md py-1.5 font-medium ${
              platform === key ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink"
            }`}
          >
            {PLATFORM_NAMES[key]}
          </button>
        ))}
      </div>

      <label className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium">Ник на {PLATFORM_NAMES[platform]}</span>
        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          required
          pattern="[A-Za-z0-9_\-]{2,50}"
          title="Латиница, цифры, «_» и «-»"
          autoComplete="off"
          spellCheck={false}
          className="rounded-lg border border-line bg-paper px-3 py-2 text-base"
        />
      </label>

      {platform === "lichess" ? (
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium">Сколько последних партий</span>
          <select
            value={count}
            onChange={(event) => setCount(Number(event.target.value))}
            className="rounded-lg border border-line bg-paper px-3 py-2 text-base"
          >
            {[20, 50, 100, 200, 500].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium">За какой период</span>
          <select
            value={months}
            onChange={(event) => setMonths(Number(event.target.value))}
            className="rounded-lg border border-line bg-paper px-3 py-2 text-base"
          >
            {[
              [1, "Текущий месяц"],
              [3, "3 месяца"],
              [6, "6 месяцев"],
              [12, "Год"],
            ].map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      )}

      <ErrorText>{error}</ErrorText>
      <div>
        <Button type="submit" disabled={busy || active || !username.trim()}>
          {busy || active ? "Загружаю…" : "Загрузить партии"}
        </Button>
      </div>
      {job && <ImportStatus job={job} />}
    </form>
  );
}

function ImportStatus({ job }: { job: ImportJob }) {
  const platform = PLATFORM_NAMES[job.source as Platform] ?? job.source;
  if (job.status === "failed") {
    return <ErrorText>{job.error ?? "Импорт не удался"}</ErrorText>;
  }
  const counts = `получено ${job.fetched}, новых ${job.imported}${job.skipped ? `, пропущено ${job.skipped}` : ""}`;
  if (job.status !== "done") {
    return (
      <p role="status" className="text-sm text-muted">
        {job.status === "queued" ? "В очереди…" : `Загружаю с ${platform}: ${counts}`}
      </p>
    );
  }
  return (
    <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      <span>Готово: {counts}.</span>
      <Link
        href={`/games?source=${job.source}`}
        className="font-medium text-accent underline-offset-2 hover:underline"
      >
        Открыть партии
      </Link>
    </div>
  );
}
