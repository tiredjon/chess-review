import { ruPlural } from "../plural";

// Сессия 13.7: тренажёр дебютов — очередь повторения по курсам, ход за свою сторону.
const positions = (n: number) => `${n} ${ruPlural(n, "позиция", "позиции", "позиций")}`;

const waitText = (seconds: number) => {
  if (seconds < 60) return `${seconds} с`;
  if (seconds < 3600) return `${Math.ceil(seconds / 60)} мин`;
  return `${Math.ceil(seconds / 3600)} ч`;
};

export const trainer = {
  title: "Тренажёр дебютов",
  heading: "Играйте свою линию",
  allCourses: "Все курсы",
  filter: "Курс",
  counts: (due: number, fresh: number, learned: number, total: number) =>
    `К повторению ${due} · новых ${fresh} · выучено ${learned} из ${total}`,
  loading: "Загружаем позицию…",
  loadError: "Не удалось загрузить позицию",
  checkError: "Не удалось проверить ход",
  retry: "Повторить",
  banner: { white: "Ход белых", black: "Ход чёрных", main: "Ход курса!", alternative: "Тоже хороший ход", wrong: "Не тот ход" },
  status: {
    intro: "Соперник делает ход…",
    task: "Найдите ход вашей линии.",
    repeat: " Эту позицию вы уже видели.",
    fresh: " Новая позиция курса.",
    checking: "Проверяем ход…",
    main: "Верно — это ход курса.",
    withHint: "С подсказкой позиция вернётся раньше.",
    alternative: (loss: string) => `Движок считает его не хуже хода курса${loss}. Засчитано, но коробка не растёт.`,
    lossSuffix: (loss: number) => ` (потеря ${loss.toFixed(1)}% шансов)`,
    courseMove: "Ход курса:",
    wrong: (loss: string) => `Этот ход заметно хуже${loss}.`,
    wrongLoss: (loss: number) => ` — минус ${loss.toFixed(1)}% шансов`,
    showAgain: (when: string) => `Повторим ${when}.`,
    returns: (when: string) => `Позиция вернётся ${when}.`,
  },
  box: (box: number, max: number) => `Коробка ${box} из ${max}`,
  boxLabel: "Повторение",
  learned: "Выучено",
  hint: "Подсказка",
  hintShown: "Подсказка: фигура подсвечена",
  next: "Следующая позиция",
  nextLoading: "Загружаем…",
  openCourse: "Открыть в курсе",
  replay: "Показать ход курса",
  ideasTitle: "Вспомните идеи позиции",
  session: (right: number, wrong: number) => `За сессию: верно ${right}, ошибок ${wrong}`,
  empty: {
    title: "Тренировать пока нечего",
    text: "Создайте курс по дебюту — и тренируйте свою сторону: позиции, где ошибаетесь, возвращаются чаще.",
    link: "К каталогу курсов",
  },
  done: {
    title: "На сегодня всё!",
    text: (learned: number, total: number) =>
      `Новые позиции пройдены, повторения появятся позже. Выучено ${positions(learned)} из ${total}.`,
    course: "К курсу",
    all: "Все курсы",
  },
  notReady: "Курс ещё собирается — тренировка откроется, когда он будет готов.",
  errors: {
    rateLimited: (seconds: number) => `Слишком много ответов подряд. Передохните ${waitText(seconds)}.`,
    courseLimited: (seconds: number) => `Слишком много новых курсов. Попробуйте через ${waitText(seconds)}.`,
    engine: "Движок не смог проверить ход — попробуйте ещё раз.",
  },
  sound: { on: "Включить звук", off: "Выключить звук" },
};
