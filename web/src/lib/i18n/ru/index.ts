// Русский словарь — источник типа `Dict`: английский обязан повторять его ключи и сигнатуры.
import { auth } from "./auth";
import { common } from "./common";
import { errors } from "./errors";
import { home } from "./home";
import { puzzles } from "./puzzles";
import { review } from "./review";
import { stats } from "./stats";

export const ru = { common, errors, auth, home, review, puzzles, stats };
