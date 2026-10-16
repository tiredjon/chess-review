// Тексты ошибок API по коду (backend/app/core/errors.py). Параметры — из `params` ответа,
// для ошибок импорта ещё `username` и `source` задачи.

export type ErrorParams = Record<string, string | number | undefined>;

const rateLimited: Record<string, (wait: string) => string> = {
  import: (wait) => `Слишком много импортов. Попробуйте через ${wait}.`,
  analyze: (wait) => `Слишком много запусков анализа. Попробуйте через ${wait}.`,
  llm: (wait) => `Слишком много запросов объяснений. Попробуйте через ${wait}.`,
  login: (wait) => `Слишком много попыток входа. Попробуйте через ${wait}.`,
  register: (wait) => `Слишком много регистраций с этого адреса. Попробуйте через ${wait}.`,
  browser: (wait) => `Слишком много анализов из браузера. Попробуйте через ${wait}.`,
  explore: (wait) => `Слишком много запросов к движку сервера. Переключитесь на браузер или подождите ${wait}.`,
};

const wait = (seconds: number) => {
  if (seconds < 60) return `${seconds} с`;
  if (seconds < 3600) return `${Math.ceil(seconds / 60)} мин`;
  return `${Math.ceil(seconds / 3600)} ч`;
};

export const errors = {
  codes: {
    not_authenticated: () => "Нужно войти в аккаунт",
    token_expired: () => "Сессия истекла, войдите снова",
    token_invalid: () => "Сессия недействительна, войдите снова",
    refresh_invalid: () => "Сессия истекла, войдите снова",
    refresh_rotated: () => "Сессия обновляется, повторите попытку",
    origin_forbidden: () => "Запрос с чужого сайта отклонён",
    email_taken: () => "Этот email уже зарегистрирован",
    invalid_credentials: () => "Неверный email или пароль",
    rate_limited: (p: ErrorParams) =>
      (rateLimited[String(p.scope)] ?? ((w: string) => `Слишком много запросов. Попробуйте через ${w}.`))(
        wait(Number(p.retry_after ?? 60)),
      ),
    game_not_found: () => "Партия не найдена",
    analysis_not_found: () => "Анализ не найден",
    analysis_not_ready: () => "Анализ ещё не готов",
    move_not_found: () => "Ход не найден",
    import_not_found: () => "Импорт не найден",
    puzzle_not_found: () => "Пазл не найден",
    puzzle_attempt_invalid: () => "Ход не совпадает с пазлом — обновите страницу",
    invalid_cursor: () => "Список устарел — обновите страницу",
    pgn_invalid: (p: ErrorParams) => `Партия ${p.game}: не удалось разобрать PGN (${p.reason})`,
    pgn_too_many: (p: ErrorParams) => `Слишком много партий за раз: не больше ${p.max}`,
    pgn_empty: () => "В тексте нет партий",
    pgn_variant: (p: ErrorParams) => `Партия ${p.game}: поддерживаются только классические шахматы`,
    pgn_no_moves: (p: ErrorParams) => `Партия ${p.game}: в партии нет ходов`,
    queue_unavailable: () => "Очередь задач недоступна, попробуйте позже",
    enqueue_failed: () => "Не удалось поставить задачу в очередь",
    interrupted: () => "Задача прервана — запустите заново",
    internal: () => "Внутренняя ошибка сервера",
    source_user_not_found: (p: ErrorParams) => `Пользователь ${p.username} не найден на ${p.source}`,
    source_rate_limited: (p: ErrorParams) => `${p.source} ограничил число запросов, попробуйте позже`,
    source_unavailable: (p: ErrorParams) => `${p.source} недоступен, попробуйте позже`,
    source_bad_response: (p: ErrorParams) => `${p.source} вернул некорректный ответ`,
    // Клиентский код: ошибка валидации поля email.
    invalid_email: () => "Некорректный email",
    share_not_found: () => "Ссылка недействительна",
    source_no_games: (p: ErrorParams) => `У ${p.username ?? "игрока"} нет партий в классические шахматы`,
    engine_data_invalid: () => "Браузерный движок прислал некорректные оценки — попробуйте ещё раз",
    depth_too_low: (p: ErrorParams) => `Глубина анализа должна быть не меньше ${p.min}`,
    invalid_fen: () => "Некорректная позиция",
    engine_unavailable: () => "Движок на сервере недоступен — переключитесь на браузер",
    validation_error: (p: ErrorParams) => (p.field ? `Проверьте поле «${p.field}»` : "Проверьте введённые данные"),
    http_error: (p: ErrorParams) => `Ошибка запроса (${p.status})`,
  } as Record<string, (p: ErrorParams) => string>,
  network: (url: string) => `Нет связи с API (${url}). Проверьте, что backend запущен.`,
  server: "Сервер не ответил. Попробуйте ещё раз через минуту.",
  request: (status: number) => `Ошибка запроса (${status})`,
  generic: "Не удалось выполнить запрос",
};
