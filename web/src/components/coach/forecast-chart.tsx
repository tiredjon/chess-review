"use client";

import { useEffect, useRef, useState } from "react";
import type { Forecast } from "@/lib/coach-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { formatShortDay } from "./copy";

const HEIGHT = 260;
const PAD = { top: 14, right: 12, bottom: 26, left: 40 };
const GOLD = "#f5c451";

const time = (date: string) => new Date(`${date.slice(0, 10)}T12:00:00`).getTime();

/** График рейтинга на SVG (без библиотек, как график оценки в разборе): история, коридор p10–p90,
 *  медиана p50 до цели и линия цели. Ширину берёт у контейнера, чтобы подписи не сжимались. */
export function ForecastChart({ forecast }: { forecast: Forecast }) {
  const { t, lang } = useI18n();
  const c = t.coach.forecast.chart;
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const update = () => setWidth(Math.max(260, Math.round(node.clientWidth)));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const { history, projection, target_rating: target, current_rating: current, start_rating: start } = forecast;
  const points = [...history.map((p) => ({ x: time(p.date), y: p.rating })), ...projection.flatMap((p) => [{ x: time(p.date), y: p.p10 }, { x: time(p.date), y: p.p90 }])];
  if (points.length === 0) points.push({ x: 0, y: current });

  const xs = points.map((p) => p.x);
  const ys = [...points.map((p) => p.y), target, current];
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs, x0 + 7 * 86_400_000);
  const rawMin = Math.min(...ys);
  const rawMax = Math.max(...ys);
  const padY = Math.max(20, (rawMax - rawMin) * 0.08);
  const step = rawMax - rawMin > 400 ? 100 : rawMax - rawMin > 160 ? 50 : 25;
  const y0 = Math.floor((rawMin - padY) / step) * step;
  const y1 = Math.ceil((rawMax + padY) / step) * step;

  const innerW = width - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const sx = (x: number) => PAD.left + ((x - x0) / (x1 - x0)) * innerW;
  const sy = (y: number) => PAD.top + (1 - (y - y0) / (y1 - y0)) * innerH;
  const line = (list: { x: number; y: number }[]) => list.map((p, i) => `${i === 0 ? "M" : "L"}${sx(p.x).toFixed(1)} ${sy(p.y).toFixed(1)}`).join(" ");

  const histLine = line(history.map((p) => ({ x: time(p.date), y: p.rating })));
  const last = history.at(-1);
  // Прогноз начинается от последней точки истории: коридор «растёт» из неё.
  const anchor = last ? { x: time(last.date), y: last.rating } : null;
  const p50 = anchor ? line([anchor, ...projection.map((p) => ({ x: time(p.date), y: p.p50 }))]) : "";
  const upper = projection.map((p) => `${sx(time(p.date)).toFixed(1)} ${sy(p.p90).toFixed(1)}`);
  const lower = [...projection].reverse().map((p) => `${sx(time(p.date)).toFixed(1)} ${sy(p.p10).toFixed(1)}`);
  const band =
    projection.length > 0 && anchor
      ? `M${sx(anchor.x).toFixed(1)} ${sy(anchor.y).toFixed(1)} L${upper.join(" L")} L${lower.join(" L")} Z`
      : "";

  const yTicks: number[] = [];
  for (let y = y0; y <= y1; y += step) yTicks.push(y);
  const xTickCount = width < 420 ? 3 : 5;
  const xTicks = Array.from({ length: xTickCount }, (_, i) => x0 + ((x1 - x0) * i) / (xTickCount - 1));
  const targetY = sy(target);
  const today = anchor ? sx(anchor.x) : null;

  return (
    <figure className="flex flex-col gap-2">
      <div ref={ref} className="w-full overflow-hidden rounded-lg bg-[var(--graph-black)]">
        <svg role="img" aria-label={c.label(start, current, target)} width={width} height={HEIGHT} viewBox={`0 0 ${width} ${HEIGHT}`} className="block">
          {yTicks.map((y) => (
            <g key={y}>
              <line x1={PAD.left} x2={width - PAD.right} y1={sy(y)} y2={sy(y)} stroke="#ffffff" strokeOpacity={0.08} />
              <text x={PAD.left - 6} y={sy(y) + 4} textAnchor="end" fontSize={11} fontWeight={700} fill="var(--muted)">
                {y}
              </text>
            </g>
          ))}
          {xTicks.map((x, i) => (
            <text key={i} x={Math.min(Math.max(sx(x), PAD.left + 16), width - PAD.right - 16)} y={HEIGHT - 8} textAnchor="middle" fontSize={11} fontWeight={700} fill="var(--muted)">
              {formatShortDay(new Date(x).toISOString(), lang)}
            </text>
          ))}
          {band && <path d={band} fill="var(--green)" fillOpacity={0.2} />}
          <line x1={PAD.left} x2={width - PAD.right} y1={targetY} y2={targetY} stroke={GOLD} strokeWidth={1.5} strokeDasharray="6 4" />
          <text x={width - PAD.right - 4} y={targetY - 6} textAnchor="end" fontSize={12} fontWeight={800} fill={GOLD}>
            {c.target(target)}
          </text>
          {today !== null && <line x1={today} x2={today} y1={PAD.top} y2={HEIGHT - PAD.bottom} stroke="#ffffff" strokeOpacity={0.15} strokeDasharray="2 3" />}
          {p50 && <path d={p50} fill="none" stroke="var(--green)" strokeWidth={2.5} strokeDasharray="7 4" strokeLinecap="round" />}
          {histLine && <path d={histLine} fill="none" stroke="#ffffff" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />}
          {anchor && (
            <>
              <circle cx={sx(anchor.x)} cy={sy(anchor.y)} r={5} fill="#ffffff" stroke="var(--graph-black)" strokeWidth={2} />
              <text x={sx(anchor.x)} y={sy(anchor.y) - 10} textAnchor={sx(anchor.x) > width - 60 ? "end" : "middle"} fontSize={12} fontWeight={800} fill="#ffffff">
                {current}
              </text>
            </>
          )}
        </svg>
      </div>
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-xs font-bold text-muted">
        <Legend color="#ffffff" label={c.history} />
        <Legend color="var(--green)" label={c.median} dashed />
        <Legend color="var(--green)" label={c.corridor} band />
        <Legend color={GOLD} label={c.target(target)} dashed />
      </figcaption>
    </figure>
  );
}

function Legend({ color, label, dashed = false, band = false }: { color: string; label: string; dashed?: boolean; band?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      <svg aria-hidden width="18" height="10" viewBox="0 0 18 10">
        {band ? (
          <rect x="0" y="1" width="18" height="8" rx="2" fill={color} fillOpacity={0.3} />
        ) : (
          <line x1="0" x2="18" y1="5" y2="5" stroke={color} strokeWidth="2.5" strokeDasharray={dashed ? "5 3" : undefined} />
        )}
      </svg>
      {label}
    </span>
  );
}
