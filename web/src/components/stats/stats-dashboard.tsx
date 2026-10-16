"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import { CLASS_COLORS, CLASS_ORDER, classPlural, phaseClass, type ClassKey } from "@/lib/classes";
import { formatDate } from "@/lib/format";
import { useI18n } from "@/lib/i18n/use-i18n";
import { motifName } from "@/lib/motifs";
import type { GameSource, OpeningStat, Stats, TimeClass } from "@/lib/types";
import { ClassBadge } from "../review/class-badge";
import { ColorSquare } from "../player-avatar";
import { ErrorText, Panel } from "../ui";
import { AccuracyChart } from "./accuracy-chart";
import { StatsFilters } from "./filters";

type Props = { source: GameSource | null; timeClass: TimeClass | null };

/** Заголовок страницы: в серверной page.tsx текста нет, язык известен только в браузере. */
export function StatsHeading() {
  const { t } = useI18n();
  return <h1 className="text-2xl font-extrabold sm:text-3xl">{t.stats.title}</h1>;
}

/** Дашборд статистики. Фильтры в URL; при смене фильтра прежние данные остаются (приглушённо). */
export function StatsDashboard({ source, timeClass }: Props) {
  const { t } = useI18n();
  // Ответ помнит свой фильтр: пока новый не пришёл, старые данные видны приглушённо.
  const key = `${source ?? ""}|${timeClass ?? ""}`;
  // `failed` без `error` — неизвестная ошибка: текст по умолчанию берётся при рендере (на текущем языке).
  const [result, setResult] = useState<{ key: string; stats: Stats | null; failed: boolean; error: string | null } | null>(
    null,
  );

  useEffect(() => {
    let cancelled = false;
    api
      .stats({ source, timeClass })
      .then((stats) => !cancelled && setResult({ key, stats, failed: false, error: null }))
      .catch(
        (err) =>
          !cancelled &&
          setResult((prev) => ({
            key,
            stats: prev?.stats ?? null,
            failed: true,
            error: err instanceof ApiError ? err.message : null,
          })),
      );
    return () => {
      cancelled = true;
    };
  }, [key, source, timeClass]);

  const loading = result?.key !== key;
  const stats = result?.stats ?? null;
  const error = loading || !result?.failed ? null : (result.error ?? t.stats.loadError);
  return (
    <div className="flex flex-col gap-5">
      <StatsFilters source={source} timeClass={timeClass} />
      <ErrorText>{error}</ErrorText>
      {stats === null ? (
        !error && <BodySkeleton />
      ) : (
        <div className={`transition-opacity ${loading ? "opacity-50" : ""}`} aria-busy={loading}>
          <StatsBody stats={stats} filtered={source !== null || timeClass !== null} />
        </div>
      )}
    </div>
  );
}

function StatsBody({ stats, filtered }: { stats: Stats; filtered: boolean }) {
  const { t } = useI18n();
  const { empty } = t.stats;
  const { totals } = stats;
  if (totals.games === 0) {
    return (
      <Panel>
        <Empty title={filtered ? empty.filteredTitle : empty.noneTitle}>
          {filtered ? (
            empty.filteredText
          ) : (
            <>
              <Link href="/" className="font-bold text-green hover:underline">
                {empty.importLink}
              </Link>{" "}
              {empty.importText}
            </>
          )}
          {totals.games_without_color > 0 && <WithoutColor count={totals.games_without_color} />}
        </Empty>
      </Panel>
    );
  }
  const noAnalysis = totals.analyzed === 0;
  return (
    <div className="flex flex-col gap-5">
      <Totals stats={stats} />
      <Panel title={t.stats.accuracy.title}>
        {stats.accuracy.points.length > 1 ? (
          <>
            <AccuracyChart points={stats.accuracy.points} window={stats.accuracy.window} />
            <AccuracyTable stats={stats} />
          </>
        ) : (
          <Empty title={t.stats.accuracy.fewTitle}>{t.stats.accuracy.fewText}</Empty>
        )}
      </Panel>
      {stats.rating_groups.length > 0 && <RatingGroups stats={stats} />}
      {noAnalysis ? (
        <Panel>
          <Empty title={empty.noAnalysisTitle}>
            {empty.noAnalysisText}{" "}
            <Link href="/games" className="font-bold text-green hover:underline">
              {empty.noAnalysisLink}
            </Link>{" "}
            {empty.noAnalysisAfter}
          </Empty>
        </Panel>
      ) : (
        <div className="grid gap-5 lg:grid-cols-2">
          <Phases stats={stats} />
          <Classes stats={stats} />
        </div>
      )}
      <Openings stats={stats} />
      {!noAnalysis && <Motifs stats={stats} />}
    </div>
  );
}

