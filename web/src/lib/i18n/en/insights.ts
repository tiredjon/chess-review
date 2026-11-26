import type { Dict } from "..";
import { enPlural } from "../plural";

const games = (n: number) => `${n} ${enPlural(n, "game", "games")}`;
const side = (color: "white" | "black") => (color === "white" ? "White" : "Black");

export const insights: Dict["insights"] = {
  title: "Weak spots",
  subtitle: "What costs you the most points: findings from your analyzed games, with examples and training.",
  loadError: "Couldn't load your weak spots",
  basis: (n) => `Based on ${games(n)} analyzed`,
  severity: { high: "Important", medium: "Notable", low: "Worth a look" },
  kinds: { motif: "Missed tactic", phase: "Game phase", time: "Time", opening: "Opening", conversion: "Conversion" },
  empty: {
    fewTitle: "Not enough analyzed games yet",
    fewText: (analyzed, min) =>
      `Weak spots need at least ${games(min)} analyzed — you have ${analyzed}. Open your games and run the analysis: findings will show up here.`,
    gamesLink: "Go to games",
    noneTitle: "No clear weak spots",
    noneText: "Nothing stands out enough to rule out chance. Check back after you analyze more games.",
    filteredText: "This filter leaves less data: try all sites and any time control.",
  },
  phaseIn: { opening: "in the opening", middlegame: "in the middlegame", endgame: "in the endgame" },
  phaseBase: { opening: "in the rest of the game", middlegame: "in the endgame", endgame: "in the middlegame" },
  motif: {
    title: (motif) => motif,
    text: (v, b, count, total) =>
      `A move with this motif was best ${total} ${enPlural(total, "time", "times")} — you missed it ${count} (${v}%). You miss other motifs ${b}% of the time.`,
    value: "missed",
    base: "other motifs",
  },
  phase: {
    title: (phaseIn) => `Mistakes ${phaseIn}`,
    text: (phaseIn, base, v, b) =>
      `${v}% of your moves ${phaseIn} are mistakes or blunders, ${b}% ${base}. Only unclear positions count: in a decided one you can hardly go wrong.`,
    value: "moves with errors",
    base: (base) => base,
  },
  time: {
    trouble: {
      title: "Mistakes in time trouble",
      text: (v, b, count, total) =>
        `With under 10% of your time left, ${v}% of your moves are mistakes or blunders (${count} of ${total}), ${b}% with time to spare.`,
      value: "in time trouble",
      base: "with time",
    },
    hasty: {
      title: "Hasty moves",
      text: (v, b, count, total) =>
        `Quick moves (2% of the game's time or less) outside time trouble go wrong ${v}% of the time (${count} of ${total}), considered ones ${b}%. Before moving, check what your opponent threatens.`,
      value: "quick moves",
      base: "considered",
    },
  },
  opening: {
    title: (family, color) => `${family} as ${side(color)}`,
    text: (count, v, b, color) => `${games(count)}: you score ${v}%, ${b}% in your other openings as ${side(color)}.`,
    value: "score",
    base: "other openings",
  },
  conversion: {
    title: "Converting won positions",
    text: (count, total, v, b) =>
      `In ${games(total)} your move left you winning (80%+ by evaluation), yet ${count} of them didn't end in a win. You dropped ${v}% of the points — about ${b}% was expected from the positions.`,
    value: "points dropped",
    base: "expected",
  },
  examples: "Examples from your games",
  best: (san) => `best ${san}`,
  open: (move, opponent) => `Open review: ${move} vs ${opponent}`,
  train: {
    puzzles: (n) => `Solve puzzles · ${n}`,
    rush: (n) => `Puzzle rush · ${n}`,
    endgames: (n) => `Endgame trainer · ${n}`,
    course: "Study this opening",
    play: "Play a bot",
    opening: "Opening the course…",
    noPuzzles: "No puzzles on this yet — they'll come from your next analyses.",
    noEndgames: "No trainer positions yet — they'll come from your next analyses.",
    courseFailed: "Couldn't open the course",
  },
  link: {
    title: "Weak spots",
    text: "What costs you the most points — and how to train it",
  },
  card: {
    label: "Weak spots",
    title: "Your weak spots",
    top: (n) => `${n} ${enPlural(n, "finding", "findings")} from your analyzed games`,
    few: (left) => `Analyze ${games(left)} more to see what costs you points.`,
    none: "No clear weak spots — keep it up.",
    open: "View",
  },
};
