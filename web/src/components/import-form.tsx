"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, codeText } from "@/lib/api";
import type { Dict } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { GameOut, ImportJob } from "@/lib/types";
import { Button, Chip, ErrorText, fieldClass } from "./ui";

type Source = "lichess" | "chesscom" | "pgn";

const SOURCE_LABELS: Record<Source, string> = { lichess: "Lichess", chesscom: "Chess.com", pgn: "PGN" };
const COUNTS = [20, 50, 100, 200];
const PERIODS = [1, 3, 6, 12];
const POLL_MS = 1000;

const message = (error: unknown, t: Dict) => (error instanceof ApiError ? error.message : t.errors.generic);

/** Загрузка партий: по нику с площадки (фоновая задача) или вставкой PGN. */
export function ImportCard({ onImported }: { onImported?: () => void }) {
  const router = useRouter();
  const { t } = useI18n();
  const copy = t.home.import;
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
        if (!cancelled) setError(message(err, t));
      }
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [active, jobId, job, onImported, t]);

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
      setError(message(err, t));
    } finally {
      setBusy(false);
    }
  }

  const ready = source === "pgn" ? pgn.trim() !== "" : username.trim() !== "";

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <h2 className="text-lg font-bold">{copy.title}</h2>
      <div role="radiogroup" aria-label={copy.from} className="grid grid-cols-3 gap-2">
        {(Object.keys(SOURCE_LABELS) as Source[]).map((key) => (
          <Chip key={key} role="radio" aria-checked={source === key} active={source === key} onClick={() => setSource(key)}>
            {SOURCE_LABELS[key]}
          </Chip>
        ))}
      </div>

      {source === "pgn" ? (
        <label className="flex flex-col gap-1.5">
          <span className="sr-only">{copy.pgnLabel}</span>
          <textarea
            value={pgn}
            onChange={(event) => setPgn(event.target.value)}
            required
            rows={7}
            spellCheck={false}
            placeholder={'[White "…"]\n[Black "…"]\n\n1. e4 e5 2. Nf3 …'}
            className={`${fieldClass} min-h-40 resize-y font-mono text-[13px] leading-relaxed`}
          />
          <span className="text-xs text-muted">{copy.pgnHint}</span>
        </label>
      ) : (
        <>
          <label className="flex flex-col gap-1.5 text-sm font-semibold text-soft">
            {copy.username(SOURCE_LABELS[source])}
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              pattern="[A-Za-z0-9_\-]{2,50}"
              autoComplete="off"
              spellCheck={false}
              placeholder={copy.usernamePlaceholder}
              className={fieldClass}
            />
          </label>
          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-1.5 text-sm font-semibold text-soft">
              {source === "lichess" ? copy.lastGames : copy.period}
            </legend>
            <div className="grid grid-cols-4 gap-2">
              {source === "lichess"
                ? COUNTS.map((value) => (
                    <Chip key={value} active={count === value} aria-pressed={count === value} onClick={() => setCount(value)}>
                      {value}
                    </Chip>
                  ))
                : PERIODS.map((value) => (
                    <Chip
                      key={value}
                      active={months === value}
                      aria-pressed={months === value}
                      onClick={() => setMonths(value)}
                      className="px-1 text-[13px]"
                    >
                      {copy.periods[value]}
                    </Chip>
                  ))}
            </div>
          </fieldset>
        </>
      )}

      <ErrorText>{error}</ErrorText>
      <Button type="submit" size="lg" disabled={busy || active || !ready}>
        {busy || active ? copy.loading : source === "pgn" ? copy.analyze : copy.load}
      </Button>
      {job && <ImportStatus job={job} />}
      {pasted && (
        <p role="status" className="text-sm text-soft">
          {copy.pasted(pasted.length)}{" "}
          <Link href="/games?source=pgn" className="font-bold text-green hover:underline">
            {copy.openList}
          </Link>
        </p>
      )}
    </form>
  );
}

function ImportStatus({ job }: { job: ImportJob }) {
  const { t } = useI18n();
  const copy = t.home.import;
  if (job.status === "failed") {
    const params = { username: job.username, source: SOURCE_LABELS[job.source] };
    return <ErrorText>{codeText(t, job.error_code, params, job.error ?? copy.failed)}</ErrorText>;
  }
  const counts = copy.counts(job.fetched, job.imported, job.skipped);
  if (job.status !== "done") {
    return (
      <p role="status" className="text-sm text-soft">
        {job.status === "queued" ? copy.queued : copy.running(counts)}
      </p>
    );
  }
  return (
    <p role="status" className="text-sm text-soft">
      {copy.done(counts)}{" "}
      <Link href={`/games?source=${job.source}`} className="font-bold text-green hover:underline">
        {copy.openGames}
      </Link>
    </p>
  );
}
