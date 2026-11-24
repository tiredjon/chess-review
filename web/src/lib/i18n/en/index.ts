import type { Dict } from "..";
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

export const en: Dict = { common, errors, auth, home, review, puzzles, stats, openings, repertoire, courses, trainer };
