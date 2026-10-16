"use client";

// Текущий язык — внешнее хранилище для useSyncExternalStore: без контекста и setState в
// эффектах, при гидратации сначала язык по умолчанию (как в пререндере), затем настоящий.
// Пока идёт проверка входа (AuthGate), на экране только заставка — смена языка не мигает.
import { useSyncExternalStore } from "react";
import { DEFAULT_LANG, DICTS, type Dict, isLang, type Lang, setCurrentLang } from ".";

const STORAGE_KEY = "lang";
const listeners = new Set<() => void>();
let lang: Lang | null = null;

function initialLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isLang(stored)) return stored;
  } catch {
    // Хранилище недоступно (приватный режим) — язык браузера.
  }
  return navigator.language.toLowerCase().startsWith("ru") ? "ru" : navigator.language ? "en" : DEFAULT_LANG;
}

function readLang(): Lang {
  if (lang === null) {
    lang = initialLang();
    setCurrentLang(lang);
    document.documentElement.lang = lang;
  }
  return lang;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Сменить язык интерфейса (и запомнить для гостя / следующего входа). */
export function setLang(next: Lang) {
  lang = next;
  setCurrentLang(next);
  document.documentElement.lang = next;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // Не запомнится — не страшно.
  }
  listeners.forEach((listener) => listener());
}

export function useLang(): Lang {
  return useSyncExternalStore(subscribe, readLang, () => DEFAULT_LANG);
}

/** Словарь текущего языка: `const { t, lang } = useI18n(); t.common.nav.games`. */
export function useI18n(): { lang: Lang; t: Dict; setLang: (lang: Lang) => void } {
  const current = useLang();
  return { lang: current, t: DICTS[current], setLang };
}
