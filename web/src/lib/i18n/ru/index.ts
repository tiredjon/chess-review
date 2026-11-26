// Русский словарь — источник типа `Dict`: английский обязан повторять его ключи и сигнатуры.
import { auth } from "./auth";
import { common } from "./common";
import { errors } from "./errors";
import { home } from "./home";
import { openings } from "./openings";
import { puzzles } from "./puzzles";
import { repertoire } from "./repertoire";
import { courses } from "./courses";
import { review } from "./review";
import { stats } from "./stats";
import { trainer } from "./trainer";
import { play } from "./play";
import { insights } from "./insights";
import { endgames } from "./endgames";

export const ru = { common, errors, auth, home, review, puzzles, stats, openings, repertoire, courses, trainer, play, insights, endgames };
