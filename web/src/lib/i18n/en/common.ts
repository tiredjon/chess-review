import type { Dict } from "..";
import { enPlural } from "../plural";

export const common: Dict["common"] = {
  appName: "Chess Review",
  description: "Chess game review on Stockfish with explained mistakes",
  nav: {
    label: "Navigation",
    toHome: "Chess Review — home",
    home: "Home",
    games: "Games",
    stats: "Stats",
    puzzles: "Puzzles",
    profile: "Profile",
    logout: "Log out",
  },
  titles: {
    home: "Game Review",
    games: "Games",
    review: "Game Review",
    stats: "Stats",
    puzzles: "Puzzles",
    profile: "Profile",
    login: "Log in",
    shared: "Game review",
    register: "Sign up",
  },
  actions: {
    retry: "Retry",
    save: "Save",
    saved: "Saved",
    cancel: "Cancel",
    close: "Close",
    loading: "Loading…",
    more: "Show more",
  },
  language: {
    label: "Language",
    ru: "Русский",
    en: "English",
  },
  // Как в Game Review Chess.com.
  classes: {
    brilliant: { label: "Brilliant", plural: "Brilliant" },
    great: { label: "Great", plural: "Great" },
    best: { label: "Best", plural: "Best" },
    excellent: { label: "Excellent", plural: "Excellent" },
    good: { label: "Good", plural: "Good" },
    book: { label: "Book", plural: "Book" },
    forced: { label: "Forced", plural: "Forced" },
    inaccuracy: { label: "Inaccuracy", plural: "Inaccuracies" },
    mistake: { label: "Mistake", plural: "Mistakes" },
    miss: { label: "Miss", plural: "Misses" },
    blunder: { label: "Blunder", plural: "Blunders" },
  },
  phases: {
    opening: "Opening",
    middlegame: "Middlegame",
    endgame: "Endgame",
  },
  motifs: {
    hanging_piece: "Hanging piece",
    fork: "Fork",
    pin: "Pin",
    skewer: "Skewer",
    discovered_attack: "Discovered attack",
    discovered_check: "Discovered check",
    double_check: "Double check",
    mate_in_n: "Mate",
    mate_threat: "Mate threat",
    back_rank: "Back-rank mate",
    trapped_piece: "Trapped piece",
    removing_defender: "Removing the defender",
    overload: "Overloading",
    promotion: "Promotion",
    promotion_threat: "Promotion threat",
    only_move: "Only move",
  },
  outcome: { win: "Win", loss: "Loss", draw: "Draw" },
  colors: { white: "white", black: "black", White: "White", Black: "Black" },
  time: {
    seconds: (n) => `${n} sec`,
    minutes: (n) => `${n} min`,
    days: (n) => `${n} d`,
  },
  wait: (seconds) => {
    if (seconds < 60) return `${seconds} s`;
    if (seconds < 3600) return `${Math.ceil(seconds / 60)} min`;
    return `${Math.ceil(seconds / 3600)} h`;
  },
  games: (n) => `${n} ${enPlural(n, "game", "games")}`,
};
