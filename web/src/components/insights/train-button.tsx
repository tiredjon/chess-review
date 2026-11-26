"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { openingKey, type Finding } from "@/lib/insights-api";
import { repertoireApi } from "@/lib/repertoire-api";
import { Button } from "../ui";
import { trainHref } from "./copy";

const GREEN =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-green px-5 text-[15px] font-bold text-white shadow-[0_4px_0_0_var(--green-edge)] hover:bg-green-hover active:translate-y-[2px] active:shadow-none max-sm:w-full sm:self-start";

/** «Тренировать» по `train` вывода: пазлы по теме / фазе / дебюту, забег на время, тренажёр
 *  эндшпиля, курс по своей линии дебюта (как «Учить эту линию» в репертуаре). */
export function TrainButton({ finding }: { finding: Finding }) {
  const { t } = useI18n();
  const train = finding.train;
  if (train === null) return null;
  const copy = t.insights.train;

  if (train.kind === "course") return <CourseButton finding={finding} />;

  const href = trainHref(finding);
  if (href === null) return null;
  if (train.kind !== "play" && train.available === 0) {
    return <p className="text-sm font-semibold text-muted sm:self-start">{train.kind === "endgames" ? copy.noEndgames : copy.noPuzzles}</p>;
  }
  const label =
    train.kind === "endgames"
      ? copy.endgames(train.available)
      : train.kind === "play"
        ? copy.play
        : href.includes("mode=rush")
          ? copy.rush(train.available)
          : copy.puzzles(train.available);
  return (
    <Link href={href} className={GREEN}>
      {label}
    </Link>
  );
}

/** Курс по самой частой своей линии этого дебюта: линия — из репертуара, курс — идемпотентно. */
function CourseButton({ finding }: { finding: Finding }) {
  const { t } = useI18n();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { color, family } = openingKey(finding.key);

  const open = async () => {
    setBusy(true);
    setError(null);
    try {
      const openings = await repertoireApi.openings(color);
      const line = openings
        .filter((o) => o.name.split(":")[0].trim() === family && o.line_uci.length > 0)
        .sort((a, b) => b.games - a.games)[0];
      if (!line) {
        router.push("/openings");
        return;
      }
      const course = await repertoireApi.createCourse({ line_uci: line.line_uci, color, name: line.name });
      router.push(`/openings/courses/${course.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.insights.train.courseFailed);
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-1.5 max-sm:w-full sm:self-start">
      <Button onClick={open} disabled={busy} className="min-h-11 px-5 max-sm:w-full">
        {busy ? t.insights.train.opening : t.insights.train.course}
      </Button>
      {error && <p className="text-sm font-semibold text-danger">{error}</p>}
    </div>
  );
}
