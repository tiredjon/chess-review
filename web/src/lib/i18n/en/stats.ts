import type { Dict } from "..";
import { enPlural } from "../plural";

export const stats: Dict["stats"] = {
  title: "Stats",
  loadError: "Couldn't load stats",
  filters: {
    source: "Source",
    allSources: "All sites",
    timeControl: "Time control",
    anyTimeControl: "Any time control",
  },
  // Как на Chess.com.
  timeClasses: {
    bullet: "Bullet",
    blitz: "Blitz",
    rapid: "Rapid",
    daily: "Daily",
  },
  kinds: {
    official: "from Chess.com",
    cc: "our estimate, close to Chess.com",
    lichess: "Lichess formula",
  },
  empty: {
    filteredTitle: "No games match this filter",
    filteredText: "Pick a different source or time control.",
    noneTitle: "No stats yet",
    importLink: "Import games",
    importText: "from Lichess or Chess.com — stats are based on your games.",
    noAnalysisTitle: "No reviewed games",
    noAnalysisText: "Phases, move classes and common mistakes are based on reviewed games.",
    noAnalysisLink: "Open a game",
    noAnalysisAfter: "and run the analysis.",
  },
  withoutColor: (n) =>
    `${n} ${enPlural(n, "game", "games")} without your color ${enPlural(n, "isn't", "aren't")} counted: enter your Lichess or Chess.com username when importing so pasted PGNs can be matched.`,
  totals: {
    games: "Games",
    analyzed: (n) => `${n} reviewed`,
    accuracy: "Avg. accuracy",
    accuracyOver: (n) => `over ${n} ${enPlural(n, "game", "games")}`,
    wins: "Wins",
    winsOf: (wins, decided) => `${wins} of ${decided}`,
    results: "Wins / Draws / Losses",
  },
  results: {
    wins: (n) => `${n} ${enPlural(n, "win", "wins")}`,
    draws: (n) => `${n} ${enPlural(n, "draw", "draws")}`,
    losses: (n) => `${n} ${enPlural(n, "loss", "losses")}`,
  },
  accuracy: {
    title: "Accuracy by game",
    fewTitle: "Not enough data for a chart",
    fewText: "Accuracy appears once a game is reviewed (or comes from Chess.com if the game was reviewed there).",
    legendGame: "Game accuracy",
    legendAverage: (window) => `${window}-game average`,
    average: (value) => `avg ${value}`,
    table: "As a table (last 30)",
    date: "Date",
    opponent: "Opponent",
    accuracy: "Accuracy",
    averageColumn: "Average",
  },
  versus: (name) => `vs ${name}`,
  phases: {
    title: "Accuracy by phase",
    note: "Phase accuracy uses the Lichess formula, as in the game review. It isn't directly comparable to the overall Chess.com-style accuracy: compare phases with each other.",
  },
  classes: {
    title: "Move classes",
    aside: "per game · share of moves",
    note: (moves, games) =>
      `${moves} of your moves in ${games} reviewed ${enPlural(games, "game", "games")}. "Misses" are a flag on top of the class: your opponent slipped and you didn't punish it.`,
  },
  openings: {
    title: "Openings",
    asWhite: "As White",
    asBlack: "As Black",
    noGames: "No games.",
    opening: "Opening",
    games: "Games",
    results: "Results",
    accuracy: "Acc.",
    winRate: (percent) => `${percent}% wins`,
  },
  motifs: {
    title: "Common mistake motifs",
    none: "No tactical motifs found in your mistakes — a great sign.",
    note: "A motif counts if it appeared in the refutation of your mistake or in the best line you missed; once per move.",
  },
};
