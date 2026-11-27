// Общие подписи и форматирование экрана тренера.
import type { Gap, Metric, MetricDelta, MetricKind } from "@/lib/coach-api";
import type { Dict, Lang } from "@/lib/i18n";
import { openingKey, type Finding, type FindingKind, type Train } from "@/lib/insights-api";
import { lessonText } from "@/lib/coach-lessons";
import { motifName } from "@/lib/motifs";

const dayFormats: Partial<Record<Lang, Intl.DateTimeFormat>> = {};

/** `2026-12-01` (или полный ISO) → «1 дек. 2026 г.» / «Dec 1, 2026». Полдень — чтобы пояс не сдвигал день. */
export function formatDay(value: string, lang: Lang): string {
  dayFormats[lang] ??= new Intl.DateTimeFormat(lang, { day: "numeric", month: "short", year: "numeric" });
  const date = value.length <= 10 ? new Date(`${value}T12:00:00`) : new Date(value);
  return dayFormats[lang].format(date);
}

const shortFormats: Partial<Record<Lang, Intl.DateTimeFormat>> = {};

export function formatShortDay(value: string, lang: Lang): string {
  shortFormats[lang] ??= new Intl.DateTimeFormat(lang, { day: "numeric", month: "short" });
  return shortFormats[lang].format(new Date(`${value.slice(0, 10)}T12:00:00`));
}

export function formatNumber(value: number, lang: Lang, digits = 1): string {
  return new Intl.NumberFormat(lang === "ru" ? "ru-RU" : "en-US", { maximumFractionDigits: digits }).format(value);
}

/** Название метрики, мотива или дебюта («цвет:семейство» → семейство). */
export function itemName(t: Dict, kind: MetricKind, key: string): string {
  if (kind === "motif") return motifName(t, key);
  if (kind === "opening") return openingKey(key).family;
  return t.coach.diagnosis.metrics[key] ?? key;
}

/** `focus` задания: тип мотива, ключ метрики или семейство дебюта. */
export function focusName(t: Dict, focus: string, lang: Lang): string {
  return t.coach.diagnosis.metrics[focus] ?? t.common.motifs[focus] ?? lessonText(lang, focus)?.title ?? focus.replace(/_/g, " ");
}

const PERCENT_KEYS = new Set(["accuracy", "accuracy_opening", "accuracy_middlegame", "accuracy_endgame", "conversion", "resilience", "time_trouble_share"]);

/** Значение метрики с единицей: доли и точность — `%`, остальное — «на 100 ходов». */
export function formatValue(t: Dict, lang: Lang, kind: MetricKind, key: string, value: number | null): string {
  if (value === null) return "—";
  const number = formatNumber(value, lang, 1);
  if (kind !== "metric" || PERCENT_KEYS.has(key)) return `${number}%`;
  return `${number}`;
}

export const metricUnit = (t: Dict, kind: MetricKind, key: string): string | null =>
  kind === "metric" && key.endsWith("_per_100") ? t.coach.diagnosis.unitPer100 : null;

export const deltaTone = (delta: MetricDelta): "better" | "worse" | "same" => {
  if (delta.before === null || delta.after === null) return "same";
  const diff = delta.after - delta.before;
  if (Math.abs(diff) < 0.05) return "same";
  return (diff > 0) === (delta.direction === "higher_better") ? "better" : "worse";
};

export const statusColor = (status: Metric["status"]): string =>
  status === "weakness" ? "var(--danger)" : status === "strength" ? "var(--green)" : "var(--muted)";

/** Вид вывода 16.1, чтобы переиспользовать `TrainButton` (ему нужны только `id`, `key`, `train`). */
function findingKind(kind: MetricKind, key: string): FindingKind {
  if (kind === "motif") return "motif";
  if (kind === "opening") return "opening";
  if (key === "conversion") return "conversion";
  if (key === "time_trouble_share" || key === "hasty_per_100") return "time";
  return "phase";
}

/** Слабая/сильная сторона или урок → `Finding` для общей кнопки «Тренировать». */
export function trainFinding(kind: MetricKind, key: string, train: Train | null): Finding {
  const timeTrouble = key === "time_trouble_share" || key === "time_management";
  return {
    id: timeTrouble ? "time:trouble" : `${kind}:${key}`,
    kind: findingKind(kind, key),
    key,
    severity: "low",
    score: 0,
    stats: { value: 0, baseline: 0, count: 0, total: 0 },
    examples: [],
    train,
  };
}

export const gapFinding = (gap: Gap): Finding => trainFinding(gap.kind, gap.key, gap.train);
