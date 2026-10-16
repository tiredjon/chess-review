import type { Dict } from "..";
import { auth } from "./auth";
import { common } from "./common";
import { errors } from "./errors";
import { home } from "./home";
import { puzzles } from "./puzzles";
import { review } from "./review";
import { stats } from "./stats";

export const en: Dict = { common, errors, auth, home, review, puzzles, stats };
