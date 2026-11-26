"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n/use-i18n";
import { motifName } from "@/lib/motifs";
import type { Phase, PuzzleFilters, PuzzleThemes } from "@/lib/types";
import { Chip, fieldClass } from "../ui";
import { hasFilters, NO_FILTERS } from "./puzzle-view";

type Props = {
  filters: PuzzleFilters;
  themes: PuzzleThemes | null;
  onChange: (filters: PuzzleFilters) => void;
};

/** Выбор темы, фазы хода-источника и дебюта партии — с числами пазлов из `/puzzles/themes`. */
export function FilterBar({ filters, themes, onChange }: Props) {
  const { t } = useI18n();
  const copy = t.puzzles.filters;
  const themeList = themes?.themes ?? [];
  // Тема или дебют из ссылки, которых в списке нет (все решены/удалены), всё равно видны выбранными.
  const themeRows = filters.theme && !themeList.some((row) => row.theme === filters.theme)
    ? [...themeList, { theme: filters.theme, total: 0, due: 0, solved: 0 }]
    : themeList;
  const openings = themes?.openings ?? [];
  const openingRows = filters.eco && !openings.some((row) => row.eco === filters.eco)
    ? [...openings, { eco: filters.eco, name: null, total: 0 }]
    : openings;

  // На телефоне фильтры сворачиваются (иначе доска уезжает за экран); сворачиваются по умолчанию,
  // если выбор пришёл из ссылки. На широких экранах всегда развёрнуты.
  const [open, setOpen] = useState(!hasFilters(filters));
  const summary = [
    filters.theme && motifName(t, filters.theme),
    filters.phase && t.common.phases[filters.phase],
    filters.eco,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div role="group" aria-label={copy.label} className="flex flex-col gap-3 rounded-xl bg-panel p-3 sm:p-4">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="puzzle-filter-body"
        onClick={() => setOpen((value) => !value)}
        className="flex min-h-9 items-center gap-2 text-left text-sm font-bold lg:hidden"
      >
        <span className="text-xs font-bold uppercase tracking-wide text-muted">{copy.active}</span>
        <span className="min-w-0 flex-1 truncate text-ink">{summary || copy.all}</span>
        <span aria-hidden className={`text-muted transition-transform ${open ? "rotate-180" : ""}`}>
          ▾
        </span>
      </button>
      <div id="puzzle-filter-body" className={`${open ? "flex" : "hidden"} flex-col gap-3 lg:flex`}>
        <Row label={copy.theme}>
          <Chip active={filters.theme === null} onClick={() => onChange({ ...filters, theme: null })} className="min-h-9">
            {copy.all}
          </Chip>
          {themeRows.map((row) => (
            <Chip
              key={row.theme}
              active={filters.theme === row.theme}
              title={copy.themeTitle(row.total, row.due, row.solved)}
              onClick={() => onChange({ ...filters, theme: filters.theme === row.theme ? null : row.theme })}
              className="min-h-9"
            >
              {motifName(t, row.theme)} <span className="font-bold text-muted">{row.total}</span>
            </Chip>
          ))}
        </Row>
        <Row label={copy.phase}>
          <Chip active={filters.phase === null} onClick={() => onChange({ ...filters, phase: null })} className="min-h-9">
            {copy.all}
          </Chip>
          {(themes?.phases ?? PHASE_PLACEHOLDER).map((row) => (
            <Chip
              key={row.phase}
              active={filters.phase === row.phase}
              onClick={() => onChange({ ...filters, phase: filters.phase === row.phase ? null : row.phase })}
              className="min-h-9"
            >
              {t.common.phases[row.phase]} {themes && <span className="font-bold text-muted">{row.total}</span>}
            </Chip>
          ))}
        </Row>
        <label className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-3">
          <span className="text-xs font-bold uppercase tracking-wide text-muted sm:w-20 sm:shrink-0">{copy.opening}</span>
          <select
            value={filters.eco ?? ""}
            onChange={(event) => onChange({ ...filters, eco: event.target.value || null })}
            className={`${fieldClass} min-h-10 sm:max-w-md`}
          >
            <option value="">{copy.allOpenings}</option>
            {openingRows.map((row) => (
              <option key={row.eco} value={row.eco}>
                {row.eco}
                {row.name ? ` · ${row.name}` : ""} ({row.total})
              </option>
            ))}
          </select>
        </label>
        {hasFilters(filters) && (
          <button
            type="button"
            onClick={() => onChange(NO_FILTERS)}
            className="self-start text-sm font-bold text-green hover:underline"
          >
            {copy.reset}
          </button>
        )}
      </div>
    </div>
  );
}

const PHASE_PLACEHOLDER: { phase: Phase; total: number }[] = [
  { phase: "opening", total: 0 },
  { phase: "middlegame", total: 0 },
  { phase: "endgame", total: 0 },
];

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:gap-3">
      <span className="pt-2 text-xs font-bold uppercase tracking-wide text-muted sm:w-20 sm:shrink-0">{label}</span>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

/** Сводка действующих фильтров для режима повторения (там выбор не нужен, но фильтры из ссылки работают). */
export function ActiveFilters({ filters, onChange }: { filters: PuzzleFilters; onChange: (filters: PuzzleFilters) => void }) {
  const { t } = useI18n();
  if (!hasFilters(filters)) return null;
  const chips: { key: keyof PuzzleFilters; label: string }[] = [];
  if (filters.theme) chips.push({ key: "theme", label: motifName(t, filters.theme) });
  if (filters.phase) chips.push({ key: "phase", label: t.common.phases[filters.phase] });
  if (filters.eco) chips.push({ key: "eco", label: filters.eco });
  return (
    <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={t.puzzles.filters.active}>
      <span className="text-xs font-bold uppercase tracking-wide text-muted">{t.puzzles.filters.active}</span>
      {chips.map(({ key, label }) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange({ ...filters, [key]: null })}
          aria-label={`${label} ✕`}
          className="flex min-h-9 items-center gap-1.5 rounded-lg bg-raised px-3 text-sm font-semibold text-ink ring-2 ring-green ring-inset hover:bg-raised-hover"
        >
          {label}
          <span aria-hidden className="text-muted">
            ✕
          </span>
        </button>
      ))}
      <button type="button" onClick={() => onChange(NO_FILTERS)} className="px-2 text-sm font-bold text-green hover:underline">
        {t.puzzles.filters.reset}
      </button>
    </div>
  );
}
