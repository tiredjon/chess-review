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
    legendGroup: "Средняя для вашего рейтинга",
    group: (rating: number, value: string) => `рейтинг ${rating}: в среднем ${value}`,
    average: (value: string) => `среднее ${value}`,
    table: "Таблицей (последние 30)",
    date: "Дата",
    opponent: "Соперник",
    accuracy: "Точность",
    averageColumn: "Среднее",
  },
  versus: (name: string) => `против ${name}`,
  // Сравнение с рейтинговой группой (сессия 11).
  groups: {
    title: "Вы и ваша рейтинговая группа",
    note: "Средняя точность игроков вашего рейтинга и контроля на Chess.com (по 20 500 партиям из открытых архивов). Только партии Chess.com с точностью «как у Chess.com».",
    control: "Контроль",
    rating: "Рейтинг",
    you: "Вы",
    group: "Группа",
    diff: "Разница",
    games: (n: number) => `${n} ${ruPlural(n, "партия", "партии", "партий")}`,
  },
  phases: {
    title: "Точность по фазам",
    note: "Точность фаз — по формуле «как у Chess.com», как в обзоре партии. Официальная точность Chess.com может отличаться: по фазам они её не отдают.",
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
  brilliant: {
    title: "Блестящие ходы",
    summary: (count: number, games: number) =>
      `${count} ${ruPlural(count, "ход", "хода", "ходов")} в ${games} ${ruPlural(games, "партии", "партиях", "партиях")}`,
    none: "Пока ни одного: блестящий ход — лучший или почти лучший ход с жертвой материала. Он ещё случится!",
    more: (n: number) => `Показать ещё ${n}`,
    open: (move: string, name: string) => `Открыть разбор: ${move} против ${name}`,
    limited: (shown: number) => `Показаны последние ${shown}.`,
  },
  // Время на ход по часам партий (%clk, сессия 15).
  time: {
    title: "Время на ход",
    troubleErrors: "Ошибки в цейтноте",
    hastyErrors: "Поспешные ошибки",
    troubleGames: "Партий с цейтнотом",
    ofErrors: (percent: number, total: number) => `${percent}% из ${total} ${ruPlural(total, "ошибки", "ошибок", "ошибок")}`,
    noErrors: "ошибок не было",
    ofGames: (n: number) => `из ${n} с часами`,
    ratio: (value: string) => `В цейтноте вы ошибаетесь в ${value} раза чаще, чем при запасе времени.`,
    bucketsTitle: "Точность по остатку на часах",
    buckets: {
      over_half: "Больше 50%",
      quarter_half: "25–50%",
      tenth_quarter: "10–25%",
      under_tenth: "Цейтнот, < 10%",
    },
    moves: (n: number) => `${n} ${ruPlural(n, "ход", "хода", "ходов")}`,
    errorsPer100: (value: string) => `${value} ош./100`,
    errorsHint: "Ошибок и зевков на 100 ходов",
    phasesTitle: "В среднем на ход",
    note: "Только разобранные партии с часами (%clk). Ошибки — ошибки и зевки. Цейтнот — перед ходом меньше 10% начального времени; поспешная ошибка — сделана быстрее 2% начального времени (но не меньше секунды) вне цейтнота.",
  },
};
