"use client";

import Link from "next/link";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import type { Lesson } from "@/lib/coach-api";
import { lessonText } from "@/lib/coach-lessons";
import { useI18n } from "@/lib/i18n/use-i18n";
import { ExampleBoard } from "../insights/example-board";
import { TrainButton } from "../insights/train-button";
import { Button, ErrorText, Panel } from "../ui";
import { BlockBody, Empty } from "./block";
import { trainFinding } from "./copy";
import { coach } from "./source";
import { useSection } from "./use-section";

export function LessonView({ lessonKey }: { lessonKey: string }) {
  const { t } = useI18n();
  const section = useSection(() => coach.lesson(lessonKey), t.coach.lesson.loadError);
  return (
    <div className="flex flex-col gap-4">
      <Link href="/coach" className="w-fit text-sm font-bold text-muted hover:text-ink">
        {t.coach.lesson.toCoach}
      </Link>
      {section.code === "lesson_not_found" || (section.data === null && section.error && section.code?.startsWith("lesson")) ? (
        <Panel>
          <Empty title={t.coach.lesson.notFound} />
        </Panel>
      ) : (
        <BlockBody section={section} height={320}>
          {(lesson) => <Body lessonKey={lessonKey} lesson={lesson} onRead={section.setData} />}
        </BlockBody>
      )}
    </div>
  );
}

function Body({ lessonKey, lesson, onRead }: { lessonKey: string; lesson: Lesson; onRead: (lesson: Lesson) => void }) {
  const { t, lang } = useI18n();
  const c = t.coach.lesson;
  const text = lessonText(lang, lessonKey);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const markRead = async () => {
    setBusy(true);
    setError(null);
    try {
      const item = await coach.readLesson(lessonKey);
      onRead({ ...lesson, read: item.read });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : c.markFailed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <article className="flex flex-col gap-4">
          <header className="flex flex-col gap-1.5">
            <p className="text-xs font-bold text-muted uppercase tracking-wide">{c.kind[lesson.kind]}</p>
            <h1 className="text-2xl font-extrabold leading-tight break-words sm:text-3xl">{text?.title ?? c.placeholderTitle}</h1>
            {text ? <p className="max-w-3xl text-lg text-soft">{text.summary}</p> : <p className="max-w-3xl text-soft">{c.placeholderText}</p>}
          </header>
          {text?.sections.map((section) => (
            <section key={section.heading} className="flex max-w-3xl flex-col gap-1.5">
              <h2 className="text-lg font-extrabold">{section.heading}</h2>
              {section.body.split("\n\n").map((paragraph, i) => (
                <p key={i} className="leading-relaxed text-soft">
                  {paragraph}
                </p>
              ))}
            </section>
          ))}
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
            {lesson.train && <TrainButton finding={trainFinding(lesson.kind === "motif" ? "motif" : "metric", lessonKey, lesson.train)} />}
            {lesson.read ? (
              <p className="flex min-h-11 items-center font-extrabold text-green">{c.isRead}</p>
            ) : (
              <Button variant="raised" disabled={busy} onClick={() => void markRead()} className="min-h-11 px-5 max-sm:w-full">
                {busy ? c.marking : c.read}
              </Button>
            )}
          </div>
          <ErrorText>{error}</ErrorText>
        </article>
      </Panel>

      <Panel title={c.examplesTitle}>
        {lesson.examples.length === 0 ? (
          <p className="text-soft">{c.noExamples}</p>
        ) : (
          <ul className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
            {lesson.examples.map((example) => (
              <li key={`${example.game_id}-${example.ply}`} className="min-w-0">
                <ExampleBoard example={example} />
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
