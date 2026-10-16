import type { Dict } from "..";

export const auth: Dict["auth"] = {
  login: {
    title: "Log in",
    heading: "Log in to Chess Review",
    submit: "Log in",
    noAccount: "No account yet?",
    toRegister: "Sign up",
  },
  register: {
    title: "Sign up",
    heading: "Create an account",
    submit: "Sign up",
    haveAccount: "Already have an account?",
    toLogin: "Log in",
    passwordHint: "At least 8 characters",
  },
  fields: {
    email: "Email",
    password: "Password",
    showPassword: "Show password",
    hidePassword: "Hide password",
  },
  tagline: "Game review on Stockfish: accuracy, move classes and explained mistakes.",
  passwordTooShort: "The password must be at least 8 characters",
  checking: "Checking your session…",
  profile: {
    title: "Profile",
    account: "Account",
    since: (date) => `Member since ${date}`,
    language: "Interface and explanations language",
    languageHint: "Move explanations and the game summary are written in this language too.",
    usernames: "Usernames",
    usernamesHint:
      "Used to detect your color in pasted PGN. Filled in automatically on the first import.",
    lichess: "Lichess username",
    chesscom: "Chess.com username",
    usernameInvalid: "Latin letters, digits, “_” and “-”, 2 to 50 characters",
    logout: "Log out",
  },
};
