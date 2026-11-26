import type { Dict } from "..";

export const endgames: Dict["endgames"] = {
  title: "Endgame trainer",
  subtitle: "Play the position out against an opponent that defends perfectly with Syzygy tablebases.",
  playLink: {
    title: "Endgame trainer",
    text: "Lucena, Philidor, opposition, basic mates — and positions from your games",
  },
  tabs: { catalog: "Essentials", mine: "From my games" },
  categories: {
    pawn: "Pawn endgames",
    rook: "Rook endgames",
    queen: "Queen vs pawn",
    mate: "Basic checkmates",
  },
  categoryProgress: (done, total) => `${done} of ${total}`,
  difficulty: { 1: "Basics", 2: "Technique", 3: "Hard" },
  goal: { win: "Win", draw: "Draw" },
  goalLong: {
    win: "Goal: deliver checkmate",
    draw: (moves) => `Goal: a rules draw, or hold the draw for ${moves} moves`,
  },
  side: { white: "You play White", black: "You play Black" },
  progress: (attempts, successes) => (attempts === 0 ? "Not tried yet" : `Attempts: ${attempts} · successful: ${successes}`),
  solved: "Solved",
  start: "Play",
  loading: "Loading…",
  loadError: "Couldn't load positions",
  retry: "Retry",
  positions: {
    pawn_opposition_win: {
      name: "Opposition: king in front of the pawn",
      hint: "Put your king in front of the pawn with one square between the kings — then push.",
    },
    pawn_opposition_draw: {
      name: "Opposition: defence",
      hint: "Only one move: take the opposition so the white king can't reach the key squares.",
    },
    pawn_key_squares: {
      name: "Key squares",
      hint: "A king on a key square in front of the pawn wins whoever is to move.",
    },
    pawn_square: {
      name: "The rule of the square",
      hint: "Step into the pawn's square — then your king catches it.",
    },
    pawn_outside_passer: {
      name: "Outside passed pawn",
      hint: "The edge passer drags the enemy king away while your king eats the pawns.",
    },
    pawn_outside_passer_2: {
      name: "Outside passer: two against one",
      hint: "Use the far pawn as a decoy and win on the other wing.",
    },
    rook_lucena: {
      name: "Lucena position",
      hint: "Cut the king off with a check, then build the bridge: a rook on the 4th rank shields your king.",
    },
    rook_lucena_2: {
      name: "Lucena: king on the edge",
      hint: "First push the enemy king away with a check, then bring your king out and build the bridge.",
    },
    rook_philidor: {
      name: "Philidor position",
      hint: "The rook on the 6th rank keeps the king out until the pawn advances.",
    },
    rook_philidor_checks: {
      name: "Philidor: checks from behind",
      hint: "The pawn reached the 6th — the king lost its shelter: check from the first rank.",
    },
    rook_vancura: {
      name: "Vančura position",
      hint: "The rook on the side attacks the a6 pawn and gives checks; the king stays on g7.",
    },
    rook_vs_pawn_win: {
      name: "Rook vs pawn",
      hint: "March the king to the pawn while the rook controls the queening square.",
    },
    rook_vs_pawn_draw: {
      name: "Rook vs pawn: defence",
      hint: "Your king is next to the pawn — push it as far as you can, the rook will have to give itself up.",
    },
    queen_vs_pawn: {
      name: "Queen vs central pawn",
      hint: "Check until the king has to stand in front of the pawn, and use the tempo to bring your king.",
    },
    queen_vs_rook_pawn: {
      name: "Queen vs rook pawn",
      hint: "Usually a stalemate draw, but your king is close: bring it in — mate comes first.",
    },
    queen_vs_bishop_pawn: {
      name: "Queen vs bishop pawn: defence",
      hint: "Run to the corner: taking the pawn there is stalemate.",
    },
    mate_queen: {
      name: "Queen checkmate",
      hint: "Keep the queen a knight's move from the king to shrink the box, then bring your king. Watch out for stalemate!",
    },
    mate_two_rooks: {
      name: "Two-rook checkmate",
      hint: "The rooks take turns pushing the king to the edge — the 'ladder'.",
    },
    mate_rook: {
      name: "Rook checkmate",
      hint: "The rook cuts the king off, your king takes the opposition — check on the edge.",
    },
    mate_two_bishops: {
      name: "Two-bishop checkmate",
      hint: "Side-by-side bishops make a diagonal wall; the king helps drive into the corner.",
    },
    mate_bishop_knight: {
      name: "Bishop and knight checkmate",
      hint: "The hardest one: mate only in a corner of the bishop's colour — drive the king there with the knight's 'W'.",
    },
  },
  mine: {
    empty: "No suitable positions yet.",
    emptyHint: "Your endgame mistakes and misses from analysed games end up here — when the position was won or drawn.",
    title: (opponent) => `vs ${opponent}`,
    played: (san) => `Played: ${san}`,
    best: (san) => `best ${san}`,
    pieces: (n) => `${n} pcs`,
    win: (value) => `${Math.round(value)}% before the mistake`,
  },
  game: {
    back: "Back to list",
    opponentTb: "The opponent defends with Syzygy tablebases — the most stubborn move.",
    opponentBot: "More than 7 pieces — the opponent is Stockfish 2800; tablebases kick in at ≤ 7 pieces.",
    hint: "Hint",
    hideHint: "Hide hint",
    tb: {
      title: "Tablebase after your move",
      start: "Tablebase in the starting position",
      win: "Win",
      draw: "Draw",
      loss: "Loss",
      none: "More than 7 pieces — no tablebase",
      pending: "Asking the tablebase…",
      error: "Tablebase unavailable",
    },
    held: (n, total) => `Draw held: ${n} of ${total} moves`,
    goalAdjusted: {
      win: "The tablebase says this is a win — goal: win.",
      draw: "The tablebase says this is only a draw — goal: draw.",
    },
    nothingToTrain: "The tablebase says this position is already lost — nothing to train here.",
    success: {
      mate: "Checkmate! Goal reached",
      draw_rules: "Draw! Goal reached",
      held: "Draw held! Goal reached",
    },
    failure: {
      lost_win: "The win slipped away",
      lost_draw: "The draw slipped away",
      draw_rules: "Draw — the win wasn't converted",
      mated: "You got checkmated",
      resigned: "You resigned",
    },
    missed: (move, kind) => `${move} — the tablebase ${kind === "win" ? "win" : "draw"} was lost here.`,
    better: (moves) => `Kept the result: ${moves}.`,
    showMoment: "Show the moment",
    again: "Try again",
    next: "Next position",
    saveError: "The attempt wasn't saved",
    fromGame: "Position from your game",
    openReview: "Open review",
  },
};
