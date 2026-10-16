"use client";

import { useRouter } from "next/navigation";
import { CartesianGrid, ComposedChart, Line, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";
import { formatDate, OUTCOME_LABELS } from "@/lib/format";
import type { AccuracyKind, AccuracyPoint } from "@/lib/types";
import { TIME_CLASS_NAMES } from "./filters";

const GAME_DOT = "#d8d3cb";
const TREND = "var(--green)";

export const KIND_LABELS: Record<AccuracyKind, string> = {
  official: "по данным Chess.com",
  cc: "наша оценка, близкая к Chess.com",
  lichess: "по формуле Lichess",
};

type Datum = AccuracyPoint & { index: number };

/** Точность по партиям (точки) и скользящее среднее (линия); клик по точке — разбор партии. */
export function AccuracyChart({ points, window }: { points: AccuracyPoint[]; window: number }) {
  const router = useRouter();
  const data: Datum[] = points.map((point, index) => ({ ...point, index }));
  const low = Math.min(...points.map((p) => p.accuracy));
  const floor = Math.max(0, Math.floor((low - 5) / 10) * 10);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs font-semibold text-soft" aria-hidden>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: GAME_DOT }} />
          Точность партии
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded-full" style={{ background: TREND }} />
          Среднее за {window} партий
        </span>
      </div>
      <ComposedChart
        data={data}
        responsive
        style={{ width: "100%", height: 240 }}
        margin={{ top: 8, right: 8, bottom: 0, left: -18 }}
        cursor="pointer"
        onClick={(state) => {
          const index = Number(state.activeTooltipIndex);
          if (Number.isInteger(index) && data[index]) router.push(`/games/${data[index].game_id}`);
        }}
      >
        <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.07)" />
        <XAxis dataKey="index" type="number" domain={[0, Math.max(1, data.length - 1)]} hide />
        <YAxis
          domain={[floor, 100]}
          tickCount={Math.min(6, (100 - floor) / 10 + 1)}
          tick={{ fill: "var(--muted)", fontSize: 11, fontWeight: 600 }}
          axisLine={false}
          tickLine={false}
        />
        <Line
          dataKey="accuracy"
          stroke="none"
          isAnimationActive={false}
          dot={{ r: 3.5, fill: GAME_DOT, fillOpacity: 0.75, stroke: "var(--panel)", strokeWidth: 1.5 }}
          activeDot={{ r: 5.5, fill: GAME_DOT, stroke: "var(--panel)", strokeWidth: 2 }}
        />
        <Line
          dataKey="moving_avg"
          type="monotone"
          stroke={TREND}
          strokeWidth={2.5}
          dot={false}
          activeDot={{ r: 4, fill: TREND, stroke: "var(--panel)", strokeWidth: 2 }}
          isAnimationActive={false}
        />
        <Tooltip content={TooltipBox} cursor={{ stroke: "#8d877e", strokeWidth: 1 }} isAnimationActive={false} />
      </ComposedChart>
    </div>
  );
}

function TooltipBox({ active, payload }: TooltipContentProps) {
  const point = payload?.[0]?.payload as Datum | undefined;
  if (!active || !point) return null;
  return (
    <div className="max-w-60 rounded-md bg-sunken px-3 py-2 text-xs shadow-lg">
      <p className="text-base font-extrabold text-ink">
        {point.accuracy.toFixed(1)}
        <span className="ml-2 text-xs font-semibold text-muted">среднее {point.moving_avg.toFixed(1)}</span>
      </p>
      <p className="font-semibold text-soft">
        против {point.opponent}
        {point.outcome && `, ${OUTCOME_LABELS[point.outcome].toLowerCase()}`}
      </p>
      <p className="text-muted">
        {[formatDate(point.played_at), TIME_CLASS_NAMES[point.time_class]].filter(Boolean).join(" · ")}
      </p>
      <p className="text-muted">{KIND_LABELS[point.kind]}</p>
    </div>
  );
}
