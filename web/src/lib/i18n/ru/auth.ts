// Вход, регистрация, профиль.
export const auth = {
  login: {
    title: "Вход",
    heading: "Войти в Chess Review",
    submit: "Войти",
    noAccount: "Нет аккаунта?",
    toRegister: "Зарегистрироваться",
  },
  register: {
    title: "Регистрация",
    heading: "Создать аккаунт",
    submit: "Зарегистрироваться",
    haveAccount: "Уже есть аккаунт?",
    toLogin: "Войти",
    passwordHint: "Не короче 8 символов",
  },
  fields: {
    email: "Email",
    password: "Пароль",
    showPassword: "Показать пароль",
    hidePassword: "Скрыть пароль",
  },
  tagline: "Разбор партий на Stockfish: точность, классы ходов и объяснения ошибок.",
  passwordTooShort: "Пароль должен быть не короче 8 символов",
  checking: "Проверяем вход…",
  profile: {
    title: "Профиль",
    account: "Аккаунт",
    since: (date: string) => `С нами с ${date}`,
    language: "Язык интерфейса и объяснений",
    languageHint: "Объяснения ходов и итог партии тоже пишутся на этом языке.",
    usernames: "Ники на площадках",
    usernamesHint:
      "По ним определяется ваш цвет во вставленных PGN. Заполняются сами при первом импорте.",
    lichess: "Ник на Lichess",
    chesscom: "Ник на Chess.com",
    usernameInvalid: "Латиница, цифры, «_» и «-», от 2 до 50 символов",
    logout: "Выйти из аккаунта",
  },
};
