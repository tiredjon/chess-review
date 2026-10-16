import { ruPlural } from "../plural";

// Страница статистики: фильтры, плитки итогов, график точности, фазы, классы, дебюты, мотивы.
export const stats = {
  title: "Статистика",
  loadError: "Не удалось загрузить статистику",
  filters: {
    source: "Источник",
    allSources: "Все площадки",
    timeControl: "Контроль времени",
    anyTimeControl: "Любой контроль",
  },
  timeClasses: {
    bullet: "Пуля",
    blitz: "Блиц",
    rapid: "Рапид",
    daily: "По переписке",
  },
  // Откуда точность партии (AccuracyKind).
  kinds: {
    official: "по данным Chess.com",
    cc: "наша оценка, близкая к Chess.com",
    lichess: "по формуле Lichess",
  },
  empty: {
    filteredTitle: "Под этот фильтр партий нет",
    filteredText: "Выберите другой источник или контроль времени.",
    noneTitle: "Статистики пока нет",
    importLink: "Загрузите партии",
    importText: "с Lichess или Chess.com — статистика считается по вашим партиям.",
    noAnalysisTitle: "Нет разобранных партий",
    noAnalysisText: "Фазы, классы ходов и частые ошибки считаются по партиям с готовым разбором.",
    noAnalysisLink: "Откройте партию",
    noAnalysisAfter: "и запустите анализ.",
  },
  withoutColor: (n: number) =>
    `${n} ${ruPlural(n, "партия", "партии", "партий")} без вашего цвета не учтены: укажите ник Lichess или Chess.com при импорте, чтобы вставленные PGN определялись.`,
  totals: {
    games: "Партий",
    analyzed: (n: number) => `разобрано ${n}`,
    accuracy: "Средняя точность",
    accuracyOver: (n: number) => `по ${n} ${ruPlural(n, "партии", "партиям", "партиям")}`,
    wins: "Побед",
    winsOf: (wins: number, decided: number) => `${wins} из ${decided}`,
    results: "Результаты",
  },
  // Подписи частей полосы результатов (title и aria-label).
  results: {
    wins: (n: number) => `${n} побед`,
    draws: (n: number) => `${n} ничьих`,
    losses: (n: number) => `${n} поражений`,
  },
  accuracy: {
    title: "Точность по партиям",
    fewTitle: "Мало данных для графика",
    fewText: "Точность появляется после разбора партии (или берётся с Chess.com, если партию разбирали там).",
    legendGame: "Точность партии",
    legendAverage: (window: number) => `Среднее за ${window} партий`,
    average: (value: string) => `среднее ${value}`,
    table: "Таблицей (последние 30)",
    date: "Дата",
    opponent: "Соперник",
    accuracy: "Точность",
    averageColumn: "Среднее",
  },
  versus: (name: string) => `против ${name}`,
  phases: {
    title: "Точность по фазам",
    note: "Точность фаз — по формуле Lichess, как в обзоре партии. С общей точностью «как у Chess.com» напрямую не сравнивается: сравнивайте фазы между собой.",
  },
  classes: {
    title: "Классы ходов",
    aside: "на партию · доля ходов",
    note: (moves: number, games: number) =>
      `${moves} ваших ходов в ${games} разобранных ${ruPlural(games, "партии", "партиях", "партиях")}. «Упущения» — флаг поверх класса: соперник ошибся, а вы не наказали.`,
  },
  openings: {
    title: "Дебюты",
    asWhite: "Белыми",
    asBlack: "Чёрными",
    noGames: "Партий нет.",
    opening: "Дебют",
    games: "Партий",
    results: "Результаты",
    accuracy: "Точн.",
    winRate: (percent: number) => `${percent}% побед`,
  },
  motifs: {
    title: "Частые мотивы ошибок",
    none: "В ваших ошибках не нашлось тактических мотивов — отличный знак.",
    note: "Мотив считается, если он был в опровержении вашей ошибки или в упущенной лучшей линии; по одному разу на ход.",
  },
};
