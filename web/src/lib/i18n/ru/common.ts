import { ruPlural } from "../plural";

// Общие подписи: навигация, классы ходов, фазы, мотивы, исходы, кнопки.
export const common = {
  appName: "Chess Review",
  description: "Разбор шахматных партий на Stockfish с объяснениями ошибок",
  nav: {
    label: "Навигация",
    toHome: "Chess Review — на главную",
    home: "Главная",
    games: "Партии",
    stats: "Статистика",
    puzzles: "Пазлы",
    profile: "Профиль",
    logout: "Выйти",
  },
  // Заголовки вкладки браузера («… — Chess Review»).
  titles: {
    home: "Разбор партий",
    games: "Партии",
    review: "Разбор партии",
    stats: "Статистика",
    puzzles: "Пазлы",
    profile: "Профиль",
    login: "Вход",
    register: "Регистрация",
  },
  actions: {
    retry: "Повторить",
    save: "Сохранить",
    saved: "Сохранено",
    cancel: "Отмена",
    close: "Закрыть",
    loading: "Загрузка…",
    more: "Показать ещё",
  },
  language: {
    label: "Язык",
    ru: "Русский",
    en: "English",
  },
  // Классы ходов (SPEC §4.5); цвета — lib/classes.ts.
  classes: {
    brilliant: { label: "Блестящий", plural: "Блестящие" },
    great: { label: "Отличный", plural: "Отличные" },
    best: { label: "Лучший", plural: "Лучшие" },
    excellent: { label: "Превосходный", plural: "Превосходные" },
    good: { label: "Хороший", plural: "Хорошие" },
    book: { label: "Теория", plural: "Теория" },
    forced: { label: "Вынужденный", plural: "Вынужденные" },
    inaccuracy: { label: "Неточность", plural: "Неточности" },
    mistake: { label: "Ошибка", plural: "Ошибки" },
    miss: { label: "Упущение", plural: "Упущения" },
    blunder: { label: "Зевок", plural: "Зевки" },
  },
  phases: {
    opening: "Дебют",
    middlegame: "Миттельшпиль",
    endgame: "Эндшпиль",
  },
  // Тактические мотивы (backend/app/review/motifs/, как в explain/templates.py) и темы пазлов.
  motifs: {
    hanging_piece: "Незащищённая фигура",
    fork: "Вилка",
    pin: "Связка",
    skewer: "Линейный удар",
    discovered_attack: "Вскрытое нападение",
    discovered_check: "Вскрытый шах",
    double_check: "Двойной шах",
    mate_in_n: "Мат",
    mate_threat: "Угроза мата",
    back_rank: "Мат по последней горизонтали",
    trapped_piece: "Пойманная фигура",
    removing_defender: "Устранение защитника",
    overload: "Перегрузка",
    promotion: "Превращение пешки",
    promotion_threat: "Угроза превращения",
    only_move: "Единственный ход",
  } as Record<string, string>,
  outcome: { win: "Победа", loss: "Поражение", draw: "Ничья" },
  colors: { white: "белые", black: "чёрные", White: "Белые", Black: "Чёрные" },
  // Контроль времени: `10+5`, `3 мин`, `30 с`, `1 д.`.
  time: {
    seconds: (n: number | string) => `${n} с`,
    minutes: (n: number | string) => `${n} мин`,
    days: (n: number | string) => `${n} д.`,
  },
  // Сколько ждать: «45 с», «12 мин», «2 ч».
  wait: (seconds: number) => {
    if (seconds < 60) return `${seconds} с`;
    if (seconds < 3600) return `${Math.ceil(seconds / 60)} мин`;
    return `${Math.ceil(seconds / 3600)} ч`;
  },
  games: (n: number) => `${n} ${ruPlural(n, "партия", "партии", "партий")}`,
};
