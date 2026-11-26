// Текст вывода из kind / key / stats (сервер отдаёт только числа) и ссылки на тренировку.
import type { Dict, Lang } from "@/lib/i18n";
import { openingKey, type Finding } from "@/lib/insights-api";
import { motifName } from "@/lib/motifs";
import type { Phase } from "@/lib/types";

export type FindingCopy = {
  kind: string;
  title: string;
  text: string;
  /** Подписи столбиков сравнения: пользователь и база. */
  valueLabel: string;
  baseLabel: string;
};

const PHASES: Phase[] = ["opening", "middlegame", "endgame"];
const asPhase = (key: string): Phase => PHASES.find((phase) => phase === key) ?? "middlegame";

export function formatPercent(value: number, lang: Lang, digits = 1): string {
  return new Intl.NumberFormat(lang === "ru" ? "ru-RU" : "en-US", { maximumFractionDigits: digits }).format(value);
}

export function findingCopy(t: Dict, lang: Lang, finding: Finding): FindingCopy {
  const c = t.insights;
  const { value, baseline, count, total } = finding.stats;
  // Доли ходов — с десятыми, очки — целыми.
  const digits = finding.kind === "opening" || finding.kind === "conversion" ? 0 : 1;
  const v = formatPercent(value, lang, digits);
  const b = formatPercent(baseline, lang, digits);
  const kind = c.kinds[finding.kind];
  switch (finding.kind) {
    case "motif":
      return {
        kind,
        title: c.motif.title(motifName(t, finding.key)),
        text: c.motif.text(v, b, count, total),
        valueLabel: c.motif.value,
        baseLabel: c.motif.base,
      };
    case "phase": {
      const phase = asPhase(finding.key);
      return {
        kind,
        title: c.phase.title(c.phaseIn[phase]),
        text: c.phase.text(c.phaseIn[phase], c.phaseBase[phase], v, b),
        valueLabel: c.phase.value,
        baseLabel: c.phase.base(c.phaseBase[phase]),
      };
    }
    case "time": {
      const copy = finding.key === "hasty" ? c.time.hasty : c.time.trouble;
      return {
        kind,
        title: copy.title,
        text: copy.text(v, b, count, total),
        valueLabel: copy.value,
        baseLabel: copy.base,
      };
    }
    case "opening": {
      const { color, family } = openingKey(finding.key);
      return {
        kind,
        title: c.opening.title(family, color),
        text: c.opening.text(count, v, b, color),
        valueLabel: c.opening.value,
        baseLabel: c.opening.base,
      };
    }
    case "conversion":
      return {
        kind,
        title: c.conversion.title,
        text: c.conversion.text(count, total, v, b),
        valueLabel: c.conversion.value,
        baseLabel: c.conversion.base,
      };
  }
}

/** Ссылка «Тренировать» (общий контракт SPEC «Сессия 16»); курс открывается действием, не ссылкой. */
export function trainHref(finding: Finding): string | null {
  const train = finding.train;
  if (train === null) return null;
  switch (train.kind) {
    case "puzzles": {
      // Цейтнот — решать быстрее: забег на время; остальное — пазлы по теме без часов.
      const query = new URLSearchParams({ mode: finding.id === "time:trouble" ? "rush" : "practice" });
      if (train.query.theme) query.set("theme", train.query.theme);
      if (train.query.phase) query.set("phase", train.query.phase);
      if (train.query.eco) query.set("eco", train.query.eco);
      return `/puzzles?${query.toString()}`;
    }
    case "endgames":
      return "/play/endgames?tab=mine";
    case "play":
      return "/play";
    case "course":
      return null;
  }
}
