import { ruPlural } from "../plural";

// Слабые места (/stats/weaknesses, сессия 16.1): текст выводов строится здесь из kind / key / stats
// ответа `GET /insights/me` — сервер отдаёт только числа (SPEC «Сессия 16»).
// Числа (`v`, `b`) приходят уже отформатированными по языку (`12,5`).

type Phase = "opening" | "middlegame" | "endgame";

const games = (n: number) => `${n} ${ruPlural(n, "партия", "партии", "партий")}`;

export const insights = {
  title: "Слабые места",
  subtitle: "Что чаще всего стоит вам очков: выводы по разобранным партиям, примеры и тренировка.",
  loadError: "Не удалось загрузить слабые места",
  basis: (n: number) => `По ${n} ${ruPlural(n, "разобранной партии", "разобранным партиям", "разобранным партиям")}`,
  severity: { high: "Важно", medium: "Заметно", low: "Стоит присмотреться" },
  kinds: { motif: "Упущенная тактика", phase: "Фаза партии", time: "Время", opening: "Дебют", conversion: "Реализация" },
  empty: {
    fewTitle: "Пока мало разобранных партий",
    fewText: (analyzed: number, min: number) =>
      `Слабые места ищутся, когда разобрано хотя бы ${games(min)} — сейчас ${analyzed}. Откройте партии и запустите анализ: выводы появятся здесь сами.`,
    gamesLink: "К партиям",
    noneTitle: "Явных слабых мест не нашлось",
    noneText:
      "Ни один показатель не выделяется так сильно, чтобы это не было случайностью. Загляните сюда, когда разберёте больше партий.",
    filteredText: "С этим фильтром — меньше данных: попробуйте все площадки и любой контроль.",
  },
  // В фразах «ошибки в эндшпиле», «…чем в миттельшпиле».
  phaseIn: { opening: "в дебюте", middlegame: "в миттельшпиле", endgame: "в эндшпиле" } as Record<Phase, string>,
  // С чем сравнивается фаза (дебют — с остальной игрой; миттельшпиль и эндшпиль — друг с другом).
  phaseBase: { opening: "в остальной игре", middlegame: "в эндшпиле", endgame: "в миттельшпиле" } as Record<Phase, string>,
  motif: {
    title: (motif: string) => motif,
    text: (v: string, b: string, count: number, total: number) =>
      `Ход с этим мотивом был лучшим ${total} ${ruPlural(total, "раз", "раза", "раз")} — вы упустили его ${count} (${v} %). Остальные мотивы вы упускаете в ${b} % случаев.`,
    value: "упущено",
    base: "у других мотивов",
  },
  phase: {
    title: (phaseIn: string) => `Ошибки ${phaseIn}`,
    text: (phaseIn: string, base: string, v: string, b: string) =>
      `Ошибка или зевок — в ${v} % ваших ходов ${phaseIn}, ${base} — в ${b} %. Считаются ходы в неясных позициях: в решённой ошибиться почти нельзя.`,
    value: "ходов с ошибкой",
    base: (base: string) => base,
  },
  time: {
    trouble: {
      title: "Ошибки в цейтноте",
      text: (v: string, b: string, count: number, total: number) =>
        `Когда на часах меньше 10 % времени, ошибка или зевок — в ${v} % ходов (${count} из ${total}), при нормальном запасе времени — в ${b} %.`,
      value: "в цейтноте",
      base: "при запасе",
    },
    hasty: {
      title: "Поспешные ходы",
      text: (v: string, b: string, count: number, total: number) =>
        `Быстрые ходы (не больше 2 % времени партии) вне цейтнота ошибочны в ${v} % случаев (${count} из ${total}), обдуманные — в ${b} %. Перед ходом проверьте, что угрожает соперник.`,
      value: "быстрые ходы",
      base: "обдуманные",
    },
  },
  opening: {
    title: (family: string, color: "white" | "black") => `${family} ${color === "white" ? "белыми" : "чёрными"}`,
    text: (count: number, v: string, b: string, color: "white" | "black") =>
      `${games(count)}: вы набираете ${v} % очков, в остальных дебютах ${color === "white" ? "белыми" : "чёрными"} — ${b} %.`,
    value: "очков",
    base: "в других дебютах",
  },
  conversion: {
    title: "Реализация выигранных позиций",
    text: (count: number, total: number, v: string, b: string) =>
      `В ${total} ${ruPlural(total, "партии", "партиях", "партиях")} после вашего хода позиция была выигранной (оценка от 80 %), но ${count} из них не закончились победой. Потеряно ${v} % очков — по оценке позиций ожидалось около ${b} %.`,
    value: "очков потеряно",
    base: "ожидалось",
  },
  examples: "Примеры из партий",
  best: (san: string) => `лучше ${san}`,
  open: (move: string, opponent: string) => `Открыть разбор: ${move} в партии с ${opponent}`,
  train: {
    puzzles: (n: number) => `Решать пазлы · ${n}`,
    rush: (n: number) => `Пазлы на время · ${n}`,
    endgames: (n: number) => `Тренажёр эндшпиля · ${n}`,
    course: "Учить дебют",
    play: "Сыграть с ботом",
    opening: "Открываем курс…",
    noPuzzles: "Пазлов на эту тему пока нет — они появятся из следующих разборов.",
    noEndgames: "Позиций для тренажёра пока нет — они появятся из следующих разборов.",
    courseFailed: "Не удалось открыть курс",
  },
  link: {
    title: "Слабые места",
    text: "Что чаще всего стоит вам очков — и как это тренировать",
  },
  card: {
    label: "Слабые места",
    title: "Ваши слабые места",
    top: (n: number) => `${n} ${ruPlural(n, "вывод", "вывода", "выводов")} по разобранным партиям`,
    few: (left: number) => `Разберите ещё ${games(left)}, чтобы увидеть, что стоит вам очков.`,
    none: "Явных слабых мест не нашлось — так держать.",
    open: "Смотреть",
  },
};
