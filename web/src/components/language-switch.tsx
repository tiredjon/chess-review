"use client";

import { LANGS, type Lang } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/use-i18n";

/** Переключатель RU / EN. `onChange` — у вошедшего (сохранить в профиль), иначе язык гостя. */
export function LanguageSwitch({
  onChange,
  disabled,
  className = "",
}: {
  onChange?: (lang: Lang) => void;
  disabled?: boolean;
  className?: string;
}) {
  const { lang, t, setLang } = useI18n();
  return (
    <div role="radiogroup" aria-label={t.common.language.label} className={`inline-flex rounded-lg bg-sunken p-1 ${className}`}>
      {LANGS.map((option) => (
        <button
          key={option}
          type="button"
          role="radio"
          aria-checked={lang === option}
          disabled={disabled}
          lang={option}
          aria-label={t.common.language[option]}
          title={t.common.language[option]}
          onClick={() => (onChange ? onChange(option) : setLang(option))}
          className={`min-h-9 min-w-12 rounded-md px-3 text-sm font-bold uppercase transition-colors disabled:opacity-50 ${
            lang === option ? "bg-raised text-ink shadow-[0_2px_0_0_rgba(0,0,0,0.35)]" : "text-muted hover:text-ink"
          }`}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
