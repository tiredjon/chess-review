// i18n интерфейса: словари в коде (ru — источник типа, en повторяет его), без библиотеки.
// Язык — users.lang у вошедшего пользователя, у гостя — localStorage / язык браузера
// (provider.tsx). Компоненты берут словарь хуком `useI18n()`; модули вне React (клиент API)
// — через `currentDict()`, который провайдер держит в синхроне.
import { en } from "./en";
import { ru } from "./ru";

export type Dict = typeof ru;
export type Lang = "ru" | "en";
export const LANGS: Lang[] = ["ru", "en"];
export const DEFAULT_LANG: Lang = "ru";

export const DICTS: Record<Lang, Dict> = { ru, en };

export const isLang = (value: unknown): value is Lang => value === "ru" || value === "en";

let current: Lang = DEFAULT_LANG;

export function setCurrentLang(lang: Lang) {
  current = lang;
}

export const currentLang = () => current;
export const currentDict = () => DICTS[current];
