"use client";

import type { ReactNode } from "react";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Button, ErrorText } from "../ui";
import type { Section } from "./use-section";

/** Содержимое блока: скелетон, ошибка с «Повторить» или готовый вид. */
export function BlockBody<T>({ section, height = 160, children }: { section: Section<T>; height?: number; children: (data: T) => ReactNode }) {
  const { t } = useI18n();
  if (section.data !== null) return <>{children(section.data)}</>;
  if (section.error) {
    return (
      <div className="flex flex-col items-start gap-2">
        <ErrorText>{section.error}</ErrorText>
        <Button variant="raised" size="sm" onClick={section.reload}>
          {t.coach.retry}
        </Button>
      </div>
    );
  }
  return <div aria-busy className="animate-pulse rounded-lg bg-raised/40" style={{ height }} />;
}

/** Пустое состояние внутри блока: заголовок, пояснение и действия. */
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-2 py-6 text-center">
      <p className="text-lg font-bold">{title}</p>
      <div className="flex max-w-md flex-col items-center gap-3 text-soft">{children}</div>
    </div>
  );
}

export const GREEN_LINK =
  "inline-flex min-h-11 items-center justify-center rounded-lg bg-green px-5 text-[15px] font-bold text-white shadow-[0_4px_0_0_var(--green-edge)] hover:bg-green-hover active:translate-y-[2px] active:shadow-none max-sm:w-full";

export const RAISED_LINK =
  "inline-flex min-h-11 items-center justify-center rounded-lg bg-raised px-5 text-[15px] font-bold text-soft shadow-[0_3px_0_0_rgba(0,0,0,0.35)] hover:bg-raised-hover hover:text-ink active:translate-y-[2px] active:shadow-none max-sm:w-full";
