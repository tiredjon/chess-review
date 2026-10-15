import { accuracyTone, CLASS_META, CLASS_ORDER, displayClass, PHASE_LABELS, type ClassKey } from "@/lib/classes";
import type { Color, MoveOut, Phase, PhaseAccuracy } from "@/lib/types";
import { ClassBadge } from "./class-badge";

// Эти счётчики показываются всегда, даже нулевые: ради них карточку и смотрят.
const ALWAYS: ClassKey[] = ["inaccuracy", "mistake", "blunder"];

export function PlayerCard({
  name,
  elo,
  color,
  isUser,
  accuracy,
  phases,
  moves,
}: {
  name: string;
  elo: number | null;
  color: Color;
  isUser: boolean;
  accuracy: number | null;
  phases: PhaseAccuracy | null;
  moves: MoveOut[];
}) {
  const counts = new Map<ClassKey, number>();
  for (const move of moves) {
    if (move.color !== color) continue;
    const value = displayClass(move);
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  const shown = CLASS_ORDER.filter((key) => ALWAYS.includes(key) || counts.get(key));
  const phaseValues = phases?.[color] ?? {};

  return (
    <section
      aria-label={`${color === "white" ? "Белые" : "Чёрные"}: ${name}`}
      className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-3"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2">
            <span
              aria-hidden
              className={`h-3.5 w-3.5 shrink-0 rounded-sm border border-muted/50 ${
                color === "white" ? "bg-white" : "bg-[#2a3240]"
              }`}
            />
            <span className={`truncate ${isUser ? "font-semibold" : "font-medium"}`}>{name}</span>
          </p>
          {elo && <p className="mt-0.5 pl-5.5 text-sm text-muted">{elo}</p>}
        </div>
        {accuracy !== null && (
          <div className="text-right">
            <p
              className="rounded-md px-2 py-0.5 text-xl font-semibold text-white"
              style={{ background: accuracyTone(accuracy) }}
            >
              {accuracy.toFixed(1)}
            </p>
            <p className="mt-0.5 text-xs text-muted">точность</p>
          </div>
        )}
      </div>

      {moves.length > 0 && (
        <ul className="flex flex-wrap gap-x-3 gap-y-1.5 text-sm" aria-label="Ходы по классам">
          {shown.map((key) => (
            <li key={key} className="flex items-center gap-1" title={CLASS_META[key].label}>
              <ClassBadge value={key} size={16} title={false} />
              <span className="sr-only">{CLASS_META[key].label}:</span>
              <span className={counts.get(key) ? "font-medium" : "text-muted"}>{counts.get(key) ?? 0}</span>
            </li>
          ))}
        </ul>
      )}

      {phases && (
        <dl className="flex flex-wrap gap-x-5 gap-y-1 border-t border-line pt-2.5 text-sm">
          {(Object.keys(PHASE_LABELS) as Phase[]).map((phase) => {
            const value = phaseValues[phase];
            return (
              <div key={phase}>
                <dt className="text-xs text-muted">{PHASE_LABELS[phase]}</dt>
                <dd className="font-medium">
                  {value != null ? value.toFixed(0) : "—"}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
    </section>
  );
}
