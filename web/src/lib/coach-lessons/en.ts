// Coach lessons in English (session 17.1). For a 1500–2000 player: the idea, how to spot it,
// common club-player mistakes, an exercise. No invented games or concrete variations.
import type { LessonSource, LessonText, LessonTexts } from "./index";

const lesson = (
  title: string,
  summary: string,
  idea: string,
  spot: string,
  mistakes: string,
  exercise: string,
): LessonText => ({
  title,
  summary,
  sections: [
    { heading: "The idea", body: idea },
    { heading: "How to spot it", body: spot },
    { heading: "Common mistakes", body: mistakes },
    { heading: "Exercise", body: exercise },
  ],
});

// Book articles: a condensed retelling of Ed. Lasker's "Chess Strategy" (1915) and Capablanca's
// "Chess Fundamentals" (1921), sections by topic. Positions come from the backend.
const LASKER = "Edward Lasker, Chess Strategy (1915)";
const CAPABLANCA = "J. R. Capablanca, Chess Fundamentals (1921)";
const book = (title: string, summary: string, sections: [string, string][], source: LessonSource): LessonText => ({
  title,
  summary,
  sections: sections.map(([heading, body]) => ({ heading, body })),
  source,
});

export const EN: LessonTexts = {
  hanging_piece: lesson(
    "Loose pieces",
    "An undefended piece is the first target of every tactic. Learn to see them on both sides of the board.",
    "A loose piece can simply be taken, and it is also the target of forks, pins and double attacks. John Nunn put it as “loose pieces drop off”. Picking up free material is the simplest way to win games at any level.",
    "After every opponent move, ask: what is undefended now? Count attackers and defenders on every piece that is under fire. Pieces on the rim and pieces that have run far ahead without support are especially vulnerable.",
    "Focusing on your own plan and missing that the opponent left a piece hanging. Forgetting that a defender may be pinned or overloaded, so the piece only looks protected. Playing an “active” move that leaves one of your own pieces undefended.",
    "In positions from your own games, name every loose piece for both sides before looking for the best move. Then solve 15–20 “hanging piece” puzzles slowly, counting defenders each time.",
  ),
  fork: lesson(
    "Fork",
    "One piece attacks two targets at once — the opponent can save only one.",
    "A fork works because you cannot answer two threats with one move. Knights are the classic forking piece because their attacks are hard to see, but any piece can fork, including pawns and the queen. The strongest forks come with check: the opponent must deal with the check first.",
    "Look for two valuable targets one move away from your piece: king and queen, rook and an undefended bishop. For a knight, check squares that hit two pieces at a knight’s distance. A fork is often prepared by a sacrifice or a trade that lures a piece onto the right square.",
    "Seeing the fork only once it is already on, and missing the move that prepares it. Leaving your king and queen a knight’s jump apart from the opponent’s knight. Not checking whether the forking square is defended.",
    "Solve 20 fork puzzles. Before each move, say out loud: which two targets, which piece forks, what can the opponent reply. In your own games, mark the positions where you missed a fork and find the preparing move.",
  ),
  pin: lesson(
    "Pin",
    "A piece cannot move without exposing a more valuable piece or the king behind it.",
    "A long-range piece (bishop, rook, queen) attacks a piece that shields a more valuable one. Against the king the pinned piece cannot move at all; against the queen it can, but at a cost. A pinned piece defends badly and cannot join an attack, so pile up on it — with a pawn or a second piece.",
    "Look for two enemy pieces on one line, file or diagonal, especially with the king or queen behind. Typical pins: a bishop on g5 (g4) against a knight on f6 (f3) with the queen behind it, a rook on an open file against a piece in front of the king.",
    "Pinning a piece and then not increasing the pressure on it. Not noticing your own piece is pinned and counting on it as a defender. Trading at once when the pin could have kept the opponent tied up for many moves.",
    "Solve 15–20 pin puzzles. For each, answer: what is pinned, to what, and how to add pressure. In the openings of your games, find moments where your piece got pinned and decide how you could have avoided it.",
  ),
  skewer: lesson(
    "Skewer",
    "Attack a valuable piece with another one behind it on the same line: the first moves away, the second is lost.",
    "A skewer is a “reverse pin”: the more valuable piece is in front. It has to move and uncovers the one behind. Most often it is a check to the king with a queen or rook behind — a standard weapon in rook and queen endgames.",
    "Look for the enemy king or queen on the same line as another of their pieces, especially on open files, ranks and long diagonals. In endgames, watch for the king and rook on one line.",
    "Putting your king and queen (or rook) on one line or diagonal for no reason. Missing that a trade has just opened the line. Confusing a skewer with a pin and attacking the wrong piece.",
    "Solve 15 skewer puzzles, naming the front piece and the piece behind each time. Then set up an enemy king and rook on one line and find every way to attack them with check.",
  ),
  discovered_attack: lesson(
    "Discovered attack",
    "One piece moves and opens a line for another — two threats in a single move.",
    "A piece standing in front of your bishop, rook or queen is a loaded gun. When it moves away with a threat of its own, the long-range piece behind it makes a second threat. The opponent answers one and loses material to the other.",
    "Look for your own piece blocking your long-range piece’s line to a valuable enemy target. Think about where it can go with its own threat: a capture, a check, an attack on a loose piece.",
    "Not noticing that the opponent has set up such a battery against your queen or king. Moving the blocking piece “anywhere” when it could have moved with a threat. Not checking for an in-between check by the opponent.",
    "Solve 15 discovered attack puzzles. Before moving, name both threats — the moving piece and the uncovered one. In your games, look at positions where your piece stood in front of a rook or bishop aimed at the enemy queen.",
  ),
  discovered_check: lesson(
    "Discovered check",
    "A piece moves away and uncovers check from another — and is free to do anything meanwhile.",
    "A discovered check is the strongest discovered attack: the opponent must answer the check, while the moving piece can take a queen or rook or make another threat. That is why a “piece in front of a rook or bishop aimed at the king” battery is dangerous even when nothing is happening yet.",
    "Look for a line between your long-range piece and the enemy king with one of your own pieces on it. Go through all of that piece’s moves and pick the one that wins the most or mates.",
    "Giving a discovered check “just because” without winning anything, and losing the battery. Missing that such a battery is aimed at your own king. Forgetting about double check, which is even stronger.",
    "Solve 10–15 discovered check puzzles. In each, first list every move of the moving piece and choose the one that wins the most. Then find positions in your games where your king stood on a line with an enemy battery.",
  ),
  double_check: lesson(
    "Double check",
    "Check from two pieces at once: you cannot block or capture — the king must move.",
    "Against a double check neither blocking nor capturing one of the checkers helps; only a king move does. That is why a double check often leads to mate even when both checking pieces are en prise. It is the main reason a battery aimed at the king is so dangerous.",
    "Look for a discovered check where the moving piece also gives check. It is especially strong when the king has few free squares: then a double check often ends in mate.",
    "Being afraid to put a piece en prise with a double check — it cannot be taken anyway. Seeing the opponent’s discovered check threat but missing that the moving piece also checks: then you cannot block or capture, and the king had to be made safe earlier.",
    "Solve 10 double check puzzles and, for each, check which squares the king has left. Then set up a king with few squares and a battery against it, and find the double check.",
  ),
  mate_in_n: lesson(
    "Mate in a few moves",
    "A forced mate: checks and captures that leave the opponent no choice.",
    "When the enemy king is exposed or boxed in by its own pieces, a forcing sequence — check, capture, threat — may end in mate. The key is to calculate forcing moves: they narrow the calculation to one or two lines.",
    "Look for a king with few free squares, your pieces close to it and open lines towards it. Check every check, even “impossible” ones with a sacrifice. Know the standard mating patterns: back-rank mate, smothered mate with a knight, a supported queen mate, two rooks or bishops “ladder” mates.",
    "Not considering sacrifices because “you can’t do that”. Calculating further than needed while not checking the opponent’s replies at each step. Winning material when there was a mate.",
    "Solve 20 mate-in-2 and mate-in-3 puzzles. Rule: checks first, then captures, then threats. Write down the full solution before making the first move.",
  ),
  mate_threat: lesson(
    "Mate threat",
    "A move that threatens mate forces the opponent to defend — and buys time for everything else.",
    "A mate threat is a powerful in-between move. The opponent has to parry it, and you gain a tempo: to grab material, bring up a piece, create a second threat. A move with two threats (mate and material) usually wins.",
    "Look for positions where you are one move short of mate and check whether that move can come with another threat. Watch your own side too: after every opponent move, ask whether they are threatening mate.",
    "Missing a mate threat against your king while busy with your own attack. Making a mate threat that is easily parried by a move that improves the opponent’s position. Forgetting that “the threat is stronger than the execution”: sometimes keeping the threat is better than rushing.",
    "Solve 15 puzzles where the best move is a quiet move threatening mate. In your games, count how often you lost to a missed mate threat — and what question you should have asked yourself before moving.",
  ),
  back_rank: lesson(
    "Back-rank weakness",
    "A king behind its pawns without “luft” is a target for a rook or queen mate.",
    "If the king sits on the edge behind unmoved pawns with no free square, a check along the back rank is mate. Even the threat overloads defenders: a rook or queen cannot leave the back rank, and that creates tactics.",
    "Look for the enemy king behind three pawns with no luft (a pushed pawn), and a single piece guarding the back rank. Check whether that piece can be deflected, traded or overloaded.",
    "Never making luft for your own king in positions with heavy pieces. Making it at the wrong moment and weakening the king. Grabbing material when the opponent then mates on the back rank.",
    "Solve 15 back-rank mate puzzles. In your games with heavy pieces, find the moment when you could have made luft calmly, and remember what that moment looked like.",
  ),
  trapped_piece: lesson(
    "Trapped piece",
    "A piece with nowhere to go dies even on an open board.",
    "A trapped piece is one whose retreat squares are all covered. The usual victims are a bishop that has gone behind a pawn, a knight on the rim and a queen that went pawn-grabbing. Sometimes a single pawn move cuts off the retreat.",
    "Before taking a “poisoned” pawn or raiding the enemy camp, count your retreat squares. On the opponent’s side, look for pieces on the rim or deep in your camp: how many free squares do they have, can you take them away in one move?",
    "Grabbing a pawn with the queen or bishop without checking the way back. Putting a knight on the rim with two squares. Missing that one pawn move by the opponent cuts off the retreat.",
    "Solve 10–15 trapped piece puzzles. Then, in a few positions from your games, count the retreat squares of each of your pieces — the habit saves pieces.",
  ),
  removing_defender: lesson(
    "Removing the defender",
    "Take away the piece that guards a key target — and the target falls.",
    "If an important square or piece is guarded by a single enemy piece, that defender can be traded, captured with a sacrifice or chased away. Then the defence collapses: material drops or a mate appears. It is one of the most common ideas in attacks on the king.",
    "Find the target (a piece, a square in front of the king, a mating square) and ask: who defends it? If there is only one defender, look for a way to remove it: a trade, a capture, a pawn attack.",
    "Attacking the target head-on without thinking about its defenders. Trading off the wrong piece — one that defended nothing important. Missing that the opponent is removing the defender of your king.",
    "Solve 15 removing-the-defender puzzles. In each, first name the target and its only defender, and only then look for the move.",
  ),
  overload: lesson(
    "Overload",
    "One piece guards two things — attack one, and the other is left undefended.",
    "An overloaded piece has two jobs: for example, guarding a piece and the back rank. As soon as you force it to do one, the other is left unprotected. Overload is often hidden: everything looks defended, but one piece is holding too much.",
    "For every enemy piece that defends something important, ask: what else does it defend? If it has two targets, look for a move that hits one of them (ideally with check or a capture).",
    "Thinking a piece is safely defended when its defender is busy with something else. Relying on one of your own pieces to cover several weaknesses. Starting the combination with the wrong target — move order often decides everything.",
    "Solve 10–15 overload puzzles, listing the duties of each defending piece. In your games, find positions where one of your pieces was holding two weaknesses.",
  ),
  promotion: lesson(
    "Promotion",
    "A pawn on the seventh rank is almost a queen — help it through.",
    "A passed pawn on the seventh (second) rank ties down enemy pieces, and a sacrifice that clears its path often wins. Tactical tools: deflecting the blockader, interfering with the defending line, promoting with a capture or check.",
    "Look for your pawns one or two moves from promotion and the enemy pieces that stop them. Check whether the only defender of the promotion square can be deflected or cut off. In endgames, count who is faster: the rule of the square for a pawn against a king.",
    "Promoting to a queen when it gives stalemate or when a knight gives a decisive check. Missing that the opponent wins the pawn just before it promotes. Pushing the pawn too early without support.",
    "Solve 10–15 promotion puzzles. Then set up king and pawn against king and test the rule of the square in different positions.",
  ),
  promotion_threat: lesson(
    "Promotion threat",
    "A pawn about to queen pulls enemy pieces away — use it.",
    "Even when promotion is not yet possible, the threat forces the opponent to keep a piece near the promotion square. While it is there, it is not defending anything else: that is how a passed pawn wins material or creates mate on the other wing.",
    "Assess which enemy pieces are tied to your passed pawn. Look for a second target on the other wing: if the pawn’s guard cannot cover both, overload wins.",
    "Underestimating the opponent’s passed pawn and trading off the pieces that held it. Pushing your passer without support and losing it. Forgetting that a passed pawn gets stronger the further it advances and the fewer pieces remain.",
    "Solve 10 promotion-threat puzzles. In your endgames, find moments where the opponent’s passed pawn forced you onto the defensive, and think about how it could have been stopped earlier.",
  ),
  opening_principles: lesson(
    "Opening principles",
    "Centre, development, king safety — and don’t waste tempi.",
    "In the opening the goal is to bring the pieces into play quickly, occupy or control the centre and get the king to safety (usually by castling). Every move should help with this. A position without needless weaknesses and with developed pieces is a good start to the middlegame, even if you don’t know the theory.",
    "Check after ten moves: how many pieces are developed, has the king castled, who controls the centre. If the opponent is developing while you chase pawns or move one piece many times, you are falling behind.",
    "Bringing the queen out early and losing tempi when it gets chased. Playing many pawn moves without developing pieces. Leaving the king in the centre when the centre opens. Grabbing “poisoned” pawns at the cost of development.",
    "Play 5 games against a bot with the goal: all minor pieces developed and the king castled by move 10. After each game, review the opening: which move broke a principle. Solve opening-phase puzzles.",
  ),
  middlegame_plans: lesson(
    "Middlegame planning",
    "Find a weakness, improve your worst piece, attack where you are stronger.",
    "Once the pieces are developed you need a plan. Simple guides: where are the opponent’s weaknesses (an isolated pawn, weak squares, a bad bishop), where do you have more space and more pieces, which of your pieces is the worst. A good move is often just improving the worst piece.",
    "Look at the pawn structure: it tells you where to play. Open files are for rooks, weak squares for knights, a pawn majority for an advance. If you see no tactics, ask: what is the opponent’s plan and how do I stop it?",
    "Making moves “without an idea” and waiting for the opponent to go wrong. Attacking where the opponent is stronger. Trading active pieces for passive ones. Forgetting your own safety while chasing an attack.",
    "Take 5 positions from your games after move 15. For each, write down: weaknesses on both sides, my worst piece, a plan for 3–5 moves. Then check with the engine. Solve middlegame-phase puzzles.",
  ),
  endgame_technique: lesson(
    "Endgame technique",
    "Active king, passed pawns, the right trades — and knowing the basic positions.",
    "In the endgame the king is a strong piece: bring it to the centre. Passed pawns decide, and an extra pawn wins more often if you trade pieces but not pawns. Know the basic positions by heart: the opposition in pawn endings, the Lucena and Philidor positions in rook endings.",
    "When few pieces remain, ask: where are the kings, who has or will have a passed pawn, which trades favour me. Put rooks behind passed pawns — yours and the opponent’s.",
    "Keeping the king on the edge out of habit. Trading rooks into a lost pawn ending. A passive rook that only guards a pawn. Rushing and not counting pawn races.",
    "Work through the endgame trainer with your own positions. Then learn the opposition, the Lucena and the Philidor positions and play each against a bot from both sides.",
  ),
  blunder_check: lesson(
    "Blunder check",
    "A short routine before every move removes most blunders.",
    "Most club-level games are decided not by strategy but by one blunder. The habit of spending 10–20 seconds checking your move against simple threats reduces them more than any amount of theory.",
    "Before moving, ask three questions: 1) what does the opponent’s last move threaten? 2) which of my pieces will be undefended after my move? 3) what checks, captures and threats will the opponent have after my move? If the answer worries you, look for another move.",
    "Checking only your own line and not the opponent’s reply. Playing “obvious” moves instantly — especially captures and retreats. Skipping the check in time trouble, when it matters most (use a short version: the opponent’s checks and captures).",
    "Play 5 rapid games against a bot, saying the three questions out loud before every move. Note how often the check changed your move. Then go through your recent blunders: which question would have caught each one.",
  ),
  tactical_vision: lesson(
    "Tactical vision",
    "Seeing tactics means knowing the motifs and checking checks, captures and threats every move.",
    "Tactics grow out of motifs: loose pieces, a king on an open line, pieces on one line, overloaded defenders. When such a motif is on the board, there is almost always a combination. Missed chances (misses) are the moments when the motif was there and you didn’t see it.",
    "Every move, quickly scan the forcing moves: all your checks, captures and threats, even silly-looking ones. Note the motifs: what is undefended, what stands on one line, where the king is weak.",
    "Looking for tactics only when you “feel” them. Dismissing sacrifices without calculating them to the end. Seeing your own tactics and missing the opponent’s defensive ones. Solving puzzles for speed instead of accuracy.",
    "Every day solve 15–20 puzzles on the themes you miss — slowly, calculating the line to the end. Once a week do a timed run to carry the pattern recognition into fast games.",
  ),
  converting_advantage: lesson(
    "Converting an advantage",
    "A winning position is not a win yet. Simplify, remove counterplay, don’t rush.",
    "When you are ahead in material or position, the main task is to give the opponent no chances. Trade pieces (not pawns), secure your king, neutralise their activity — and only then push forward. Winning positions are won by technique, not by fireworks.",
    "If the evaluation is clearly in your favour, switch to “safety mode”: what counter-chances does the opponent have — an attack on the king, a passed pawn, perpetual check? Remove them first. Offer trades the opponent cannot decline.",
    "Relaxing and playing fast. Chasing even more material and exposing your king. Trading pawns and leaving the opponent drawing chances. Allowing perpetual check because of a careless queen and king placement.",
    "Play out winning positions from your own games against a bot (the endgame trainer) until you win. After each, write down which trade or move removed the opponent’s last counterplay.",
  ),
  defense: lesson(
    "Defending difficult positions",
    "A bad position is not a lost one. Create problems and look for resources.",
    "In a worse position the goal is to make winning as hard as possible for the opponent: keep pieces for counterplay, create threats, trade their attacking pieces, head for endings with drawing chances (opposite-coloured bishops, rook endings). Many games at 1500–2000 are saved by stubborn defence.",
    "When the position turns bad, don’t give up mentally. Ask: which moves are awkward for the opponent? Is there perpetual check, a fortress, stalemate? Which trade reduces their attack?",
    "Despairing and playing fast. Resigning too early. Clinging to material when activity is needed. Staying passive while the opponent calmly improves.",
    "Play 3 games against a stronger bot and, each time you get a worse position, write down after the game what resources there were. Review your lost games with a worse but not hopeless position: where could you have defended more stubbornly.",
  ),
  time_management: lesson(
    "Time management",
    "Think long in critical positions and fast in simple ones. Stay out of time trouble.",
    "Time is a resource, like material. Spend it on critical moments: choosing a plan, trades, tactical positions, transitions to the endgame. Simple moves (recaptures, only moves, a familiar opening) should be quick. Hasty mistakes and time trouble are usually a problem of distributing time, not of thinking speed.",
    "Signs of a critical position: many forcing moves, tension in the centre, a decision about a trade, a king under threat. Here you can spend 2–3 minutes in rapid. If little time is left with many moves to go, play solidly and avoid sharp complications.",
    "Thinking long over familiar opening moves. Recalculating the same line in circles. Replying instantly in sharp positions. Leaving less than a minute for the last ten moves.",
    "Play 5 rapid games aiming to have at least half your time left at move 20. After each game, mark 2–3 moves where you should have thought longer and 2–3 where time was wasted. A timed puzzle run helps you solve simple things faster.",
  ),
  opening_repertoire: lesson(
    "Your repertoire",
    "A small set of openings you understand scores more than broad theory.",
    "A repertoire is your answers to the opponent’s main moves with White and with Black. Its job is to reach familiar positions where you know the plans and the typical tactics. Understanding ideas matters more than memorising long lines.",
    "Look at your opening statistics: where you score worse than usual, there is a problem — not knowing the plan, a typical trap, an awkward structure. Those lines are the ones to learn first.",
    "Changing openings after every loss. Learning moves without ideas and getting lost at the first deviation. Choosing an opening whose positions you don’t enjoy. Never reviewing your own games in that opening.",
    "Pick the opening where your results are worst and go through the course built from your own games. Then play 5 games with it against a bot and compare your moves with the course after each one.",
  ),
  book_attack_targets: book(
    "What to attack: targets that cannot run",
    "An attack only makes sense if its target cannot step aside. A piece retreats; a weak pawn stays where it is — that is what you play against.",
    [
      [
        "The target must not run",
        "Attacking something that can simply move away wastes time. Lasker shows the typical mistake: chasing a bishop with queenside pawns (a3, b4, a4, a5). The bishop calmly steps to the next square and is just as good there, while the pawns are advanced and weakened — five moves spent against three.\n\nA piece can only be held in place by a pin. A pawn can be held by a blockade (a piece right in front of it) or by controlling the square in front of it with more force than the opponent has.",
      ],
      [
        "Don't chase pieces with pawns",
        "When an enemy queen or knight is annoying, it is tempting to kick it with a pawn. The piece will find another good square, and if the pawn move left a backward pawn behind, that weakness stays for the rest of the game. Lasker calls such short-lived pawn attacks on pieces always doubtful. The same goes for pieces: don't send your own pieces far away just to drive off an enemy one.",
      ],
      [
        "Playing against a backward pawn",
        "Lasker's scheme: keep the pawn from advancing (occupy or control the square in front of it), double rooks on the half-open file, bring up the queen and bishop. The defender can protect the pawn as many times as it is attacked, but the pawn cannot move, and the attacker still has a reserve — bringing up a pawn of his own. It is even easier when the defender has no bishop of the pawn's colour. The square in front of a backward pawn is a ready-made outpost for a knight.",
      ],
      [
        "In the games",
        "Blackburne–Nimzowitsch (1914): Black's centralised knight forced c3, leaving White a backward pawn on d3. Teichmann–Amateurs (1902): after Black's pawn advance a white knight settled on d6 and paralysed Black's whole game. Chajes–Capablanca (1916): a knight on d5 that nothing can dislodge — in Capablanca's words, the game is won strategically.",
      ],
    ],
    { ref: `${LASKER}, ch. VI "The Middle Game"`, quote: { text: "Attacks should only be directed to objects which cannot be moved away.", author: "Edward Lasker" } },
  ),
  book_king_pawns: book(
    "Pawns in front of the castled king",
    "Every pawn move in front of your own king leaves squares unguarded. Lasker explains when that is fatal and when it is bearable.",
    [
      [
        "Why pawn moves are dangerous",
        "A pawn that has advanced no longer guards the squares it used to — and in front of a castled king, those are exactly the squares enemy pieces come in through. The advanced pawn also becomes a target: the opponent brings up a pawn on the next file to open lines for his rooks, or sacrifices a piece for the pawns of the shelter.",
      ],
      [
        "h3 against a pin, and the holes after g3",
        "To prevent a pin with Bg5, beginners play h3 (h6) in advance. That loses time and weakens the king. The pin on a knight on f6 is only dangerous if nothing is done against Nd5 and a doubled attack on f6; the normal defence is to develop the bishop to e6.\n\nAfter g3 (g6) the squares f3 and h3 (f6 and h6) are weak. The opponent's plan: Qd2 and Bh6, trading off the defending bishop, then queen and knight break in on f6 or h6. The weakness only matters while the opponent has pieces that can use it: once that bishop is traded, the holes are nearly harmless.",
      ],
      [
        "When to attack with pawns",
        "When both kings are castled on the same side, starting an attack by pushing the pawns in front of your own king is rarely right — only when overwhelming force can be gathered quickly, before a counter-attack. Marshall–Burn (1907): h4–h5 against g6, while Black's queenside was still undeveloped, ripped open the h-file. If the rook has already left the h-file, the plan with Bh6 is better.",
      ],
      [
        "In the games",
        "Tarrasch–Capablanca (1911): g3, with no direct threat to meet, weakened f3 and h3. Tarrasch–Spielmann (1914): Black prepares Qc8 and Bh3 to trade bishops and leave holes on f3 and h3. Capablanca–Alekhine (1913): to cover the weak h6 square Alekhine brought his knight back to g8 — and it never got back into play.",
      ],
    ],
    { ref: `${LASKER}, ch. VI "The Middle Game"`, quote: { text: "Pawn moves always create weaknesses.", author: "Edward Lasker" } },
  ),
  book_open_files: book(
    "Open files and the seventh rank",
    "Whoever occupies the open files first dictates the game. Lasker shows the road from owning a file to winning a pawn.",
    [
      [
        "A file is a road for the rooks",
        "In Lazard–Lasker (Paris, 1914) both pawn structures are broken, and the game is decided by who takes the open files first. Lasker (Black) did not defend a pawn passively with his bishop but doubled rooks on the b-file: now he could enter the seventh or eighth rank and attack the pawns from the side and from behind.",
      ],
      [
        "A rook on the seventh",
        "Even the threat of invasion paralyses: the opponent's pieces have to guard the pawns and lose mobility. But for the invasion to achieve something, the pawns must be deprived of support — Lasker played c5–c4 and f5. Then he traded one pair of rooks so that the remaining enemy rook could not break in along its own file, and guarded its entry squares with the king. And don't forget a loophole for your own king (h3), or the rook can never leave the back rank.",
      ],
      [
        "A file has to be held",
        "Opening a file is not enough. Lasker's note to Tartakower–Asztalos (1913): the capture that opens the a-file is premature — first the rooks and queen must be placed on that file. The reverse trick: a piece covering the entry square (a bishop on e6 against a rook on d7) makes the opponent's file worthless.",
      ],
      [
        "In the games",
        "Salwe–Marshall (1908): Black already has two open files for his rooks. Capablanca–Alekhine (1913): White takes the seventh rank and Black's position collapses quickly. Griffith–Gunston (1902): White has open files and diagonals for every piece while Black's pieces are tied up.",
      ],
    ],
    { ref: `${LASKER}, ch. VI "The Middle Game" (Lazard–Lasker)`, quote: { text: "The player that occupies the open files first, gets a decisive advantage.", author: "Edward Lasker" } },
  ),
  book_pawn_weaknesses: book(
    "Doubled and broken pawns",
    "A doubled pawn is not always a weakness. What matters is which pieces remain and where the game is heading — an attack or an endgame.",
    [
      [
        "A doubled pawn is also a file",
        "A capture that doubles your pawns opens a file for a rook and can support a pawn advance in the centre. A doubled pawn that is not isolated is not necessarily weak; the truly bad one is a doubled isolated pawn. Lasker adds that it does become a weakness if the king castles behind it.",
      ],
      [
        "Middlegame or endgame",
        "Lasker compares two structures. Without the g-pawn, f6 and h6 are weak — dangerous in the middlegame, but hardly a problem in the endgame, since the f- and h-pawns are near the king. Without the b-pawn there is nothing to attack in the middlegame, but the a- and c-pawns are weak in the endgame because the king cannot reach them — especially in rook endings. The compensation is an open file for the rooks; the weak a-pawn can be pushed and traded off.",
      ],
      [
        "What you get in return",
        "Yates–Esser (1914): Black accepts doubled pawns to keep the two bishops. Em. Lasker–Capablanca (1914): White captures on c6 to head for an endgame with four pawns against three on the kingside, while Black's queenside majority is devalued by the doubled pawn.",
      ],
      [
        "Capablanca on pawns",
        "Pawns are strongest side by side on the same rank; advancing a centre pawn to the fifth rank decides the character of the whole game. A passed pawn is either very weak or very strong, and its strength grows as pieces come off. In Marshall–Capablanca (1918) a doubled, isolated pawn on h4 exerts enormous pressure.",
      ],
    ],
    { ref: `${LASKER}, ch. VI; ${CAPABLANCA}, § 31 "Some Salient Points about Pawns"`, quote: { text: "Two or more Pawns are strongest when they are in the same rank next to one another.", author: "J. R. Capablanca" } },
  ),
  book_initiative: book(
    "The initiative",
    "The right to move is the initiative. Keep it as long as possible and give it up only for a material or positional gain.",
    [
      [
        "What the initiative is",
        "In the starting position material and placement are equal, but White has the move — that is, the initiative. While developing, you should also hinder the opponent's development, applying pressure wherever possible, above all in the centre. Give up the initiative only when you get something for it and are sure you can withstand the counter-attack and then, thanks to your extra material, take the initiative back.",
      ],
      [
        "Three kinds of positions",
        "Once the pieces are developed, Capablanca distinguishes three cases. A direct attack on the king — carried out with sufficient force. Improving a position — if the opponent has no weaknesses, create some. Winning material at the cost of the initiative for a while — then you weather the attack and, once it is repulsed, act quickly with all your forces.",
      ],
      [
        "The threat is stronger than its execution",
        "Threatening is always useful, but carry a threat out only if it gains something at once. While the threat hangs, the opponent must keep forces ready to meet it and may overlook a blow elsewhere; once executed, the threat no longer exists. The best manoeuvre: a demonstration on one wing to draw the opponent's forces there, then a quick switch to the other wing and a breakthrough before the defenders can come over. The same principle works in the endgame.",
      ],
      [
        "In the games",
        "Barasz–Mieses (1912): White let Black develop the queenside undisturbed, and the initiative passed to Black. Capablanca–Marshall (1914): Black gives up a pawn to free his game and seize the initiative. Chajes–Capablanca (1916): Capablanca admits he tried to take the initiative too early. Marshall–Capablanca (1918): White cannot bear the slow pressure and gives up pawns for counterplay.",
      ],
    ],
    { ref: `${CAPABLANCA}, § 20–23, § 26`, quote: { text: "It is always an advantage to threaten something.", author: "J. R. Capablanca" } },
  ),
  book_cut_off_pieces: book(
    "Pieces out of play",
    "Cutting an enemy piece off from the fight is almost as good as winning it: in the battle you are a piece up.",
    [
      [
        "An extra piece where it matters",
        "Capablanca writes that a master often plays only to cut off one of the opponent's pieces from the scene of action. If a bishop or knight is completely shut out, the game can be considered practically won: for all practical purposes one side has an extra piece.",
      ],
      [
        "How pieces fall out of play",
        "A knight goes to the rim to cover a weak square; a rook is locked in by its own pawns; a bishop bites on its own pawn chain. Lasker calls the middlegame the pieces' own hunting ground: the first rule is to avoid moves that reduce your pieces' mobility, and not to send pieces far away just to drive off an enemy piece.",
      ],
      [
        "Material without play",
        "Extra material is worth nothing if it is out of play. Capablanca–Bernstein (1914): Black is a whole rook up, but it is as cut off as his entire queenside, and the king is driven into a mating net. Nimzowitsch–Tarrasch (1912): as long as Black's h8 rook stays out of play, every exchange favours White.",
      ],
      [
        "Check your own games",
        "For each of your pieces, ask: is it taking part in the fight on the important wing? If not — by which route does it come back, and how many moves will that take? And the other way round: which enemy piece can be shut out with one pawn move or exchange?",
      ],
    ],
    { ref: `${CAPABLANCA}, § 24 "Cutting off Pieces from the Scene of Action"; ${LASKER}, ch. VI`, quote: { text: "Often a Bishop or a Knight is completely put out of action.", author: "J. R. Capablanca" } },
  ),
  book_endgame_king: book(
    "Heading for the endgame, and an active king",
    "Once your advantage is enough to win the endgame, trade pieces. In the endgame the king is a strong piece.",
    [
      [
        "Exchanges are not dull",
        "Lasker notes that beginners avoid exchanges, especially of queens, thinking the game will become dull. But if your advantage is enough to win the endgame, you should exchange down to the familiar elementary cases — that is the shortest way to victory. That is also why in the middlegame you must keep a healthy pawn structure at all times: an exchange can turn the game into an endgame at any moment.",
      ],
      [
        "The king goes forward",
        "In the endgame the king attacks pawns and escorts its own passed pawns. Leonhardt–Marshall (1911): Black's king marches irresistibly towards White's weakened pawns. In his game with Em. Lasker (1914) Capablanca reasons that the king should stay on the wing where the opponent has a pawn majority, to stop its advance later.",
      ],
      [
        "“A unit that holds two”",
        "Capablanca: in pawn endings, advance the pawn that has no enemy pawn facing it. And the key principle: one unit holds two — a single well-placed pawn stops two enemy pawns. Capablanca calls this one of the principal weapons of a master.",
      ],
      [
        "Passed pawns",
        "A passed pawn grows stronger with every exchange. Berlin–Riga (1908–09): Black no longer fears a trade of rooks — the king will go for the queenside pawns while the passed pawns keep White's pieces busy. Janowski–Capablanca (1913): Black found no defence against White's two passed pawns.",
      ],
    ],
    { ref: `${LASKER}, ch. VI "General Remarks"; ${CAPABLANCA}, § 9, § 13, § 31`, quote: { text: "A unit that holds two.", author: "J. R. Capablanca" } },
  ),
  book_rook_endings: book(
    "Rook endings",
    "The most common endings and among the hardest: even a “simple” position with an extra pawn demands accuracy.",
    [
      [
        "The most common ending",
        "Capablanca: endings with one rook and pawns occur more often than any other kind, yet few players have mastered them. His example is Marshall–Rosenthal (1909–10): there was a simple win with a rook check, but an inaccurate pawn move gave the opponent a single drawing move, which he failed to find.",
      ],
      [
        "The danger of a safe position",
        "Marshall–Kupchik (Havana, 1913): Black, a pawn up, felt so sure of his position that he made three careless moves — took a pawn instead of giving an active check, did not make room for his king — and lost. The lesson: with an extra pawn, look for the most active move first, not the greediest.",
      ],
      [
        "Active rook, active king",
        "Rubinstein–Capablanca (1911): Lasker thinks Black should first have brought his king up and kept the enemy rook off its active square. Marshall–Capablanca (1918): an active rook move is “much better than taking pawns” — it forces the opponent onto the defensive. In his game with Em. Lasker (1914) Capablanca reproaches himself for irresolution: once a plan is made, carry it out.",
      ],
      [
        "A passed pawn on the majority side",
        "Lasker: in a rook ending with an extra pawn, advance the pawns on the wing where you have the majority, to get a passed pawn as soon as possible. The farther it is from the enemy king, the stronger it is.",
      ],
    ],
    { ref: `${CAPABLANCA}, § 27–28; ${LASKER}, game notes`, quote: { text: "When a plan is made, it must be carried out if at all possible.", author: "J. R. Capablanca" } },
  ),
};
