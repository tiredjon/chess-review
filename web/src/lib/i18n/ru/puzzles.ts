import { ruPlural } from "../plural";

// Тренажёр пазлов из своих ошибок. `when` — относительное время («через 3 дня»).
export const puzzles = {
  title: "Пазлы из ваших ошибок",
  section: "Пазл",
  heading: "Пазлы",
  headingSuffix: " из ваших ошибок",
  counts: (due: number, fresh: number, total: number) => `повторить ${due} · новых ${fresh} · всего ${total}`,
  soundOn: "Включить звук (M)",
  soundOff: "Выключить звук (M)",
  loadError: "Не удалось загрузить пазл",
  checkError: "Не удалось проверить ход",
  solution: "Решение",
  loading: "Загружаю…",
  next: "Следующий пазл",
  replay: "Показать решение с начала",
  hint: "Подсказка",
  giveUp: "Решение",
  banner: {
    solved: "Решено",
    failed: "Не решено",
    white: "Ход белых",
    black: "Ход чёрных",
  },
  status: {
    intro: "Соперник делает ход…",
    correct: "Верно!",
    withHint: "С подсказкой — интервал не растёт.",
    wellDone: "Отличная работа.",
    showAgain: (when: string) => `Снова покажем ${when}.`,
    incorrect: "Не то.",
    // «Верный ход — <b>Kf3</b> (зелёная стрелка).»
    correctMove: "Верный ход —",
    correctMoveAfter: "(зелёная стрелка).",
    returns: (when: string) => `Пазл вернётся ${when}.`,
    checking: "Проверяю ход…",
    keepGoing: (move: number, total: number) => `Верно, продолжайте! Ход ${move} из ${total}.`,
    task: (total: number) =>
      `В партии здесь была ошибка. Найдите лучший ход${total > 1 ? ` — решение в ${total} ${ruPlural(total, "ход", "хода", "ходов")}` : ""}.`,
    repeat: " Это повторение.",
  },
  // «Из партии против <b>ник</b>, дата: в партии было <b>23. Kf3</b> (зевок)».
  source: {
    fromGame: "Из партии против",
    played: "в партии было",
  },
  streak: "Решено подряд",
  streakLabel: (n: number) => `Решено подряд: ${n}`,
  empty: {
    title: "Пазлов пока нет",
    text: "Пазлы появляются из ваших ошибок в разобранных партиях (нужен ваш цвет в партии).",
    link: "Разберите партии",
  },
  done: {
    title: "На сейчас всё решено",
    text: (when: string, streak: number) => `Следующее повторение — ${when}. Решено подряд: ${streak}.`,
  },
};
