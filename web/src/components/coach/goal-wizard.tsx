"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ApiError } from "@/lib/api";
import type { Goal, GoalIn, GoalSource, GoalState, RatingOption } from "@/lib/coach-api";
import { SOURCE_NAMES } from "@/lib/format";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { TimeClass } from "@/lib/types";
import { Button, Chip, ErrorText, Panel } from "../ui";
import { Empty, GREEN_LINK } from "./block";
import { coach } from "./source";

const HINTS = [100, 200, 300, 400, 500, 600];
const MINUTES = [15, 30, 45, 60, 90];
const DAYS = [3, 4, 5, 6, 7];
const MIN_TARGET_GAP = 25;

const optionKey = (o: Pick<RatingOption, "source" | "time_class">) => `${o.source}:${o.time_class}`;

/** Мастер цели: площадка и контроль (из `ratings`), целевой рейтинг, минут в день, дней в неделю.
 *  Часовой пояс берётся из браузера. Без `current` — первая цель; с ним — правка. */
export function GoalWizard({
  state,
  current = null,
  onSaved,
  onCancel,
  onRemoved,
}: {
  state: GoalState;
  current?: Goal | null;
  onSaved: () => void;
  onCancel?: () => void;
  onRemoved?: () => void;
}) {
  const { t } = useI18n();
  const c = t.coach.wizard;
  const options = state.ratings;
  const initial = options.find((o) => current && o.source === current.source && o.time_class === current.time_class) ?? options[0];
  const [picked, setPicked] = useState<string | null>(initial ? optionKey(initial) : null);
  const option = options.find((o) => optionKey(o) === picked) ?? initial ?? null;
  const base = option?.rating ?? current?.current_rating ?? 0;
  const [target, setTarget] = useState<string>(current ? String(current.target_rating) : option ? String(option.rating + 300) : "");
  const [minutes, setMinutes] = useState(current?.minutes_per_day ?? 45);
  const [days, setDays] = useState(current?.days_per_week ?? 5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  const tz = useMemo(() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    } catch {
      return "UTC";
    }
  }, []);

  const heading = current ? c.editTitle : c.title;
  if (options.length === 0) {
    return (
      <Panel>
        <Empty title={c.noRatingsTitle}>
          <p>{c.noRatingsText}</p>
          <Link href="/" className={GREEN_LINK}>
            {c.importLink}
          </Link>
          {onCancel && (
            <Button variant="raised" onClick={onCancel}>
              {c.cancel}
            </Button>
          )}
        </Empty>
      </Panel>
    );
  }

  const targetNumber = Number(target);
  const minTarget = base + MIN_TARGET_GAP;
  const targetValid = Number.isInteger(targetNumber) && targetNumber >= minTarget && targetNumber <= 3500;

  const submit = async () => {
    if (!option || !targetValid) return;
    setBusy(true);
    setError(null);
    const input: GoalIn = {
      source: option.source,
      time_class: option.time_class,
      target_rating: targetNumber,
      minutes_per_day: minutes,
      days_per_week: days,
      tz,
    };
    try {
      await coach.setGoal(input);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : c.failed);
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!confirmRemove) {
      setConfirmRemove(true);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await coach.deleteGoal();
      onRemoved?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : c.failed);
      setBusy(false);
    }
  };

  return (
    <Panel className="mx-auto w-full max-w-2xl">
      <form
        className="flex flex-col gap-6"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <header className="flex flex-col gap-1">
          <h2 className="text-2xl font-extrabold">{heading}</h2>
          {!current && <p className="text-soft">{c.intro}</p>}
        </header>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-sm font-bold text-muted">{c.pickTitle}</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {options.map((o) => {
              const key = optionKey(o);
              return (
                <Chip
                  key={key}
                  active={key === optionKey(option ?? o)}
                  onClick={() => {
                    setPicked(key);
                    if (!current) setTarget(String(o.rating + 300));
                  }}
                  className="flex flex-col items-start gap-0.5 py-2 text-left"
                >
                  <span className="font-bold">
                    {SOURCE_NAMES[o.source as GoalSource]} · {t.stats.timeClasses[o.time_class as TimeClass]}
                  </span>
                  <span className="text-xs font-semibold text-muted">{c.option(o.rating, o.games)}</span>
                </Chip>
              );
            })}
          </div>
        </fieldset>

        <div className="flex flex-col gap-2">
          <label htmlFor="coach-target" className="text-sm font-bold text-muted">
            {c.target}
          </label>
          <input
            id="coach-target"
            inputMode="numeric"
            value={target}
            onChange={(event) => setTarget(event.target.value.replace(/\D/g, "").slice(0, 4))}
            aria-invalid={target !== "" && !targetValid}
            className="min-h-11 w-32 rounded-lg border border-line bg-sunken px-3 text-xl font-extrabold tabular-nums text-ink focus:border-green focus:outline-none"
          />
          <div className="flex flex-wrap gap-1.5" aria-label={c.targetHint}>
            {HINTS.map((plus) => (
              <Chip key={plus} active={targetNumber === base + plus} onClick={() => setTarget(String(base + plus))} className="min-h-9">
                {c.plus(plus)}
              </Chip>
            ))}
          </div>
          {target !== "" && !targetValid && <ErrorText>{c.targetInvalid(minTarget)}</ErrorText>}
        </div>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-sm font-bold text-muted">{c.minutes}</legend>
          <div className="flex flex-wrap gap-1.5">
            {MINUTES.map((m) => (
              <Chip key={m} active={minutes === m} onClick={() => setMinutes(m)} className="min-h-11">
                {t.coach.plan.minutes(m)}
              </Chip>
            ))}
          </div>
        </fieldset>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-sm font-bold text-muted">{c.days}</legend>
          <div className="flex flex-wrap gap-1.5">
            {DAYS.map((d) => (
              <Chip key={d} active={days === d} onClick={() => setDays(d)} className="min-h-11 min-w-11">
                {d}
              </Chip>
            ))}
          </div>
          <p className="text-sm font-semibold text-muted">
            {c.daysValue(days)} · {c.weekLoad(minutes * days)}
          </p>
        </fieldset>

        <p className="text-xs font-semibold text-muted">{c.tzNote(tz)}</p>
        <ErrorText>{error}</ErrorText>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Button type="submit" size="lg" disabled={busy || !targetValid} className="max-sm:w-full">
            {busy ? c.saving : current ? c.saveEdit : c.submit}
          </Button>
          {onCancel && (
            <Button variant="raised" size="lg" disabled={busy} onClick={onCancel} className="max-sm:w-full">
              {c.cancel}
            </Button>
          )}
          {current && onRemoved && (
            <Button variant="raised" disabled={busy} onClick={() => void remove()} className="text-danger max-sm:w-full sm:ml-auto">
              {confirmRemove ? c.removeConfirm : c.remove}
            </Button>
          )}
        </div>
      </form>
    </Panel>
  );
}
