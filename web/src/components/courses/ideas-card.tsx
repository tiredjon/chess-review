"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { IDEA_LESSONS, lessonText } from "@/lib/coach-lessons";
import type { PawnBreak, PositionIdeas, RenderedIdeas, Side } from "@/lib/courses-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { ColorMark } from "./shared";

const SIDES: Side[] = ["white", "black"];

/** «…d5» — прорыв, который можно сыграть; «f7–f5» — к которому готовятся. */
const breakLabel = (brk: PawnBreak) =>
  brk.legal_now && brk.san ? `${brk.side === "black" ? "…" : ""}${brk.san}` : `${brk.uci.slice(0, 2)}–${brk.uci.slice(2, 4)}`;

/**
 * Идеи позиции (сессия 13.2): структура, планы обеих сторон, прорывы, форпосты, слабости,
 * линии. Тексты планов — готовые (`RenderedIdeas` с сервера на языке пользователя), факты
 * (клетки, прорывы) — из `PositionIdeas` узла, подписи к ним — словарь.
 *
 *  - `learner` — цвет ученика: его планы первыми и с пометкой «вы»;
 *  - `compact` — для тренажёра: не больше двух планов на сторону, без фактов, кроме прорывов.
 */
export function IdeasCard({
  text,
  raw,
  learner,
  compact = false,
}: {
  text: RenderedIdeas | undefined;
  raw: PositionIdeas | null;
  learner: Side;
  compact?: boolean;
}) {
  const { t, lang } = useI18n();
  const l = t.courses.ideas;
  const order = learner === "white" ? SIDES : [...SIDES].reverse();
  const plans = order
    .map((side) => ({ side, items: (text?.ideas ?? []).filter((idea) => idea.side === side) }))
    .filter((group) => group.items.length > 0);
  const breaks = raw?.breaks ?? [];
  const outposts = raw?.outposts ?? [];
  const weaknesses = raw?.weaknesses ?? [];
  const halfOpen = order.flatMap((side) => {
    const files = raw?.half_open_files?.[side] ?? [];
    return files.length > 0 ? [l.halfOpen(l.sideOf[side], files.join(", "))] : [];
  });
  const files = [...(raw?.open_files.length ? [l.open(raw.open_files.join(", "))] : []), ...halfOpen];
  const empty = !text?.structure_title && plans.length === 0 && breaks.length === 0;

  if (empty) return <p className="text-sm text-muted">{l.empty}</p>;

  return (
    <div className="flex flex-col gap-3">
      {text?.structure_title && (
        <div className="rounded-lg bg-sunken/70 px-3 py-2.5">
          <p className="text-[15px] font-extrabold">{text.structure_title}</p>
          {text.structure_summary && !compact && (
            <p className="mt-1 text-sm leading-snug text-soft">{text.structure_summary}</p>
          )}
        </div>
      )}

      {plans.length > 0 && (
        <Section title={compact ? null : l.plans}>
          <div className="flex flex-col gap-2.5">
            {plans.map(({ side, items }) => (
              <div key={side}>
                <p className="mb-1 flex items-center gap-1.5 text-xs font-bold tracking-wide text-muted uppercase">
                  <ColorMark color={side} size={16} />
                  {l.side[side]}
                  {side === learner && <span className="rounded bg-green/20 px-1 py-px text-[10px] text-green normal-case">{l.you}</span>}
                </p>
                <ul className="flex flex-col gap-1.5">
                  {(compact ? items.slice(0, 2) : items).map((idea, index) => (
                    <li key={`${idea.key}-${index}`} className="flex gap-2 text-sm leading-snug text-soft">
                      <span
                        aria-hidden
                        className={`mt-[7px] size-1.5 shrink-0 rounded-full ${side === "white" ? "bg-[#f2efe9]" : "bg-[#8b8781]"}`}
                      />
                      <span>
                        {idea.text}
                        {!compact && IDEA_LESSONS[idea.key] && (
                          <>
                            {" "}
                            <Link
                              href={`/coach/lessons/${IDEA_LESSONS[idea.key]}`}
                              title={lessonText(lang, IDEA_LESSONS[idea.key])?.title}
                              className="font-bold whitespace-nowrap text-green hover:underline"
                            >
                              {l.theory}
                            </Link>
                          </>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Section>
      )}

      {breaks.length > 0 && (
        <Section title={l.breaks}>
          <Chips>
            {breaks.map((brk) => (
              <Chip key={`${brk.side}-${brk.uci}`} side={brk.side}>
                <span className="font-extrabold text-ink">{breakLabel(brk)}</span>
                <span className="text-muted">{brk.legal_now ? l.breakNow : l.breakPrepare}</span>
              </Chip>
            ))}
          </Chips>
        </Section>
      )}

      {!compact && outposts.length > 0 && (
        <Section title={l.outposts}>
          <Chips>
            {outposts.map((outpost) => (
              <Chip key={`${outpost.side}-${outpost.square}`} side={outpost.side}>
                <span className="font-extrabold text-ink">{outpost.square}</span>
              </Chip>
            ))}
          </Chips>
        </Section>
      )}

      {!compact && weaknesses.length > 0 && (
        <Section title={l.weaknesses}>
          <Chips>
            {weaknesses.map((weakness) => (
              <Chip key={`${weakness.side}-${weakness.square}-${weakness.kind}`} side={weakness.side}>
                <span className="font-extrabold text-ink">{weakness.square}</span>
                <span className="text-muted">{l.kinds[weakness.kind] ?? weakness.kind}</span>
              </Chip>
            ))}
          </Chips>
        </Section>
      )}

      {!compact && files.length > 0 && (
        <Section title={l.files}>
          <p className="text-sm text-soft">{files.join(" · ")}</p>
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string | null; children: ReactNode }) {
  return (
    <div>
      {title && <h4 className="mb-1.5 text-xs font-bold tracking-wide text-muted uppercase">{title}</h4>}
      {children}
    </div>
  );
}

const Chips = ({ children }: { children: ReactNode }) => <div className="flex flex-wrap gap-1.5">{children}</div>;

/** Факт про сторону: кружок цвета стороны + текст. */
function Chip({ side, children }: { side: Side; children: ReactNode }) {
  const { t } = useI18n();
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md bg-raised px-2 py-1 text-[13px]" title={t.courses.ideas.side[side]}>
      <span
        aria-label={t.courses.ideas.side[side]}
        className={`size-2.5 shrink-0 rounded-full ${side === "white" ? "bg-[#f2efe9]" : "bg-[#403d39] ring-1 ring-white/40"}`}
      />
      {children}
    </span>
  );
}
