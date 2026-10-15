"use client";

import { Area, AreaChart, ReferenceLine, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";
import { CLASS_META, displayClass, type ClassKey } from "@/lib/classes";
import { moveNumber, type Ply } from "@/lib/chess";
import { formatEval, whiteWinPercent, type WhiteEval } from "@/lib/eval";

type Point = { index: number; white: number; label: string; eval: string; mark: ClassKey | null };

// Точки на графике — только у ходов, о которых стоит знать.
const MARKED: ClassKey[] = ["brilliant", "great", "inaccuracy", "mistake", "miss", "blunder"];

/** График оценки (win% белых по позициям); клик — переход к позиции. */
export function EvalGraph({
  evals,
  plies,
  cursor,
  onSelect,
  compact = false,
}: {
  evals: WhiteEval[];
  plies: Ply[];
  cursor: number;
  onSelect: (index: number) => void;
  /** Пониже — в режиме разбора по ходам. */
  compact?: boolean;
}) {
  const data: Point[] = evals.map((evaluation, index) => {
    const ply = index > 0 ? plies[index - 1] : null;
    const value = ply?.move ? displayClass(ply.move) : null;
    return {
      index,
      white: whiteWinPercent(evaluation),
      label: ply ? `${moveNumber(ply)} ${ply.san}` : "Начало",
      eval: formatEval(evaluation),
      mark: value && MARKED.includes(value) ? value : null,
    };
  });

  return (
    <div className="shrink-0 overflow-hidden rounded-md bg-[var(--graph-black)]">
      <AreaChart
        data={data}
        responsive
        style={{ width: "100%", height: compact ? 72 : 104 }}
        margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
        cursor="pointer"
        accessibilityLayer={false}
        onClick={(state) => {
          const index = Number(state.activeTooltipIndex);
          if (Number.isInteger(index)) onSelect(index);
        }}
      >
        <XAxis dataKey="index" type="number" domain={[0, Math.max(1, data.length - 1)]} hide />
        <YAxis domain={[0, 100]} hide />
        <ReferenceLine y={50} stroke="#8d877e" strokeOpacity={0.7} />
        <Area
          type="monotone"
          dataKey="white"
          baseValue={0}
          stroke="none"
          fill="var(--graph-white)"
          fillOpacity={1}
          isAnimationActive={false}
          dot={renderDot}
          activeDot={{ r: 4, fill: "var(--green)", stroke: "white", strokeWidth: 1.5 }}
        />
        <ReferenceLine x={cursor} stroke="var(--green)" strokeWidth={2} />
        <Tooltip content={TooltipBox} cursor={{ stroke: "#8d877e", strokeWidth: 1 }} isAnimationActive={false} />
      </AreaChart>
    </div>
  );
}

function renderDot(props: { cx?: number; cy?: number; payload?: Point; index?: number }) {
  const { cx, cy, payload, index } = props;
  if (!payload?.mark || cx === undefined || cy === undefined) return <g key={`dot-${index}`} />;
  return (
    <circle
      key={`dot-${index}`}
      cx={cx}
      cy={cy}
      r={4}
      fill={CLASS_META[payload.mark].color}
      stroke="none"
    />
  );
}

function TooltipBox({ active, payload }: TooltipContentProps) {
  const point = payload?.[0]?.payload as Point | undefined;
  if (!active || !point) return null;
  return (
    <div className="rounded-md bg-sunken px-2 py-1 text-xs font-bold text-ink shadow-md">
      <span>{point.label}</span>
      <span className="ml-2 text-muted">{point.eval}</span>
    </div>
  );
}