function BodySkeleton() {
  return (
    <div aria-busy className="flex flex-col gap-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-xl bg-panel" />
        ))}
      </div>
      <div className="h-80 animate-pulse rounded-xl bg-panel" />
    </div>
  );
}

export function StatsSkeleton() {
  return (
    <div className="flex flex-col gap-5">
      <div className="h-9 w-2/3 animate-pulse rounded-lg bg-raised/50" />
      <BodySkeleton />
    </div>
  );
}

function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
      <p className="text-lg font-bold">{title}</p>
      <div className="max-w-md text-soft">{children}</div>
    </div>
  );
}

function WithoutColor({ count }: { count: number }) {
  const { t } = useI18n();
  return <p className="mt-2 text-sm text-muted">{t.stats.withoutColor(count)}</p>;
}

const percent = (part: number, total: number) => (total > 0 ? Math.round((100 * part) / total) : 0);

function Totals({ stats }: { stats: Stats }) {
  const { t } = useI18n();
  const labels = t.stats.totals;
  const { totals } = stats;
  const decided = totals.wins + totals.draws + totals.losses;
  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label={labels.games} value={String(totals.games)} note={labels.analyzed(totals.analyzed)} />
        <Tile
          label={labels.accuracy}
          value={totals.accuracy === null ? "—" : totals.accuracy.toFixed(1)}
          note={labels.accuracyOver(totals.with_accuracy)}
        />
        <Tile label={labels.wins} value={`${percent(totals.wins, decided)}%`} note={labels.winsOf(totals.wins, decided)} />
        <div className="flex flex-col justify-between gap-2 rounded-xl bg-panel p-4">
          <p className="text-xs font-semibold text-muted">{labels.results}</p>
          <ResultBar wins={totals.wins} draws={totals.draws} losses={totals.losses} />
          <p className="text-xs font-semibold text-soft">
            {totals.wins} / {totals.draws} / {totals.losses}
          </p>
        </div>
      </div>
      {totals.games_without_color > 0 && <WithoutColor count={totals.games_without_color} />}
    </div>
  );
}

function Tile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-xl bg-panel p-4">
      <p className="text-xs font-semibold text-muted">{label}</p>
      <p className="text-3xl font-extrabold">{value}</p>
      <p className="text-xs font-semibold text-soft">{note}</p>
    </div>
  );
}

// Победы / ничьи / поражения — цветами исхода, как значки в таблице партий.
const OUTCOME_COLORS = { wins: "#7fb04a", draws: "#9b958c", losses: "#e8402e" };

function ResultBar({ wins, draws, losses }: { wins: number; draws: number; losses: number }) {
  const { t } = useI18n();
  const total = wins + draws + losses;
  const parts = [
    ["wins", wins],
    ["draws", draws],
    ["losses", losses],
  ] as const;
  return (
    <div
      role="img"
      aria-label={parts.map(([key, value]) => t.stats.results[key](value)).join(", ")}
      className="flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full bg-sunken"
    >
      {total > 0 &&
        parts.map(([key, value]) =>
          value > 0 ? (
            <span
              key={key}
              title={t.stats.results[key](value)}
              className="h-full"
              style={{ width: `${(100 * value) / total}%`, background: OUTCOME_COLORS[key] }}
            />
          ) : null,
        )}
    </div>
  );
}

