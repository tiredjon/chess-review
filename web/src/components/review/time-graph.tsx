"use client";

import { Bar, BarChart, Cell, ReferenceLine, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";
import { CLASS_COLORS, displayClass, type ClassKey } from "@/lib/classes";
import { moveNumber, type Ply } from "@/lib/chess";
import { formatClock, formatSpent } from "@/lib/clock";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { GameClock } from "@/lib/types";

type Point = {
  index: number;
  /** Секунды: белые — вверх, чёрные — вниз. */
  value: number;
  label: string;
  spent: string;
  left: string | null;
  color: string;
  trouble: boolean;
};

// Окрашиваются только ошибки: видно, на быстрых или долгих ходах они случились.
const MARKED: ClassKey[] = ["inaccuracy", "mistake", "miss", "blunder"];

/** Время на каждый ход (по `%clk`); клик — переход к ходу. */
export function TimeGraph({
  clock,
  plies,
  cursor,
  onSelect,
  compact = false,
}: {
  clock: GameClock;
  plies: Ply[];
  cursor: number;
  onSelect: (index: number) => void;
  compact?: boolean;
}) {
  const { t } = useI18n();
  const data: Point[] = plies.map((ply, index) => {
    const entry = clock.plies[index];
    const seconds = (entry?.spent_cs ?? 0) / 100;
    const value = ply.move ? displayClass(ply.move) : null;
    const neutral = ply.color === "white" ? "var(--graph-white)" : "#8d877e";
    return {
      index: index + 1,
      value: ply.color === "white" ? seconds : -seconds,
      label: `${moveNumber(ply)} ${ply.san}`,
      spent: entry?.spent_cs != null ? formatSpent(entry.spent_cs, t) : "—",
      left: entry?.clock_cs != null ? formatClock(entry.clock_cs) : null,
      color: value && MARKED.includes(value) ? CLASS_COLORS[value] : neutral,
      trouble: entry?.trouble ?? false,
    };
  });
  const peak = Math.max(1, ...data.map((point) => Math.abs(point.value)));

  return (
    <figure className="flex shrink-0 flex-col gap-1">
      <figcaption className="flex items-center justify-between text-xs font-bold text-muted">
        <span>{t.review.time.graph}</span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="h-2 w-2 rounded-sm bg-[#e06c5a]" />
          {t.review.time.troubleLegend}
        </span>
      </figcaption>
      <div className="overflow-hidden rounded-md bg-[var(--graph-black)]">
        <BarChart
          data={data}
          responsive
          style={{ width: "100%", height: compact ? 56 : 84 }}
          margin={{ top: 2, right: 0, bottom: 2, left: 0 }}
          barCategoryGap={1}
          cursor="pointer"
          accessibilityLayer={false}
          onClick={(state) => {
            const index = Number(state.activeTooltipIndex);
            if (Number.isInteger(index)) onSelect(index + 1);
          }}
        >
          <XAxis dataKey="index" hide />
          <YAxis domain={[-peak, peak]} hide />
          <ReferenceLine y={0} stroke="#8d877e" strokeOpacity={0.7} />
          <Bar dataKey="value" isAnimationActive={false} minPointSize={1}>
            {data.map((point) => (
              <Cell
                key={point.index}
                fill={point.color}
                stroke={point.trouble ? "#e06c5a" : "none"}
                strokeWidth={point.trouble ? 1.5 : 0}
                fillOpacity={point.index === cursor ? 1 : 0.85}
              />
            ))}
          </Bar>
          {cursor > 0 && <ReferenceLine x={cursor} stroke="var(--green)" strokeWidth={2} />}
          <Tooltip content={(props) => <TooltipBox {...props} />} cursor={{ fill: "#ffffff14" }} isAnimationActive={false} />
        </BarChart>
      </div>
    </figure>
  );
}

function TooltipBox({ active, payload }: TooltipContentProps) {
  const { t } = useI18n();
  const point = payload?.[0]?.payload as Point | undefined;
  if (!active || !point) return null;
  return (
    <div className="rounded-md bg-sunken px-2 py-1 text-xs font-bold text-ink shadow-md">
      <span>{point.label}</span>
      <span className="ml-2 text-muted">{point.spent}</span>
      {point.left && <span className="ml-2 text-muted">{t.review.time.left(point.left)}</span>}
    </div>
  );
}