function AccuracyTable({ stats }: { stats: Stats }) {
  const { t, lang } = useI18n();
  const labels = t.stats.accuracy;
  const rows = stats.accuracy.points.slice(-30).reverse();
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer font-semibold text-soft hover:text-ink">{labels.table}</summary>
      <table className="mt-2 w-full">
        <thead className="text-left text-xs text-muted">
          <tr>
            <th className="py-1 font-semibold">{labels.date}</th>
            <th className="py-1 font-semibold">{labels.opponent}</th>
            <th className="py-1 text-right font-semibold">{labels.accuracy}</th>
            <th className="py-1 text-right font-semibold">{labels.averageColumn}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((point) => (
            <tr key={point.game_id} className="border-t border-line">
              <td className="py-1.5 text-soft">{formatDate(point.played_at, lang) ?? "—"}</td>
              <td className="max-w-0 truncate py-1.5">
                <Link href={`/games/${point.game_id}`} className="hover:underline">
                  {point.opponent}
                </Link>
              </td>
              <td className="py-1.5 text-right font-bold" title={t.stats.kinds[point.kind]}>
                {point.accuracy.toFixed(1)}
              </td>
              <td className="py-1.5 text-right text-soft">{point.moving_avg.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

function Meter({ value, color }: { value: number; color: string }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-sunken">
      <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color }} />
    </div>
  );
}

function Phases({ stats }: { stats: Stats }) {
  const { t } = useI18n();
  return (
    <Panel title={t.stats.phases.title}>
      <ul className="flex flex-col gap-4">
        {stats.phases.map(({ phase, accuracy, games }) => (
          <li key={phase} className="flex items-center gap-3">
            {accuracy === null ? (
              <span className="h-6 w-6 shrink-0 rounded-full bg-sunken" />
            ) : (
              <ClassBadge value={phaseClass(accuracy)} size={24} />
            )}
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-bold">{t.common.phases[phase]}</span>
                <span className="text-xs font-semibold text-muted">{t.common.games(games)}</span>
              </div>
              <Meter value={accuracy ?? 0} color={accuracy === null ? "transparent" : CLASS_COLORS[phaseClass(accuracy)]} />
            </div>
            <span className="w-12 text-right text-lg font-extrabold">{accuracy === null ? "—" : accuracy.toFixed(1)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-muted">{t.stats.phases.note}</p>
    </Panel>
  );
}

function Classes({ stats }: { stats: Stats }) {
  const { t } = useI18n();
  const items = new Map(stats.classes.items.map((item) => [item.class as ClassKey, item]));
  const max = Math.max(1, ...stats.classes.items.map((item) => item.share));
  return (
    <Panel
      title={t.stats.classes.title}
      aside={<span className="text-xs font-semibold text-muted">{t.stats.classes.aside}</span>}
    >
      <ul className="flex flex-col gap-2">
        {CLASS_ORDER.map((key) => {
          const item = items.get(key);
          if (!item) return null;
          return (
            <li key={key} className="grid grid-cols-[1.5rem_minmax(0,7.5rem)_minmax(0,1fr)_2.75rem_3rem] items-center gap-2 text-sm">
              <ClassBadge value={key} size={22} />
              <span className="truncate font-semibold">{classPlural(t, key)}</span>
              <Meter value={(100 * item.share) / max} color={CLASS_COLORS[key]} />
              <span className="text-right font-bold">{item.per_game.toFixed(1)}</span>
              <span className="text-right text-soft">{item.share.toFixed(1)}%</span>
            </li>
          );
        })}
      </ul>
      <p className="mt-4 text-xs text-muted">{t.stats.classes.note(stats.classes.moves, stats.classes.games)}</p>
    </Panel>
  );
}

function Openings({ stats }: { stats: Stats }) {
  const { t } = useI18n();
  const { white, black } = stats.openings;
  if (white.length === 0 && black.length === 0) return null;
  return (
    <Panel title={t.stats.openings.title}>
      <div className="grid gap-6 lg:grid-cols-2">
        <OpeningTable color="white" title={t.stats.openings.asWhite} rows={white} />
        <OpeningTable color="black" title={t.stats.openings.asBlack} rows={black} />
      </div>
    </Panel>
  );
}

function OpeningTable({ color, title, rows }: { color: "white" | "black"; title: string; rows: OpeningStat[] }) {
  const { t } = useI18n();
  const labels = t.stats.openings;
  return (
    <div className="min-w-0">
      <h3 className="mb-2 flex items-center gap-2 font-bold">
        <ColorSquare color={color} />
        {title}
      </h3>
      {rows.length === 0 ? (
        <p className="text-sm text-muted">{labels.noGames}</p>
      ) : (
        <table className="w-full table-fixed text-sm">
          <thead className="text-left text-xs text-muted">
            <tr>
              <th className="py-1 font-semibold">{labels.opening}</th>
              <th className="w-12 py-1 text-right font-semibold">{labels.games}</th>
              <th className="w-24 py-1 pl-3 font-semibold sm:w-32">{labels.results}</th>
              <th className="w-14 py-1 text-right font-semibold">{labels.accuracy}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.eco}-${row.name}`} className="border-t border-line">
                <td className="py-2 pr-2">
                  <p className="line-clamp-2 font-semibold leading-snug" title={row.name}>
                    {row.name}
                  </p>
                  <p className="text-xs text-muted">{row.eco}</p>
                </td>
                <td className="py-2 text-right font-bold">{row.games}</td>
                <td className="py-2 pl-3">
                  <ResultBar wins={row.wins} draws={row.draws} losses={row.losses} />
                  <p className="mt-1 text-xs text-soft">
                    {labels.winRate(percent(row.wins, row.wins + row.draws + row.losses))}
                  </p>
                </td>
                <td className="py-2 text-right font-bold">{row.accuracy === null ? "—" : row.accuracy.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function Motifs({ stats }: { stats: Stats }) {
  const { t } = useI18n();
  const max = Math.max(1, ...stats.motifs.map((motif) => motif.count));
  return (
    <Panel title={t.stats.motifs.title}>
      {stats.motifs.length === 0 ? (
        <p className="text-soft">{t.stats.motifs.none}</p>
      ) : (
        <ul className="flex flex-col gap-5">
          {stats.motifs.map((motif) => (
            <li key={motif.type} className="flex flex-col gap-2">
              <div className="grid grid-cols-[minmax(0,15rem)_minmax(0,1fr)_2.5rem] items-center gap-3">
                <span className="truncate font-bold">{motifName(t, motif.type)}</span>
                <Meter value={(100 * motif.count) / max} color={CLASS_COLORS.mistake} />
                <span className="text-right font-extrabold">{motif.count}</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {motif.examples.map((example) => {
                  const cls: ClassKey = example.is_miss && !["mistake", "blunder"].includes(example.class) ? "miss" : example.class;
                  return (
                    <Link
                      key={example.move_id}
                      href={`/games/${example.game_id}?ply=${example.ply}`}
                      className="flex min-h-9 max-w-full items-center gap-1.5 rounded-lg bg-raised/60 px-2.5 text-xs font-semibold text-soft hover:bg-raised hover:text-ink"
                    >
                      <ClassBadge value={cls} size={16} />
                      <span className="font-bold text-ink">
                        {example.fullmove}
                        {example.color === "white" ? "." : "…"} {example.san}
                      </span>
                      <span className="truncate">{t.stats.versus(example.opponent)}</span>
                    </Link>
                  );
                })}
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-4 text-xs text-muted">{t.stats.motifs.note}</p>
    </Panel>
  );
}

/** Точность пользователя против средней у игроков его рейтинга — по контролям. */
function RatingGroups({ stats }: { stats: Stats }) {
  const { t } = useI18n();
  const labels = t.stats.groups;
  return (
    <Panel title={labels.title}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs font-bold text-muted">
              <th className="py-1.5 pr-3 font-bold">{labels.control}</th>
              <th className="py-1.5 pr-3 text-right font-bold">{labels.rating}</th>
              <th className="py-1.5 pr-3 text-right font-bold">{labels.you}</th>
              <th className="py-1.5 pr-3 text-right font-bold">{labels.group}</th>
              <th className="py-1.5 text-right font-bold">{labels.diff}</th>
            </tr>
          </thead>
          <tbody>
            {stats.rating_groups.map((row) => {
              const diff = row.accuracy - row.group_accuracy;
              return (
                <tr key={row.time_class} className="border-t border-line font-semibold">
                  <td className="py-2 pr-3">
                    {t.stats.timeClasses[row.time_class]}
                    <span className="ml-2 text-xs text-muted">{labels.games(row.games)}</span>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">{row.rating}</td>
                  <td className="py-2 pr-3 text-right font-extrabold tabular-nums">{row.accuracy.toFixed(1)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums text-soft">{row.group_accuracy.toFixed(1)}</td>
                  <td className={`py-2 text-right font-extrabold tabular-nums ${diff >= 0 ? "text-green" : "text-danger"}`}>
                    {diff >= 0 ? "+" : "−"}
                    {Math.abs(diff).toFixed(1)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs font-semibold text-muted">{labels.note}</p>
    </Panel>
  );
}
