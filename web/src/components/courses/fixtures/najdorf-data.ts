// Сгенерировано generate_najdorf.py — не править руками. Dev-фикстура (сессия 13.7):
// дерево курса «Найдорф за чёрных», идеи RU/EN из app.plans, оценки Stockfish.
import type { CourseTree, RenderedIdeas } from "@/lib/courses-api";

export const najdorfTree: CourseTree = {
 "version": 1,
 "color": "black",
 "line_end": 10,
 "nodes": [
  {
   "id": 0,
   "parent": null,
   "children": [
    1
   ],
   "ply": 0,
   "uci": null,
   "san": null,
   "mover": null,
   "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
   "book": true,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": null,
   "eval": {
    "cp": 27,
    "mate": null,
    "depth": 14,
    "best_uci": "e2e4"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 1,
   "parent": 0,
   "children": [
    2
   ],
   "ply": 1,
   "uci": "e2e4",
   "san": "e4",
   "mover": "opponent",
   "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
   "book": true,
   "name": "King's Pawn Game",
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 812000,
    "white": 261708,
    "draws": 313351,
    "black": 236941,
    "average_rating": 2487
   },
   "eval": {
    "cp": 27,
    "mate": null,
    "depth": 14,
    "best_uci": "c7c5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 2,
   "parent": 1,
   "children": [
    3
   ],
   "ply": 2,
   "uci": "c7c5",
   "san": "c5",
   "mover": "learner",
   "fen": "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
   "book": true,
   "name": "Sicilian Defense",
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 598738,
    "white": 183013,
    "draws": 255433,
    "black": 160292,
    "average_rating": 2497
   },
   "eval": {
    "cp": 36,
    "mate": null,
    "depth": 14,
    "best_uci": "g1f3"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 3,
   "parent": 2,
   "children": [
    4
   ],
   "ply": 3,
   "uci": "g1f3",
   "san": "Nf3",
   "mover": "opponent",
   "fen": "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
   "book": true,
   "name": "Sicilian Defense",
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 598738,
    "white": 184450,
    "draws": 253922,
    "black": 160366,
    "average_rating": 2487
   },
   "eval": {
    "cp": 38,
    "mate": null,
    "depth": 14,
    "best_uci": "b8c6"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 4,
   "parent": 3,
   "children": [
    5
   ],
   "ply": 4,
   "uci": "d7d6",
   "san": "d6",
   "mover": "learner",
   "fen": "rnbqkbnr/pp2pppp/3p4/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3",
   "book": true,
   "name": "Sicilian Defense: Modern Variations",
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 385251,
    "white": 120942,
    "draws": 159159,
    "black": 105150,
    "average_rating": 2494
   },
   "eval": {
    "cp": 38,
    "mate": null,
    "depth": 14,
    "best_uci": "d2d4"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 5,
   "parent": 4,
   "children": [
    6
   ],
   "ply": 5,
   "uci": "d2d4",
   "san": "d4",
   "mover": "opponent",
   "fen": "rnbqkbnr/pp2pppp/3p4/2p5/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 3",
   "book": true,
   "name": "Sicilian Defense",
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 385251,
    "white": 115546,
    "draws": 167380,
    "black": 102325,
    "average_rating": 2447
   },
   "eval": {
    "cp": 33,
    "mate": null,
    "depth": 14,
    "best_uci": "c5d4"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 6,
   "parent": 5,
   "children": [
    7
   ],
   "ply": 6,
   "uci": "c5d4",
   "san": "cxd4",
   "mover": "learner",
   "fen": "rnbqkbnr/pp2pppp/3p4/8/3pP3/5N2/PPP2PPP/RNBQKB1R w KQkq - 0 4",
   "book": true,
   "name": "Sicilian Defense",
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 268784,
    "white": 79975,
    "draws": 119277,
    "black": 69532,
    "average_rating": 2443
   },
   "eval": {
    "cp": 38,
    "mate": null,
    "depth": 14,
    "best_uci": "f3d4"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 7,
   "parent": 6,
   "children": [
    8
   ],
   "ply": 7,
   "uci": "f3d4",
   "san": "Nxd4",
   "mover": "opponent",
   "fen": "rnbqkbnr/pp2pppp/3p4/8/3NP3/8/PPP2PPP/RNBQKB1R b KQkq - 0 4",
   "book": true,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 268784,
    "white": 77608,
    "draws": 123452,
    "black": 67724,
    "average_rating": 2477
   },
   "eval": {
    "cp": 37,
    "mate": null,
    "depth": 14,
    "best_uci": "g8f6"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 8,
   "parent": 7,
   "children": [
    9
   ],
   "ply": 8,
   "uci": "g8f6",
   "san": "Nf6",
   "mover": "learner",
   "fen": "rnbqkb1r/pp2pppp/3p1n2/8/3NP3/8/PPP2PPP/RNBQKB1R w KQkq - 1 5",
   "book": true,
   "name": "Sicilian Defense: Modern Variations, Main Line",
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 170756,
    "white": 50503,
    "draws": 75032,
    "black": 45221,
    "average_rating": 2507
   },
   "eval": {
    "cp": 30,
    "mate": null,
    "depth": 14,
    "best_uci": "b1c3"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 9,
   "parent": 8,
   "children": [
    10
   ],
   "ply": 9,
   "uci": "b1c3",
   "san": "Nc3",
   "mover": "opponent",
   "fen": "rnbqkb1r/pp2pppp/3p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R b KQkq - 2 5",
   "book": true,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 170756,
    "white": 50037,
    "draws": 75583,
    "black": 45136,
    "average_rating": 2551
   },
   "eval": {
    "cp": 28,
    "mate": null,
    "depth": 14,
    "best_uci": "a7a6"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 10,
   "parent": 9,
   "children": [
    11,
    49,
    65
   ],
   "ply": 10,
   "uci": "a7a6",
   "san": "a6",
   "mover": "learner",
   "fen": "rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6",
   "book": true,
   "name": "Sicilian Defense: Najdorf Variation",
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 135047,
    "white": 39596,
    "draws": 59337,
    "black": 36114,
    "average_rating": 2505
   },
   "eval": {
    "cp": 25,
    "mate": null,
    "depth": 14,
    "best_uci": "c1e3"
   },
   "ideas": {
    "structures": [],
    "ideas": [
     {
      "key": "pawn_break_now",
      "side": "black",
      "params": {
       "target": "e4",
       "san": "d5"
      }
     },
     {
      "key": "pawn_break_prepare",
      "side": "white",
      "params": {
       "target": "d6",
       "move": "e4–e5"
      }
     },
     {
      "key": "pawn_break_prepare",
      "side": "black",
      "params": {
       "target": "e4",
       "move": "f7–f5"
      }
     },
     {
      "key": "rook_half_open",
      "side": "white",
      "params": {
       "file": "d",
       "target": "d6"
      }
     },
     {
      "key": "rook_half_open",
      "side": "black",
      "params": {
       "file": "c",
       "target": "c2"
      }
     },
     {
      "key": "majority",
      "side": "white",
      "params": {
       "wing": "queenside",
       "own": "3",
       "other": "2"
      }
     }
    ],
    "breaks": [
     {
      "side": "black",
      "uci": "d6d5",
      "san": "d5",
      "target": "e4",
      "legal_now": true
     },
     {
      "side": "white",
      "uci": "e4e5",
      "san": null,
      "target": "d6",
      "legal_now": false
     },
     {
      "side": "black",
      "uci": "f7f5",
      "san": null,
      "target": "e4",
      "legal_now": false
     }
    ],
    "outposts": [],
    "weaknesses": [],
    "open_files": [],
    "half_open_files": {
     "white": [
      "d"
     ],
     "black": [
      "c"
     ]
    }
   },
   "key_moment": "line_end"
  },
  {
   "id": 11,
   "parent": 10,
   "children": [
    12
   ],
   "ply": 11,
   "uci": "c1e3",
   "san": "Be3",
   "mover": "opponent",
   "fen": "rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N1B3/PPP2PPP/R2QKB1R b KQkq - 1 6",
   "book": true,
   "name": "Sicilian Defense: Najdorf Variation, English Attack",
   "main": false,
   "weight": 0.42,
   "stats": {
    "source": "masters",
    "games": 56720,
    "white": 18024,
    "draws": 22437,
    "black": 16259,
    "average_rating": 2499
   },
   "eval": {
    "cp": 28,
    "mate": null,
    "depth": 14,
    "best_uci": "e7e5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 12,
   "parent": 11,
   "children": [
    13,
    35,
    43
   ],
   "ply": 12,
   "uci": "e7e5",
   "san": "e5",
   "mover": "learner",
   "fen": "rnbqkb1r/1p3ppp/p2p1n2/4p3/3NP3/2N1B3/PPP2PPP/R2QKB1R w KQkq - 0 7",
   "book": true,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 40136,
    "white": 11787,
    "draws": 17479,
    "black": 10870,
    "average_rating": 2549
   },
   "eval": {
    "cp": 22,
    "mate": null,
    "depth": 14,
    "best_uci": "d4b3"
   },
   "ideas": {
    "structures": [
     "sicilian_d6_e5"
    ],
    "ideas": [
     {
      "key": "sicilian_d6_e5.d5_break",
      "side": "black",
      "params": {
       "pawn": "d6",
       "hole": "d5",
       "e": "e5",
       "san": "d5"
      }
     },
     {
      "key": "sicilian_d6_e5.d5",
      "side": "white",
      "params": {
       "square": "d5",
       "pieces": "Nf6"
      }
     },
     {
      "key": "pawn_break_now",
      "side": "white",
      "params": {
       "target": "e5",
       "san": "f4"
      }
     },
     {
      "key": "target_backward",
      "side": "white",
      "params": {
       "pawn": "d6"
      }
     },
     {
      "key": "pawn_break_prepare",
      "side": "black",
      "params": {
       "target": "e4",
       "move": "f7–f5"
      }
     },
     {
      "key": "rook_half_open",
      "side": "black",
      "params": {
       "file": "c",
       "target": "c2"
      }
     },
     {
      "key": "majority",
      "side": "white",
      "params": {
       "wing": "queenside",
       "own": "3",
       "other": "2"
      }
     }
    ],
    "breaks": [
     {
      "side": "white",
      "uci": "f2f4",
      "san": "f4",
      "target": "e5",
      "legal_now": true
     },
     {
      "side": "black",
      "uci": "d6d5",
      "san": "d5",
      "target": "e4",
      "legal_now": true
     },
     {
      "side": "black",
      "uci": "f7f5",
      "san": null,
      "target": "e4",
      "legal_now": false
     }
    ],
    "outposts": [
     {
      "side": "white",
      "square": "d5"
     }
    ],
    "weaknesses": [
     {
      "side": "black",
      "square": "d6",
      "kind": "backward"
     },
     {
      "side": "black",
      "square": "d5",
      "kind": "hole"
     }
    ],
    "open_files": [],
    "half_open_files": {
     "white": [
      "d"
     ],
     "black": [
      "c"
     ]
    }
   },
   "key_moment": "structure"
  },
  {
   "id": 13,
   "parent": 12,
   "children": [
    14
   ],
   "ply": 13,
   "uci": "d4b3",
   "san": "Nb3",
   "mover": "opponent",
   "fen": "rnbqkb1r/1p3ppp/p2p1n2/4p3/4P3/1NN1B3/PPP2PPP/R2QKB1R b KQkq - 1 7",
   "book": true,
   "name": null,
   "main": false,
   "weight": 0.71,
   "stats": {
    "source": "masters",
    "games": 28497,
    "white": 8569,
    "draws": 12170,
    "black": 7758,
    "average_rating": 2550
   },
   "eval": {
    "cp": 27,
    "mate": null,
    "depth": 14,
    "best_uci": "f8e7"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 14,
   "parent": 13,
   "children": [
    15,
    25,
    31
   ],
   "ply": 14,
   "uci": "c8e6",
   "san": "Be6",
   "mover": "learner",
   "fen": "rn1qkb1r/1p3ppp/p2pbn2/4p3/4P3/1NN1B3/PPP2PPP/R2QKB1R w KQkq - 2 8",
   "book": true,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 20944,
    "white": 6271,
    "draws": 8912,
    "black": 5761,
    "average_rating": 2528
   },
   "eval": {
    "cp": 23,
    "mate": null,
    "depth": 14,
    "best_uci": "f2f4"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 15,
   "parent": 14,
   "children": [
    16
   ],
   "ply": 15,
   "uci": "f2f3",
   "san": "f3",
   "mover": "opponent",
   "fen": "rn1qkb1r/1p3ppp/p2pbn2/4p3/4P3/1NN1BP2/PPP3PP/R2QKB1R b KQkq - 0 8",
   "book": true,
   "name": "Sicilian Defense: Najdorf Variation, English Attack",
   "main": false,
   "weight": 0.74,
   "stats": {
    "source": "masters",
    "games": 15499,
    "white": 4492,
    "draws": 6850,
    "black": 4157,
    "average_rating": 2507
   },
   "eval": {
    "cp": 21,
    "mate": null,
    "depth": 14,
    "best_uci": "h7h5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 16,
   "parent": 15,
   "children": [
    17
   ],
   "ply": 16,
   "uci": "f8e7",
   "san": "Be7",
   "mover": "learner",
   "fen": "rn1qk2r/1p2bppp/p2pbn2/4p3/4P3/1NN1BP2/PPP3PP/R2QKB1R w KQkq - 1 9",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 11537,
    "white": 3589,
    "draws": 4793,
    "black": 3155,
    "average_rating": 2474
   },
   "eval": {
    "cp": 35,
    "mate": null,
    "depth": 14,
    "best_uci": "d1d2"
   },
   "ideas": {
    "structures": [
     "sicilian_d6_e5"
    ],
    "ideas": [
     {
      "key": "sicilian_d6_e5.d5_break",
      "side": "black",
      "params": {
       "pawn": "d6",
       "hole": "d5",
       "e": "e5",
       "san": "d5"
      }
     },
     {
      "key": "sicilian_d6_e5.d5",
      "side": "white",
      "params": {
       "square": "d5",
       "pieces": "Be6,Nf6"
      }
     },
     {
      "key": "pawn_break_now",
      "side": "white",
      "params": {
       "target": "e5",
       "san": "f4"
      }
     },
     {
      "key": "target_backward",
      "side": "white",
      "params": {
       "pawn": "d6"
      }
     },
     {
      "key": "pawn_break_prepare",
      "side": "black",
      "params": {
       "target": "e4",
       "move": "f7–f5"
      }
     },
     {
      "key": "rook_half_open",
      "side": "black",
      "params": {
       "file": "c",
       "target": "c2"
      }
     },
     {
      "key": "majority",
      "side": "white",
      "params": {
       "wing": "queenside",
       "own": "3",
       "other": "2"
      }
     }
    ],
    "breaks": [
     {
      "side": "white",
      "uci": "f3f4",
      "san": "f4",
      "target": "e5",
      "legal_now": true
     },
     {
      "side": "black",
      "uci": "d6d5",
      "san": "d5",
      "target": "e4",
      "legal_now": true
     },
     {
      "side": "black",
      "uci": "f7f5",
      "san": null,
      "target": "e4",
      "legal_now": false
     }
    ],
    "outposts": [
     {
      "side": "white",
      "square": "d5"
     }
    ],
    "weaknesses": [
     {
      "side": "black",
      "square": "d6",
      "kind": "backward"
     },
     {
      "side": "white",
      "square": "e3",
      "kind": "hole"
     },
     {
      "side": "black",
      "square": "d5",
      "kind": "hole"
     }
    ],
    "open_files": [],
    "half_open_files": {
     "white": [
      "d"
     ],
     "black": [
      "c"
     ]
    }
   },
   "key_moment": "book_exit"
  },
  {
   "id": 17,
   "parent": 16,
   "children": [
    18
   ],
   "ply": 17,
   "uci": "d1d2",
   "san": "Qd2",
   "mover": "opponent",
   "fen": "rn1qk2r/1p2bppp/p2pbn2/4p3/4P3/1NN1BP2/PPPQ2PP/R3KB1R b KQkq - 2 9",
   "book": false,
   "name": null,
   "main": false,
   "weight": 0.81,
   "stats": {
    "source": "masters",
    "games": 9345,
    "white": 2959,
    "draws": 3776,
    "black": 2610,
    "average_rating": 2553
   },
   "eval": {
    "cp": 34,
    "mate": null,
    "depth": 14,
    "best_uci": "e8g8"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 18,
   "parent": 17,
   "children": [
    19
   ],
   "ply": 18,
   "uci": "e8g8",
   "san": "O-O",
   "mover": "learner",
   "fen": "rn1q1rk1/1p2bppp/p2pbn2/4p3/4P3/1NN1BP2/PPPQ2PP/R3KB1R w KQ - 3 10",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 6695,
    "white": 2172,
    "draws": 2607,
    "black": 1916,
    "average_rating": 2485
   },
   "eval": {
    "cp": 34,
    "mate": null,
    "depth": 14,
    "best_uci": "e1c1"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 19,
   "parent": 18,
   "children": [
    20
   ],
   "ply": 19,
   "uci": "e1c1",
   "san": "O-O-O",
   "mover": "opponent",
   "fen": "rn1q1rk1/1p2bppp/p2pbn2/4p3/4P3/1NN1BP2/PPPQ2PP/2KR1B1R b - - 4 10",
   "book": false,
   "name": null,
   "main": false,
   "weight": 0.88,
   "stats": {
    "source": "masters",
    "games": 5892,
    "white": 1856,
    "draws": 2429,
    "black": 1607,
    "average_rating": 2504
   },
   "eval": {
    "cp": 39,
    "mate": null,
    "depth": 14,
    "best_uci": "b8d7"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 20,
   "parent": 19,
   "children": [
    21
   ],
   "ply": 20,
   "uci": "b8d7",
   "san": "Nbd7",
   "mover": "learner",
   "fen": "r2q1rk1/1p1nbppp/p2pbn2/4p3/4P3/1NN1BP2/PPPQ2PP/2KR1B1R w - - 5 11",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 4047,
    "white": 1311,
    "draws": 1563,
    "black": 1173,
    "average_rating": 2511
   },
   "eval": {
    "cp": 30,
    "mate": null,
    "depth": 14,
    "best_uci": "g2g4"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 21,
   "parent": 20,
   "children": [
    22
   ],
   "ply": 21,
   "uci": "g2g4",
   "san": "g4",
   "mover": "opponent",
   "fen": "r2q1rk1/1p1nbppp/p2pbn2/4p3/4P1P1/1NN1BP2/PPPQ3P/2KR1B1R b - - 0 11",
   "book": false,
   "name": null,
   "main": false,
   "weight": 0.9,
   "stats": {
    "source": "masters",
    "games": 3642,
    "white": 1184,
    "draws": 1455,
    "black": 1003,
    "average_rating": 2473
   },
   "eval": {
    "cp": 45,
    "mate": null,
    "depth": 14,
    "best_uci": "b7b5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 22,
   "parent": 21,
   "children": [
    23
   ],
   "ply": 22,
   "uci": "b7b5",
   "san": "b5",
   "mover": "learner",
   "fen": "r2q1rk1/3nbppp/p2pbn2/1p2p3/4P1P1/1NN1BP2/PPPQ3P/2KR1B1R w - - 0 12",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 2636,
    "white": 835,
    "draws": 1094,
    "black": 707,
    "average_rating": 2500
   },
   "eval": {
    "cp": 45,
    "mate": null,
    "depth": 14,
    "best_uci": "g4g5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 23,
   "parent": 22,
   "children": [
    24
   ],
   "ply": 23,
   "uci": "g4g5",
   "san": "g5",
   "mover": "opponent",
   "fen": "r2q1rk1/3nbppp/p2pbn2/1p2p1P1/4P3/1NN1BP2/PPPQ3P/2KR1B1R b - - 0 12",
   "book": false,
   "name": null,
   "main": false,
   "weight": 0.85,
   "stats": {
    "source": "masters",
    "games": 2241,
    "white": 686,
    "draws": 1005,
    "black": 550,
    "average_rating": 2533
   },
   "eval": {
    "cp": 60,
    "mate": null,
    "depth": 14,
    "best_uci": "b5b4"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 24,
   "parent": 23,
   "children": [],
   "ply": 24,
   "uci": "b5b4",
   "san": "b4",
   "mover": "learner",
   "fen": "r2q1rk1/3nbppp/p2pbn2/4p1P1/1p2P3/1NN1BP2/PPPQ3P/2KR1B1R w - - 0 13",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 1442,
    "white": 478,
    "draws": 581,
    "black": 383,
    "average_rating": 2558
   },
   "eval": {
    "cp": 60,
    "mate": null,
    "depth": 14,
    "best_uci": "c3e2"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 25,
   "parent": 14,
   "children": [
    26
   ],
   "ply": 15,
   "uci": "d1d2",
   "san": "Qd2",
   "mover": "opponent",
   "fen": "rn1qkb1r/1p3ppp/p2pbn2/4p3/4P3/1NN1B3/PPPQ1PPP/R3KB1R b KQkq - 3 8",
   "book": false,
   "name": null,
   "main": false,
   "weight": 0.18,
   "stats": {
    "source": "masters",
    "games": 3770,
    "white": 1185,
    "draws": 1504,
    "black": 1081,
    "average_rating": 2548
   },
   "eval": {
    "cp": 25,
    "mate": null,
    "depth": 14,
    "best_uci": "b8d7"
   },
   "ideas": {
    "structures": [
     "sicilian_d6_e5"
    ],
    "ideas": [
     {
      "key": "sicilian_d6_e5.d5_break",
      "side": "black",
      "params": {
       "pawn": "d6",
       "hole": "d5",
       "e": "e5",
       "san": "d5"
      }
     },
     {
      "key": "sicilian_d6_e5.d5",
      "side": "white",
      "params": {
       "square": "d5",
       "pieces": "Be6,Nf6"
      }
     },
     {
      "key": "pawn_break_now",
      "side": "white",
      "params": {
       "target": "e5",
       "san": "f4"
      }
     },
     {
      "key": "target_backward",
      "side": "white",
      "params": {
       "pawn": "d6"
      }
     },
     {
      "key": "pawn_break_prepare",
      "side": "black",
      "params": {
       "target": "e4",
       "move": "f7–f5"
      }
     },
     {
      "key": "rook_half_open",
      "side": "black",
      "params": {
       "file": "c",
       "target": "c2"
      }
     },
     {
      "key": "majority",
      "side": "white",
      "params": {
       "wing": "queenside",
       "own": "3",
       "other": "2"
      }
     }
    ],
    "breaks": [
     {
      "side": "white",
      "uci": "f2f4",
      "san": "f4",
      "target": "e5",
      "legal_now": true
     },
     {
      "side": "black",
      "uci": "d6d5",
      "san": "d5",
      "target": "e4",
      "legal_now": true
     },
     {
      "side": "black",
      "uci": "f7f5",
      "san": null,
      "target": "e4",
      "legal_now": false
     }
    ],
    "outposts": [
     {
      "side": "white",
      "square": "d5"
     }
    ],
    "weaknesses": [
     {
      "side": "black",
      "square": "d6",
      "kind": "backward"
     },
     {
      "side": "black",
      "square": "d5",
      "kind": "hole"
     }
    ],
    "open_files": [],
    "half_open_files": {
     "white": [
      "d"
     ],
     "black": [
      "c"
     ]
    }
   },
   "key_moment": "book_exit"
  },
  {
   "id": 26,
   "parent": 25,
   "children": [
    27
   ],
   "ply": 16,
   "uci": "b8d7",
   "san": "Nbd7",
   "mover": "learner",
   "fen": "r2qkb1r/1p1n1ppp/p2pbn2/4p3/4P3/1NN1B3/PPPQ1PPP/R3KB1R w KQkq - 4 9",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 2971,
    "white": 983,
    "draws": 1082,
    "black": 906,
    "average_rating": 2476
   },
   "eval": {
    "cp": 22,
    "mate": null,
    "depth": 14,
    "best_uci": "f2f3"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 27,
   "parent": 26,
   "children": [
    28
   ],
   "ply": 17,
   "uci": "f2f3",
   "san": "f3",
   "mover": "opponent",
   "fen": "r2qkb1r/1p1n1ppp/p2pbn2/4p3/4P3/1NN1BP2/PPPQ2PP/R3KB1R b KQkq - 0 9",
   "book": false,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 2971,
    "white": 918,
    "draws": 1218,
    "black": 835,
    "average_rating": 2553
   },
   "eval": {
    "cp": 26,
    "mate": null,
    "depth": 14,
    "best_uci": "h7h5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 28,
   "parent": 27,
   "children": [
    29
   ],
   "ply": 18,
   "uci": "b7b5",
   "san": "b5",
   "mover": "learner",
   "fen": "r2qkb1r/3n1ppp/p2pbn2/1p2p3/4P3/1NN1BP2/PPPQ2PP/R3KB1R w KQkq - 0 10",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 2184,
    "white": 756,
    "draws": 821,
    "black": 607,
    "average_rating": 2545
   },
   "eval": {
    "cp": 60,
    "mate": null,
    "depth": 14,
    "best_uci": "a2a4"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 29,
   "parent": 28,
   "children": [
    30
   ],
   "ply": 19,
   "uci": "g2g4",
   "san": "g4",
   "mover": "opponent",
   "fen": "r2qkb1r/3n1ppp/p2pbn2/1p2p3/4P1P1/1NN1BP2/PPPQ3P/R3KB1R b KQkq - 0 10",
   "book": false,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 2184,
    "white": 631,
    "draws": 947,
    "black": 606,
    "average_rating": 2504
   },
   "eval": {
    "cp": 11,
    "mate": null,
    "depth": 14,
    "best_uci": "b5b4"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 30,
   "parent": 29,
   "children": [],
   "ply": 20,
   "uci": "d7b6",
   "san": "Nb6",
   "mover": "learner",
   "fen": "r2qkb1r/5ppp/pn1pbn2/1p2p3/4P1P1/1NN1BP2/PPPQ3P/R3KB1R w KQkq - 1 11",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 1702,
    "white": 515,
    "draws": 749,
    "black": 438,
    "average_rating": 2491
   },
   "eval": {
    "cp": 44,
    "mate": null,
    "depth": 14,
    "best_uci": "g4g5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 31,
   "parent": 14,
   "children": [
    32
   ],
   "ply": 15,
   "uci": "h2h3",
   "san": "h3",
   "mover": "opponent",
   "fen": "rn1qkb1r/1p3ppp/p2pbn2/4p3/4P3/1NN1B2P/PPP2PP1/R2QKB1R b KQkq - 0 8",
   "book": true,
   "name": "Sicilian Defense: Najdorf Variation, English Attack",
   "main": false,
   "weight": 0.08,
   "stats": {
    "source": "masters",
    "games": 1676,
    "white": 491,
    "draws": 722,
    "black": 463,
    "average_rating": 2535
   },
   "eval": {
    "cp": 16,
    "mate": null,
    "depth": 14,
    "best_uci": "b8d7"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 32,
   "parent": 31,
   "children": [
    33
   ],
   "ply": 16,
   "uci": "f8e7",
   "san": "Be7",
   "mover": "learner",
   "fen": "rn1qk2r/1p2bppp/p2pbn2/4p3/4P3/1NN1B2P/PPP2PP1/R2QKB1R w KQkq - 1 9",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 1196,
    "white": 356,
    "draws": 509,
    "black": 331,
    "average_rating": 2500
   },
   "eval": {
    "cp": 20,
    "mate": null,
    "depth": 14,
    "best_uci": "d1f3"
   },
   "ideas": {
    "structures": [
     "sicilian_d6_e5"
    ],
    "ideas": [
     {
      "key": "sicilian_d6_e5.d5_break",
      "side": "black",
      "params": {
       "pawn": "d6",
       "hole": "d5",
       "e": "e5",
       "san": "d5"
      }
     },
     {
      "key": "sicilian_d6_e5.d5",
      "side": "white",
      "params": {
       "square": "d5",
       "pieces": "Be6,Nf6"
      }
     },
     {
      "key": "pawn_break_now",
      "side": "white",
      "params": {
       "target": "e5",
       "san": "f4"
      }
     },
     {
      "key": "target_backward",
      "side": "white",
      "params": {
       "pawn": "d6"
      }
     },
     {
      "key": "pawn_break_prepare",
      "side": "black",
      "params": {
       "target": "e4",
       "move": "f7–f5"
      }
     },
     {
      "key": "rook_half_open",
      "side": "black",
      "params": {
       "file": "c",
       "target": "c2"
      }
     },
     {
      "key": "majority",
      "side": "white",
      "params": {
       "wing": "queenside",
       "own": "3",
       "other": "2"
      }
     }
    ],
    "breaks": [
     {
      "side": "white",
      "uci": "f2f4",
      "san": "f4",
      "target": "e5",
      "legal_now": true
     },
     {
      "side": "black",
      "uci": "d6d5",
      "san": "d5",
      "target": "e4",
      "legal_now": true
     },
     {
      "side": "black",
      "uci": "f7f5",
      "san": null,
      "target": "e4",
      "legal_now": false
     }
    ],
    "outposts": [
     {
      "side": "white",
      "square": "d5"
     }
    ],
    "weaknesses": [
     {
      "side": "black",
      "square": "d6",
      "kind": "backward"
     },
     {
      "side": "black",
      "square": "d5",
      "kind": "hole"
     }
    ],
    "open_files": [],
    "half_open_files": {
     "white": [
      "d"
     ],
     "black": [
      "c"
     ]
    }
   },
   "key_moment": "book_exit"
  },
  {
   "id": 33,
   "parent": 32,
   "children": [
    34
   ],
   "ply": 17,
   "uci": "g2g4",
   "san": "g4",
   "mover": "opponent",
   "fen": "rn1qk2r/1p2bppp/p2pbn2/4p3/4P1P1/1NN1B2P/PPP2P2/R2QKB1R b KQkq - 0 9",
   "book": false,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 1196,
    "white": 333,
    "draws": 517,
    "black": 346,
    "average_rating": 2494
   },
   "eval": {
    "cp": -10,
    "mate": null,
    "depth": 14,
    "best_uci": "d6d5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 34,
   "parent": 33,
   "children": [],
   "ply": 18,
   "uci": "d6d5",
   "san": "d5",
   "mover": "learner",
   "fen": "rn1qk2r/1p2bppp/p3bn2/3pp3/4P1P1/1NN1B2P/PPP2P2/R2QKB1R w KQkq - 0 10",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 927,
    "white": 292,
    "draws": 338,
    "black": 297,
    "average_rating": 2449
   },
   "eval": {
    "cp": -5,
    "mate": null,
    "depth": 14,
    "best_uci": "e4d5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 35,
   "parent": 12,
   "children": [
    36
   ],
   "ply": 13,
   "uci": "d4f3",
   "san": "Nf3",
   "mover": "opponent",
   "fen": "rnbqkb1r/1p3ppp/p2p1n2/4p3/4P3/2N1BN2/PPP2PPP/R2QKB1R b KQkq - 1 7",
   "book": false,
   "name": null,
   "main": false,
   "weight": 0.19,
   "stats": {
    "source": "masters",
    "games": 7626,
    "white": 2363,
    "draws": 3019,
    "black": 2244,
    "average_rating": 2527
   },
   "eval": {
    "cp": 14,
    "mate": null,
    "depth": 14,
    "best_uci": "f8e7"
   },
   "ideas": {
    "structures": [
     "sicilian_d6_e5"
    ],
    "ideas": [
     {
      "key": "sicilian_d6_e5.d5_break",
      "side": "black",
      "params": {
       "pawn": "d6",
       "hole": "d5",
       "e": "e5",
       "move": "d6–d5"
      }
     },
     {
      "key": "sicilian_d6_e5.d5",
      "side": "white",
      "params": {
       "square": "d5",
       "pieces": "Nf6"
      }
     },
     {
      "key": "target_backward",
      "side": "white",
      "params": {
       "pawn": "d6"
      }
     },
     {
      "key": "pawn_break_prepare",
      "side": "white",
      "params": {
       "target": "e5",
       "move": "f2–f4"
      }
     },
     {
      "key": "pawn_break_prepare",
      "side": "black",
      "params": {
       "target": "e4",
       "move": "f7–f5"
      }
     },
     {
      "key": "rook_half_open",
      "side": "black",
      "params": {
       "file": "c",
       "target": "c2"
      }
     },
     {
      "key": "majority",
      "side": "white",
      "params": {
       "wing": "queenside",
       "own": "3",
       "other": "2"
      }
     }
    ],
    "breaks": [
     {
      "side": "white",
      "uci": "f2f4",
      "san": null,
      "target": "e5",
      "legal_now": false
     },
     {
      "side": "black",
      "uci": "d6d5",
      "san": null,
      "target": "e4",
      "legal_now": false
     },
     {
      "side": "black",
      "uci": "f7f5",
      "san": null,
      "target": "e4",
      "legal_now": false
     }
    ],
    "outposts": [
     {
      "side": "white",
      "square": "d5"
     }
    ],
    "weaknesses": [
     {
      "side": "black",
      "square": "d6",
      "kind": "backward"
     },
     {
      "side": "black",
      "square": "d5",
      "kind": "hole"
     }
    ],
    "open_files": [],
    "half_open_files": {
     "white": [
      "d"
     ],
     "black": [
      "c"
     ]
    }
   },
   "key_moment": "book_exit"
  },
  {
   "id": 36,
   "parent": 35,
   "children": [
    37
   ],
   "ply": 14,
   "uci": "d8c7",
   "san": "Qc7",
   "mover": "learner",
   "fen": "rnb1kb1r/1pq2ppp/p2p1n2/4p3/4P3/2N1BN2/PPP2PPP/R2QKB1R w KQkq - 2 8",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 4978,
    "white": 1630,
    "draws": 1888,
    "black": 1460,
    "average_rating": 2468
   },
   "eval": {
    "cp": 30,
    "mate": null,
    "depth": 14,
    "best_uci": "f1e2"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 37,
   "parent": 36,
   "children": [
    38
   ],
   "ply": 15,
   "uci": "a2a4",
   "san": "a4",
   "mover": "opponent",
   "fen": "rnb1kb1r/1pq2ppp/p2p1n2/4p3/P3P3/2N1BN2/1PP2PPP/R2QKB1R b KQkq - 0 8",
   "book": false,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 4978,
    "white": 1450,
    "draws": 2240,
    "black": 1288,
    "average_rating": 2482
   },
   "eval": {
    "cp": 32,
    "mate": null,
    "depth": 14,
    "best_uci": "f8e7"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 38,
   "parent": 37,
   "children": [
    39
   ],
   "ply": 16,
   "uci": "f8e7",
   "san": "Be7",
   "mover": "learner",
   "fen": "rnb1k2r/1pq1bppp/p2p1n2/4p3/P3P3/2N1BN2/1PP2PPP/R2QKB1R w KQkq - 1 9",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 3148,
    "white": 958,
    "draws": 1336,
    "black": 854,
    "average_rating": 2579
   },
   "eval": {
    "cp": 31,
    "mate": null,
    "depth": 14,
    "best_uci": "a4a5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 39,
   "parent": 38,
   "children": [
    40
   ],
   "ply": 17,
   "uci": "f1e2",
   "san": "Be2",
   "mover": "opponent",
   "fen": "rnb1k2r/1pq1bppp/p2p1n2/4p3/P3P3/2N1BN2/1PP1BPPP/R2QK2R b KQkq - 2 9",
   "book": false,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 3148,
    "white": 952,
    "draws": 1352,
    "black": 844,
    "average_rating": 2552
   },
   "eval": {
    "cp": 33,
    "mate": null,
    "depth": 14,
    "best_uci": "e8g8"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 40,
   "parent": 39,
   "children": [
    41
   ],
   "ply": 18,
   "uci": "e8g8",
   "san": "O-O",
   "mover": "learner",
   "fen": "rnb2rk1/1pq1bppp/p2p1n2/4p3/P3P3/2N1BN2/1PP1BPPP/R2QK2R w KQ - 3 10",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 2419,
    "white": 740,
    "draws": 1027,
    "black": 652,
    "average_rating": 2574
   },
   "eval": {
    "cp": 34,
    "mate": null,
    "depth": 14,
    "best_uci": "a4a5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 41,
   "parent": 40,
   "children": [
    42
   ],
   "ply": 19,
   "uci": "e1g1",
   "san": "O-O",
   "mover": "opponent",
   "fen": "rnb2rk1/1pq1bppp/p2p1n2/4p3/P3P3/2N1BN2/1PP1BPPP/R2Q1RK1 b - - 4 10",
   "book": false,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 2419,
    "white": 818,
    "draws": 872,
    "black": 729,
    "average_rating": 2519
   },
   "eval": {
    "cp": 31,
    "mate": null,
    "depth": 14,
    "best_uci": "c8e6"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 42,
   "parent": 41,
   "children": [],
   "ply": 20,
   "uci": "c8e6",
   "san": "Be6",
   "mover": "learner",
   "fen": "rn3rk1/1pq1bppp/p2pbn2/4p3/P3P3/2N1BN2/1PP1BPPP/R2Q1RK1 w - - 5 11",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 1553,
    "white": 504,
    "draws": 606,
    "black": 443,
    "average_rating": 2508
   },
   "eval": {
    "cp": 35,
    "mate": null,
    "depth": 14,
    "best_uci": "a4a5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 43,
   "parent": 12,
   "children": [
    44
   ],
   "ply": 13,
   "uci": "d4e2",
   "san": "Nde2",
   "mover": "opponent",
   "fen": "rnbqkb1r/1p3ppp/p2p1n2/4p3/4P3/2N1B3/PPP1NPPP/R2QKB1R b KQkq - 1 7",
   "book": false,
   "name": null,
   "main": false,
   "weight": 0.1,
   "stats": {
    "source": "masters",
    "games": 4014,
    "white": 1177,
    "draws": 1672,
    "black": 1165,
    "average_rating": 2459
   },
   "eval": {
    "cp": 3,
    "mate": null,
    "depth": 14,
    "best_uci": "c8e6"
   },
   "ideas": {
    "structures": [
     "sicilian_d6_e5"
    ],
    "ideas": [
     {
      "key": "sicilian_d6_e5.d5_break",
      "side": "black",
      "params": {
       "pawn": "d6",
       "hole": "d5",
       "e": "e5",
       "move": "d6–d5"
      }
     },
     {
      "key": "sicilian_d6_e5.d5",
      "side": "white",
      "params": {
       "square": "d5",
       "pieces": "Nf6"
      }
     },
     {
      "key": "pawn_break_now",
      "side": "white",
      "params": {
       "target": "e5",
       "san": "f4"
      }
     },
     {
      "key": "target_backward",
      "side": "white",
      "params": {
       "pawn": "d6"
      }
     },
     {
      "key": "pawn_break_prepare",
      "side": "black",
      "params": {
       "target": "e4",
       "move": "f7–f5"
      }
     },
     {
      "key": "rook_half_open",
      "side": "black",
      "params": {
       "file": "c",
       "target": "c2"
      }
     },
     {
      "key": "majority",
      "side": "white",
      "params": {
       "wing": "queenside",
       "own": "3",
       "other": "2"
      }
     }
    ],
    "breaks": [
     {
      "side": "white",
      "uci": "f2f4",
      "san": "f4",
      "target": "e5",
      "legal_now": true
     },
     {
      "side": "black",
      "uci": "d6d5",
      "san": null,
      "target": "e4",
      "legal_now": false
     },
     {
      "side": "black",
      "uci": "f7f5",
      "san": null,
      "target": "e4",
      "legal_now": false
     }
    ],
    "outposts": [
     {
      "side": "white",
      "square": "d5"
     }
    ],
    "weaknesses": [
     {
      "side": "black",
      "square": "d6",
      "kind": "backward"
     },
     {
      "side": "black",
      "square": "d5",
      "kind": "hole"
     }
    ],
    "open_files": [],
    "half_open_files": {
     "white": [
      "d"
     ],
     "black": [
      "c"
     ]
    }
   },
   "key_moment": "book_exit"
  },
  {
   "id": 44,
   "parent": 43,
   "children": [
    45
   ],
   "ply": 14,
   "uci": "b8d7",
   "san": "Nbd7",
   "mover": "learner",
   "fen": "r1bqkb1r/1p1n1ppp/p2p1n2/4p3/4P3/2N1B3/PPP1NPPP/R2QKB1R w KQkq - 2 8",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 3167,
    "white": 986,
    "draws": 1305,
    "black": 876,
    "average_rating": 2449
   },
   "eval": {
    "cp": 32,
    "mate": null,
    "depth": 14,
    "best_uci": "a2a4"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 45,
   "parent": 44,
   "children": [
    46
   ],
   "ply": 15,
   "uci": "g2g3",
   "san": "g3",
   "mover": "opponent",
   "fen": "r1bqkb1r/1p1n1ppp/p2p1n2/4p3/4P3/2N1B1P1/PPP1NP1P/R2QKB1R b KQkq - 0 8",
   "book": false,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 3167,
    "white": 994,
    "draws": 1142,
    "black": 1031,
    "average_rating": 2525
   },
   "eval": {
    "cp": -10,
    "mate": null,
    "depth": 14,
    "best_uci": "b7b5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 46,
   "parent": 45,
   "children": [
    47
   ],
   "ply": 16,
   "uci": "b7b5",
   "san": "b5",
   "mover": "learner",
   "fen": "r1bqkb1r/3n1ppp/p2p1n2/1p2p3/4P3/2N1B1P1/PPP1NP1P/R2QKB1R w KQkq - 0 9",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 2052,
    "white": 588,
    "draws": 854,
    "black": 610,
    "average_rating": 2576
   },
   "eval": {
    "cp": -10,
    "mate": null,
    "depth": 14,
    "best_uci": "c3d5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 47,
   "parent": 46,
   "children": [
    48
   ],
   "ply": 17,
   "uci": "f1g2",
   "san": "Bg2",
   "mover": "opponent",
   "fen": "r1bqkb1r/3n1ppp/p2p1n2/1p2p3/4P3/2N1B1P1/PPP1NPBP/R2QK2R b KQkq - 1 9",
   "book": false,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 2052,
    "white": 591,
    "draws": 845,
    "black": 616,
    "average_rating": 2561
   },
   "eval": {
    "cp": -11,
    "mate": null,
    "depth": 14,
    "best_uci": "a8b8"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 48,
   "parent": 47,
   "children": [],
   "ply": 18,
   "uci": "c8b7",
   "san": "Bb7",
   "mover": "learner",
   "fen": "r2qkb1r/1b1n1ppp/p2p1n2/1p2p3/4P3/2N1B1P1/PPP1NPBP/R2QK2R w KQkq - 2 10",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 1355,
    "white": 427,
    "draws": 516,
    "black": 412,
    "average_rating": 2448
   },
   "eval": {
    "cp": 10,
    "mate": null,
    "depth": 14,
    "best_uci": "c3d5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 49,
   "parent": 10,
   "children": [
    50
   ],
   "ply": 11,
   "uci": "c1g5",
   "san": "Bg5",
   "mover": "opponent",
   "fen": "rnbqkb1r/1p2pppp/p2p1n2/6B1/3NP3/2N5/PPP2PPP/R2QKB1R b KQkq - 1 6",
   "book": true,
   "name": "Sicilian Defense: Najdorf Variation",
   "main": false,
   "weight": 0.27,
   "stats": {
    "source": "masters",
    "games": 36463,
    "white": 11427,
    "draws": 14498,
    "black": 10538,
    "average_rating": 2480
   },
   "eval": {
    "cp": 22,
    "mate": null,
    "depth": 14,
    "best_uci": "e7e6"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 50,
   "parent": 49,
   "children": [
    51,
    59
   ],
   "ply": 12,
   "uci": "e7e6",
   "san": "e6",
   "mover": "learner",
   "fen": "rnbqkb1r/1p3ppp/p2ppn2/6B1/3NP3/2N5/PPP2PPP/R2QKB1R w KQkq - 0 7",
   "book": true,
   "name": "Sicilian Defense: Najdorf Variation",
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 27453,
    "white": 8756,
    "draws": 10592,
    "black": 8105,
    "average_rating": 2495
   },
   "eval": {
    "cp": 21,
    "mate": null,
    "depth": 14,
    "best_uci": "f2f4"
   },
   "ideas": {
    "structures": [
     "scheveningen"
    ],
    "ideas": [
     {
      "key": "scheveningen.counter",
      "side": "black",
      "params": {
       "pawns": "d6,e6",
       "san": "d5"
      }
     },
     {
      "key": "scheveningen.attack",
      "side": "white",
      "params": {
       "pawn": "e4",
       "target": "d6",
       "move": "e4–e5"
      }
     },
     {
      "key": "pawn_break_prepare",
      "side": "black",
      "params": {
       "target": "e4",
       "move": "f7–f5"
      }
     },
     {
      "key": "rook_half_open",
      "side": "white",
      "params": {
       "file": "d",
       "target": "d6"
      }
     },
     {
      "key": "rook_half_open",
      "side": "black",
      "params": {
       "file": "c",
       "target": "c2"
      }
     },
     {
      "key": "majority",
      "side": "white",
      "params": {
       "wing": "queenside",
       "own": "3",
       "other": "2"
      }
     }
    ],
    "breaks": [
     {
      "side": "black",
      "uci": "d6d5",
      "san": "d5",
      "target": "e4",
      "legal_now": true
     },
     {
      "side": "white",
      "uci": "e4e5",
      "san": null,
      "target": "d6",
      "legal_now": false
     },
     {
      "side": "black",
      "uci": "f7f5",
      "san": null,
      "target": "e4",
      "legal_now": false
     }
    ],
    "outposts": [],
    "weaknesses": [],
    "open_files": [],
    "half_open_files": {
     "white": [
      "d"
     ],
     "black": [
      "c"
     ]
    }
   },
   "key_moment": "structure"
  },
  {
   "id": 51,
   "parent": 50,
   "children": [
    52
   ],
   "ply": 13,
   "uci": "f2f4",
   "san": "f4",
   "mover": "opponent",
   "fen": "rnbqkb1r/1p3ppp/p2ppn2/6B1/3NPP2/2N5/PPP3PP/R2QKB1R b KQkq - 0 7",
   "book": true,
   "name": "Sicilian Defense: Najdorf Variation",
   "main": false,
   "weight": 0.83,
   "stats": {
    "source": "masters",
    "games": 22786,
    "white": 7100,
    "draws": 8792,
    "black": 6894,
    "average_rating": 2500
   },
   "eval": {
    "cp": 8,
    "mate": null,
    "depth": 14,
    "best_uci": "d8b6"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 52,
   "parent": 51,
   "children": [
    53
   ],
   "ply": 14,
   "uci": "f8e7",
   "san": "Be7",
   "mover": "learner",
   "fen": "rnbqk2r/1p2bppp/p2ppn2/6B1/3NPP2/2N5/PPP3PP/R2QKB1R w KQkq - 1 8",
   "book": true,
   "name": "Sicilian Defense: Najdorf Variation",
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 15586,
    "white": 4982,
    "draws": 5992,
    "black": 4612,
    "average_rating": 2513
   },
   "eval": {
    "cp": 21,
    "mate": null,
    "depth": 14,
    "best_uci": "d1f3"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 53,
   "parent": 52,
   "children": [
    54
   ],
   "ply": 15,
   "uci": "d1f3",
   "san": "Qf3",
   "mover": "opponent",
   "fen": "rnbqk2r/1p2bppp/p2ppn2/6B1/3NPP2/2N2Q2/PPP3PP/R3KB1R b KQkq - 2 8",
   "book": true,
   "name": null,
   "main": false,
   "weight": 0.9,
   "stats": {
    "source": "masters",
    "games": 14027,
    "white": 4404,
    "draws": 5650,
    "black": 3973,
    "average_rating": 2529
   },
   "eval": {
    "cp": 28,
    "mate": null,
    "depth": 14,
    "best_uci": "d8c7"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 54,
   "parent": 53,
   "children": [
    55
   ],
   "ply": 16,
   "uci": "d8c7",
   "san": "Qc7",
   "mover": "learner",
   "fen": "rnb1k2r/1pq1bppp/p2ppn2/6B1/3NPP2/2N2Q2/PPP3PP/R3KB1R w KQkq - 3 9",
   "book": true,
   "name": "Sicilian Defense: Najdorf Variation, Traditional Line",
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 9771,
    "white": 3125,
    "draws": 3827,
    "black": 2819,
    "average_rating": 2557
   },
   "eval": {
    "cp": 28,
    "mate": null,
    "depth": 14,
    "best_uci": "e1c1"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 55,
   "parent": 54,
   "children": [
    56
   ],
   "ply": 17,
   "uci": "e1c1",
   "san": "O-O-O",
   "mover": "opponent",
   "fen": "rnb1k2r/1pq1bppp/p2ppn2/6B1/3NPP2/2N2Q2/PPP3PP/2KR1B1R b kq - 4 9",
   "book": true,
   "name": null,
   "main": false,
   "weight": 0.95,
   "stats": {
    "source": "masters",
    "games": 9282,
    "white": 3081,
    "draws": 3422,
    "black": 2779,
    "average_rating": 2451
   },
   "eval": {
    "cp": 28,
    "mate": null,
    "depth": 14,
    "best_uci": "b8d7"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 56,
   "parent": 55,
   "children": [
    57
   ],
   "ply": 18,
   "uci": "b8d7",
   "san": "Nbd7",
   "mover": "learner",
   "fen": "r1b1k2r/1pqnbppp/p2ppn2/6B1/3NPP2/2N2Q2/PPP3PP/2KR1B1R w kq - 5 10",
   "book": true,
   "name": "Sicilian Defense: Najdorf Variation, Main Line",
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 6757,
    "white": 2272,
    "draws": 2435,
    "black": 2050,
    "average_rating": 2518
   },
   "eval": {
    "cp": 28,
    "mate": null,
    "depth": 14,
    "best_uci": "f1d3"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 57,
   "parent": 56,
   "children": [
    58
   ],
   "ply": 19,
   "uci": "g2g4",
   "san": "g4",
   "mover": "opponent",
   "fen": "r1b1k2r/1pqnbppp/p2ppn2/6B1/3NPPP1/2N2Q2/PPP4P/2KR1B1R b kq - 0 10",
   "book": false,
   "name": null,
   "main": false,
   "weight": 0.8,
   "stats": {
    "source": "masters",
    "games": 5406,
    "white": 1790,
    "draws": 2049,
    "black": 1567,
    "average_rating": 2563
   },
   "eval": {
    "cp": 36,
    "mate": null,
    "depth": 14,
    "best_uci": "h7h6"
   },
   "ideas": {
    "structures": [
     "scheveningen"
    ],
    "ideas": [
     {
      "key": "scheveningen.counter",
      "side": "black",
      "params": {
       "pawns": "d6,e6",
       "move": "d6–d5"
      }
     },
     {
      "key": "scheveningen.attack",
      "side": "white",
      "params": {
       "pawn": "e4",
       "target": "d6",
       "move": "e4–e5"
      }
     },
     {
      "key": "pawn_break_now",
      "side": "white",
      "params": {
       "target": "e6",
       "san": "f5"
      }
     },
     {
      "key": "pawn_break_now",
      "side": "black",
      "params": {
       "target": "f4",
       "san": "e5"
      }
     },
     {
      "key": "rook_half_open",
      "side": "white",
      "params": {
       "file": "d",
       "target": "d6"
      }
     },
     {
      "key": "rook_half_open",
      "side": "black",
      "params": {
       "file": "c",
       "target": "c2"
      }
     },
     {
      "key": "majority",
      "side": "white",
      "params": {
       "wing": "queenside",
       "own": "3",
       "other": "2"
      }
     }
    ],
    "breaks": [
     {
      "side": "white",
      "uci": "f4f5",
      "san": "f5",
      "target": "e6",
      "legal_now": true
     },
     {
      "side": "black",
      "uci": "e6e5",
      "san": "e5",
      "target": "f4",
      "legal_now": true
     },
     {
      "side": "black",
      "uci": "h7h5",
      "san": "h5",
      "target": "g4",
      "legal_now": true
     },
     {
      "side": "white",
      "uci": "e4e5",
      "san": null,
      "target": "d6",
      "legal_now": false
     },
     {
      "side": "black",
      "uci": "d6d5",
      "san": null,
      "target": "e4",
      "legal_now": false
     }
    ],
    "outposts": [],
    "weaknesses": [
     {
      "side": "white",
      "square": "e3",
      "kind": "hole"
     },
     {
      "side": "white",
      "square": "f3",
      "kind": "hole"
     }
    ],
    "open_files": [],
    "half_open_files": {
     "white": [
      "d"
     ],
     "black": [
      "c"
     ]
    }
   },
   "key_moment": "book_exit"
  },
  {
   "id": 58,
   "parent": 57,
   "children": [],
   "ply": 20,
   "uci": "b7b5",
   "san": "b5",
   "mover": "learner",
   "fen": "r1b1k2r/2qnbppp/p2ppn2/1p4B1/3NPPP1/2N2Q2/PPP4P/2KR1B1R w kq - 0 11",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 4317,
    "white": 1447,
    "draws": 1722,
    "black": 1148,
    "average_rating": 2455
   },
   "eval": {
    "cp": 63,
    "mate": null,
    "depth": 14,
    "best_uci": "g5f6"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 59,
   "parent": 50,
   "children": [
    60
   ],
   "ply": 13,
   "uci": "d1f3",
   "san": "Qf3",
   "mover": "opponent",
   "fen": "rnbqkb1r/1p3ppp/p2ppn2/6B1/3NP3/2N2Q2/PPP2PPP/R3KB1R b KQkq - 1 7",
   "book": false,
   "name": null,
   "main": false,
   "weight": 0.17,
   "stats": {
    "source": "masters",
    "games": 4667,
    "white": 1452,
    "draws": 1815,
    "black": 1400,
    "average_rating": 2551
   },
   "eval": {
    "cp": 10,
    "mate": null,
    "depth": 14,
    "best_uci": "h7h6"
   },
   "ideas": {
    "structures": [
     "scheveningen"
    ],
    "ideas": [
     {
      "key": "scheveningen.counter",
      "side": "black",
      "params": {
       "pawns": "d6,e6",
       "san": "d5"
      }
     },
     {
      "key": "scheveningen.attack",
      "side": "white",
      "params": {
       "pawn": "e4",
       "target": "d6",
       "move": "e4–e5"
      }
     },
     {
      "key": "pawn_break_prepare",
      "side": "black",
      "params": {
       "target": "e4",
       "move": "f7–f5"
      }
     },
     {
      "key": "rook_half_open",
      "side": "white",
      "params": {
       "file": "d",
       "target": "d6"
      }
     },
     {
      "key": "rook_half_open",
      "side": "black",
      "params": {
       "file": "c",
       "target": "c2"
      }
     },
     {
      "key": "majority",
      "side": "white",
      "params": {
       "wing": "queenside",
       "own": "3",
       "other": "2"
      }
     }
    ],
    "breaks": [
     {
      "side": "black",
      "uci": "d6d5",
      "san": "d5",
      "target": "e4",
      "legal_now": true
     },
     {
      "side": "white",
      "uci": "e4e5",
      "san": null,
      "target": "d6",
      "legal_now": false
     },
     {
      "side": "black",
      "uci": "f7f5",
      "san": null,
      "target": "e4",
      "legal_now": false
     }
    ],
    "outposts": [],
    "weaknesses": [],
    "open_files": [],
    "half_open_files": {
     "white": [
      "d"
     ],
     "black": [
      "c"
     ]
    }
   },
   "key_moment": "book_exit"
  },
  {
   "id": 60,
   "parent": 59,
   "children": [
    61
   ],
   "ply": 14,
   "uci": "h7h6",
   "san": "h6",
   "mover": "learner",
   "fen": "rnbqkb1r/1p3pp1/p2ppn1p/6B1/3NP3/2N2Q2/PPP2PPP/R3KB1R w KQkq - 0 8",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 3693,
    "white": 1167,
    "draws": 1384,
    "black": 1142,
    "average_rating": 2453
   },
   "eval": {
    "cp": 6,
    "mate": null,
    "depth": 14,
    "best_uci": "g5e3"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 61,
   "parent": 60,
   "children": [
    62
   ],
   "ply": 15,
   "uci": "g5h4",
   "san": "Bh4",
   "mover": "opponent",
   "fen": "rnbqkb1r/1p3pp1/p2ppn1p/8/3NP2B/2N2Q2/PPP2PPP/R3KB1R b KQkq - 1 8",
   "book": false,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 3693,
    "white": 1123,
    "draws": 1371,
    "black": 1199,
    "average_rating": 2480
   },
   "eval": {
    "cp": -18,
    "mate": null,
    "depth": 14,
    "best_uci": "f8e7"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 62,
   "parent": 61,
   "children": [
    63
   ],
   "ply": 16,
   "uci": "b8d7",
   "san": "Nbd7",
   "mover": "learner",
   "fen": "r1bqkb1r/1p1n1pp1/p2ppn1p/8/3NP2B/2N2Q2/PPP2PPP/R3KB1R w KQkq - 2 9",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 2435,
    "white": 740,
    "draws": 950,
    "black": 745,
    "average_rating": 2539
   },
   "eval": {
    "cp": -2,
    "mate": null,
    "depth": 14,
    "best_uci": "f1e2"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 63,
   "parent": 62,
   "children": [
    64
   ],
   "ply": 17,
   "uci": "e1c1",
   "san": "O-O-O",
   "mover": "opponent",
   "fen": "r1bqkb1r/1p1n1pp1/p2ppn1p/8/3NP2B/2N2Q2/PPP2PPP/2KR1B1R b kq - 3 9",
   "book": false,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 2435,
    "white": 737,
    "draws": 947,
    "black": 751,
    "average_rating": 2528
   },
   "eval": {
    "cp": -5,
    "mate": null,
    "depth": 14,
    "best_uci": "d8c7"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 64,
   "parent": 63,
   "children": [],
   "ply": 18,
   "uci": "d8c7",
   "san": "Qc7",
   "mover": "learner",
   "fen": "r1b1kb1r/1pqn1pp1/p2ppn1p/8/3NP2B/2N2Q2/PPP2PPP/2KR1B1R w kq - 4 10",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 1566,
    "white": 460,
    "draws": 620,
    "black": 486,
    "average_rating": 2553
   },
   "eval": {
    "cp": -15,
    "mate": null,
    "depth": 14,
    "best_uci": "f1d3"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 65,
   "parent": 10,
   "children": [
    66
   ],
   "ply": 11,
   "uci": "h2h3",
   "san": "h3",
   "mover": "opponent",
   "fen": "rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N4P/PPP2PP1/R1BQKB1R b KQkq - 0 6",
   "book": true,
   "name": "Sicilian Defense: Najdorf Variation, Adams Attack",
   "main": false,
   "weight": 0.16,
   "stats": {
    "source": "masters",
    "games": 21608,
    "white": 6491,
    "draws": 9043,
    "black": 6074,
    "average_rating": 2551
   },
   "eval": {
    "cp": 18,
    "mate": null,
    "depth": 14,
    "best_uci": "e7e5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 66,
   "parent": 65,
   "children": [
    67
   ],
   "ply": 12,
   "uci": "e7e5",
   "san": "e5",
   "mover": "learner",
   "fen": "rnbqkb1r/1p3ppp/p2p1n2/4p3/3NP3/2N4P/PPP2PP1/R1BQKB1R w KQkq - 0 7",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 13566,
    "white": 4183,
    "draws": 5610,
    "black": 3773,
    "average_rating": 2473
   },
   "eval": {
    "cp": 28,
    "mate": null,
    "depth": 14,
    "best_uci": "d4e2"
   },
   "ideas": {
    "structures": [
     "sicilian_d6_e5"
    ],
    "ideas": [
     {
      "key": "sicilian_d6_e5.d5_break",
      "side": "black",
      "params": {
       "pawn": "d6",
       "hole": "d5",
       "e": "e5",
       "san": "d5"
      }
     },
     {
      "key": "sicilian_d6_e5.d5",
      "side": "white",
      "params": {
       "square": "d5",
       "pieces": "Nf6"
      }
     },
     {
      "key": "pawn_break_now",
      "side": "white",
      "params": {
       "target": "e5",
       "san": "f4"
      }
     },
     {
      "key": "target_backward",
      "side": "white",
      "params": {
       "pawn": "d6"
      }
     },
     {
      "key": "pawn_break_prepare",
      "side": "black",
      "params": {
       "target": "e4",
       "move": "f7–f5"
      }
     },
     {
      "key": "rook_half_open",
      "side": "black",
      "params": {
       "file": "c",
       "target": "c2"
      }
     },
     {
      "key": "majority",
      "side": "white",
      "params": {
       "wing": "queenside",
       "own": "3",
       "other": "2"
      }
     }
    ],
    "breaks": [
     {
      "side": "white",
      "uci": "f2f4",
      "san": "f4",
      "target": "e5",
      "legal_now": true
     },
     {
      "side": "black",
      "uci": "d6d5",
      "san": "d5",
      "target": "e4",
      "legal_now": true
     },
     {
      "side": "black",
      "uci": "f7f5",
      "san": null,
      "target": "e4",
      "legal_now": false
     }
    ],
    "outposts": [
     {
      "side": "white",
      "square": "d5"
     }
    ],
    "weaknesses": [
     {
      "side": "black",
      "square": "d6",
      "kind": "backward"
     },
     {
      "side": "black",
      "square": "d5",
      "kind": "hole"
     }
    ],
    "open_files": [],
    "half_open_files": {
     "white": [
      "d"
     ],
     "black": [
      "c"
     ]
    }
   },
   "key_moment": "book_exit"
  },
  {
   "id": 67,
   "parent": 66,
   "children": [
    68
   ],
   "ply": 13,
   "uci": "d4e2",
   "san": "Nde2",
   "mover": "opponent",
   "fen": "rnbqkb1r/1p3ppp/p2p1n2/4p3/4P3/2N4P/PPP1NPP1/R1BQKB1R b KQkq - 1 7",
   "book": false,
   "name": null,
   "main": false,
   "weight": 0.78,
   "stats": {
    "source": "masters",
    "games": 10581,
    "white": 3001,
    "draws": 4833,
    "black": 2747,
    "average_rating": 2452
   },
   "eval": {
    "cp": 24,
    "mate": null,
    "depth": 14,
    "best_uci": "h7h5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 68,
   "parent": 67,
   "children": [
    69
   ],
   "ply": 14,
   "uci": "h7h5",
   "san": "h5",
   "mover": "learner",
   "fen": "rnbqkb1r/1p3pp1/p2p1n2/4p2p/4P3/2N4P/PPP1NPP1/R1BQKB1R w KQkq - 0 8",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 7175,
    "white": 2059,
    "draws": 3224,
    "black": 1892,
    "average_rating": 2579
   },
   "eval": {
    "cp": 23,
    "mate": null,
    "depth": 14,
    "best_uci": "g2g3"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 69,
   "parent": 68,
   "children": [
    70
   ],
   "ply": 15,
   "uci": "g2g3",
   "san": "g3",
   "mover": "opponent",
   "fen": "rnbqkb1r/1p3pp1/p2p1n2/4p2p/4P3/2N3PP/PPP1NP2/R1BQKB1R b KQkq - 0 8",
   "book": false,
   "name": null,
   "main": false,
   "weight": 0.92,
   "stats": {
    "source": "masters",
    "games": 6601,
    "white": 1947,
    "draws": 2865,
    "black": 1789,
    "average_rating": 2441
   },
   "eval": {
    "cp": 23,
    "mate": null,
    "depth": 14,
    "best_uci": "c8e6"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 70,
   "parent": 69,
   "children": [
    71
   ],
   "ply": 16,
   "uci": "b7b5",
   "san": "b5",
   "mover": "learner",
   "fen": "rnbqkb1r/5pp1/p2p1n2/1p2p2p/4P3/2N3PP/PPP1NP2/R1BQKB1R w KQkq - 0 9",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 5155,
    "white": 1503,
    "draws": 2326,
    "black": 1326,
    "average_rating": 2478
   },
   "eval": {
    "cp": 34,
    "mate": null,
    "depth": 14,
    "best_uci": "c3d5"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 71,
   "parent": 70,
   "children": [
    72
   ],
   "ply": 17,
   "uci": "f1g2",
   "san": "Bg2",
   "mover": "opponent",
   "fen": "rnbqkb1r/5pp1/p2p1n2/1p2p2p/4P3/2N3PP/PPP1NPB1/R1BQK2R b KQkq - 1 9",
   "book": false,
   "name": null,
   "main": false,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 5155,
    "white": 1588,
    "draws": 1902,
    "black": 1665,
    "average_rating": 2535
   },
   "eval": {
    "cp": -13,
    "mate": null,
    "depth": 14,
    "best_uci": "b8d7"
   },
   "ideas": null,
   "key_moment": null
  },
  {
   "id": 72,
   "parent": 71,
   "children": [],
   "ply": 18,
   "uci": "b8d7",
   "san": "Nbd7",
   "mover": "learner",
   "fen": "r1bqkb1r/3n1pp1/p2p1n2/1p2p2p/4P3/2N3PP/PPP1NPB1/R1BQK2R w KQkq - 2 10",
   "book": false,
   "name": null,
   "main": true,
   "weight": 1.0,
   "stats": {
    "source": "masters",
    "games": 3261,
    "white": 1006,
    "draws": 1260,
    "black": 995,
    "average_rating": 2494
   },
   "eval": {
    "cp": 3,
    "mate": null,
    "depth": 14,
    "best_uci": "c1e3"
   },
   "ideas": null,
   "key_moment": null
  }
 ],
 "model_games": [
  {
   "id": "fx01",
   "node_id": 12,
   "white": "Varga, Z.",
   "black": "Kowalczyk, D.",
   "white_rating": 2600,
   "black_rating": 2579,
   "year": 2018,
   "result": "1/2-1/2",
   "pgn": "[Event \"Fixture Open\"]\n[Site \"?\"]\n[Date \"2018.??.??\"]\n[White \"Varga, Z.\"]\n[Black \"Kowalczyk, D.\"]\n[Result \"1/2-1/2\"]\n[WhiteElo \"2600\"]\n[BlackElo \"2579\"]\n\n1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Be3 e5 7. Nb3 Be7 8. f3 Be6 9. Nd5 Nxd5 10. exd5 Bf5 11. Be2 Nd7 12. Qd2 Qc7 13. Rc1 Bh4+ 14. g3 Be7 15. Na5 Bh3 16. Rg1 O-O 17. b4 h5 18. c4 e4 19. fxe4 Rfe8 20. Kf2 Bd8 21. Bf3 Nf6 22. Qd3 Qd7 23. Rge1 Ng4+ 24. Bxg4 1/2-1/2"
  },
  {
   "id": "fx02",
   "node_id": 16,
   "white": "Lindqvist, O.",
   "black": "Rahimov, A.",
   "white_rating": 2519,
   "black_rating": 2646,
   "year": 2021,
   "result": "1-0",
   "pgn": "[Event \"Fixture Open\"]\n[Site \"?\"]\n[Date \"2021.??.??\"]\n[White \"Lindqvist, O.\"]\n[Black \"Rahimov, A.\"]\n[Result \"1-0\"]\n[WhiteElo \"2519\"]\n[BlackElo \"2646\"]\n\n1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Be3 e5 7. Nb3 Be6 8. f3 Be7 9. Qd2 Nbd7 10. g4 b5 11. g5 b4 12. Ne2 Ng8 13. Rg1 a5 14. O-O-O a4 15. Na1 Bxa2 16. Ng3 g6 17. b3 axb3 18. cxb3 Rc8+ 19. Kb2 f5 20. Qd5 Bxb3 21. Nxb3 f4 22. Bb5 fxe3 23. Qe6 Rb8 24. Bc6 Qc7 25. Ba4 h6 26. Bxd7+ Qxd7 27. Qxg6+ Kd8 28. Nc5 Qc6 29. Ne6+ Kd7 1-0"
  },
  {
   "id": "fx03",
   "node_id": 24,
   "white": "Moreau, T.",
   "black": "Fontaine, L.",
   "white_rating": 2678,
   "black_rating": 2598,
   "year": 2012,
   "result": "0-1",
   "pgn": "[Event \"Fixture Open\"]\n[Site \"?\"]\n[Date \"2012.??.??\"]\n[White \"Moreau, T.\"]\n[Black \"Fontaine, L.\"]\n[Result \"0-1\"]\n[WhiteElo \"2678\"]\n[BlackElo \"2598\"]\n\n1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Be3 e5 7. Nb3 Be6 8. f3 Be7 9. Qd2 O-O 10. O-O-O Nbd7 11. g4 b5 12. g5 b4 13. Ne2 Nh5 14. Ng3 Nf4 15. h4 a5 16. Nd4 exd4 17. Bxf4 a4 18. Kb1 b3 19. Nf5 Bxf5 20. axb3 axb3 21. cxb3 Be6 22. Bc4 Bxc4 23. bxc4 Nc5 24. Kc2 d3+ 25. Kb1 Ra4 26. Qxd3 Nxd3 27. Rxd3 Qa8 28. Rdd1 d5 29. Be5 Ra1+ 30. Kc2 0-1"
  },
  {
   "id": "fx04",
   "node_id": 25,
   "white": "Okafor, E.",
   "black": "Brandt, S.",
   "white_rating": 2706,
   "black_rating": 2525,
   "year": 2021,
   "result": "0-1",
   "pgn": "[Event \"Fixture Open\"]\n[Site \"?\"]\n[Date \"2021.??.??\"]\n[White \"Okafor, E.\"]\n[Black \"Brandt, S.\"]\n[Result \"0-1\"]\n[WhiteElo \"2706\"]\n[BlackElo \"2525\"]\n\n1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Be3 e5 7. Nb3 Be6 8. Qd2 Nbd7 9. f3 h5 10. Nd5 Bxd5 11. O-O-O Be6 12. Be2 Be7 13. a3 a5 14. a4 Rc8 15. Nxa5 d5 16. exd5 Bxd5 17. g3 Qc7 18. Qc3 Bb4 19. Bb6 Nxb6 20. Qxc7 Rxc7 21. f4 Bxh1 22. Nxb7 Bd5 23. fxe5 Rxb7 24. exf6 gxf6 25. Bb5+ Kf8 26. h4 Be1 27. b3 Bc3 28. Rd3 Bb4 29. a5 Kg7 30. Ba6 Re7 0-1"
  },
  {
   "id": "fx05",
   "node_id": 30,
   "white": "Sandoval, R.",
   "black": "Petrescu, M.",
   "white_rating": 2660,
   "black_rating": 2480,
   "year": 2014,
   "result": "1-0",
   "pgn": "[Event \"Fixture Open\"]\n[Site \"?\"]\n[Date \"2014.??.??\"]\n[White \"Sandoval, R.\"]\n[Black \"Petrescu, M.\"]\n[Result \"1-0\"]\n[WhiteElo \"2660\"]\n[BlackElo \"2480\"]\n\n1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Be3 e5 7. Nb3 Be6 8. Qd2 Nbd7 9. f3 b5 10. g4 Nb6 11. g5 Nh5 12. Na5 b4 13. Nd5 Nxd5 14. exd5 Qxa5 15. dxe6 fxe6 16. O-O-O Be7 17. Kb1 g6 18. Bh3 Ng7 19. Bg4 Nf5 20. f4 Qb5 21. h4 Rc8 22. h5 Rg8 23. fxe5 dxe5 24. hxg6 hxg6 25. Rde1 Kf7 26. Rh7+ Rg7 27. Qh2 Bf8 28. Rh3 Bd6 29. Bc1 Qc6 30. Qd2 a5 31. b3 Rgg8 32. Rh7+ Rg7 33. Rhh1 e4 34. Bb2 1-0"
  },
  {
   "id": "fx06",
   "node_id": 32,
   "white": "Haugen, K.",
   "black": "Ibarra, J.",
   "white_rating": 2520,
   "black_rating": 2592,
   "year": 2021,
   "result": "1-0",
   "pgn": "[Event \"Fixture Open\"]\n[Site \"?\"]\n[Date \"2021.??.??\"]\n[White \"Haugen, K.\"]\n[Black \"Ibarra, J.\"]\n[Result \"1-0\"]\n[WhiteElo \"2520\"]\n[BlackElo \"2592\"]\n\n1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Be3 e5 7. Nb3 Be6 8. h3 Be7 9. Qf3 Nc6 10. g4 d5 11. exd5 Bxd5 12. Nxd5 Qxd5 13. Bg2 Qxf3 14. Bxf3 O-O-O 15. Bd2 Nd5 16. O-O-O Bh4 17. Ba5 Nxa5 18. Nxa5 Nb6 19. Bxb7+ Kc7 20. Kb1 Rxd1+ 21. Rxd1 g6 22. c3 h5 23. f3 hxg4 24. hxg4 Bg3 25. Kc2 f5 26. Rd2 Bf4 27. Re2 Rh3 28. gxf5 gxf5 29. Rg2 Nd7 30. Bd5 Nf6 31. Rg7+ Kd6 32. Bc4 e4 33. Rf7 Bg5 1-0"
  },
  {
   "id": "fx07",
   "node_id": 34,
   "white": "Varga, Z.",
   "black": "Kowalczyk, D.",
   "white_rating": 2519,
   "black_rating": 2683,
   "year": 2014,
   "result": "0-1",
   "pgn": "[Event \"Fixture Open\"]\n[Site \"?\"]\n[Date \"2014.??.??\"]\n[White \"Varga, Z.\"]\n[Black \"Kowalczyk, D.\"]\n[Result \"0-1\"]\n[WhiteElo \"2519\"]\n[BlackElo \"2683\"]\n\n1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Be3 e5 7. Nb3 Be6 8. h3 Be7 9. g4 d5 10. exd5 Nxd5 11. Nxd5 Qxd5 12. Rg1 Qc6 13. Bg2 Qc7 14. Bd5 O-O 15. Bxe6 fxe6 16. Qe2 a5 17. a3 a4 18. Nc1 Nc6 19. Na2 Rad8 20. Nc3 Bh4 21. Qc4 Rf3 22. Qe4 Qf7 23. Rg2 Rxh3 24. Rd1 Rh1+ 25. Rg1 Rxd1+ 26. Kxd1 Qd7+ 27. Ke1 Rxg1+ 28. Ke2 Nd4+ 29. Bxd4 Qxd4 0-1"
  }
 ]
};

export const najdorfIdeas: Record<"ru" | "en", Record<string, RenderedIdeas>> = {
 "ru": {
  "10": {
   "structures": [],
   "structure_title": null,
   "structure_summary": null,
   "ideas": [
    {
     "key": "pawn_break_now",
     "side": "black",
     "text": "Пешечный прорыв …d5 — удар по пешке e4."
    },
    {
     "key": "pawn_break_prepare",
     "side": "white",
     "text": "Готовьте прорыв e4–e5 против пешки d6."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Готовьте прорыв f7–f5 против пешки e4."
    },
    {
     "key": "rook_half_open",
     "side": "white",
     "text": "Полуоткрытая линия d: давите ладьёй на пешку d6."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Полуоткрытая линия c: давите ладьёй на пешку c2."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Большинство на ферзевом фланге (3 против 2): в эндшпиле оно даёт проходную."
    }
   ]
  },
  "12": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Структура Найдорфа / Свешникова",
   "structure_summary": "Пешка e5 даёт чёрным пространство и активную игру, но поле d5 пешкой уже не защитить, а пешка d6 — отсталая. Белые борются за поле d5; чёрные готовят прорыв …d5 и контригру на ферзевом фланге.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "Прорыв …d5 убирает отсталую пешку d6 и снимает проблемы; до тех пор контригра — на ферзевом фланге и по линии c."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "Поле d5 — главный пункт: ставьте туда фигуры и разменивайте его защитников (конь f6)."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "Пешечный прорыв f4 — удар по пешке e5."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Давите на отсталую пешку d6: пешкой её не защитить, а поле перед ней — ваше."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Готовьте прорыв f7–f5 против пешки e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Полуоткрытая линия c: давите ладьёй на пешку c2."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Большинство на ферзевом фланге (3 против 2): в эндшпиле оно даёт проходную."
    }
   ]
  },
  "16": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Структура Найдорфа / Свешникова",
   "structure_summary": "Пешка e5 даёт чёрным пространство и активную игру, но поле d5 пешкой уже не защитить, а пешка d6 — отсталая. Белые борются за поле d5; чёрные готовят прорыв …d5 и контригру на ферзевом фланге.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "Прорыв …d5 убирает отсталую пешку d6 и снимает проблемы; до тех пор контригра — на ферзевом фланге и по линии c."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "Поле d5 — главный пункт: ставьте туда фигуры и разменивайте его защитников (слон e6, конь f6)."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "Пешечный прорыв f4 — удар по пешке e5."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Давите на отсталую пешку d6: пешкой её не защитить, а поле перед ней — ваше."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Готовьте прорыв f7–f5 против пешки e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Полуоткрытая линия c: давите ладьёй на пешку c2."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Большинство на ферзевом фланге (3 против 2): в эндшпиле оно даёт проходную."
    }
   ]
  },
  "25": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Структура Найдорфа / Свешникова",
   "structure_summary": "Пешка e5 даёт чёрным пространство и активную игру, но поле d5 пешкой уже не защитить, а пешка d6 — отсталая. Белые борются за поле d5; чёрные готовят прорыв …d5 и контригру на ферзевом фланге.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "Прорыв …d5 убирает отсталую пешку d6 и снимает проблемы; до тех пор контригра — на ферзевом фланге и по линии c."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "Поле d5 — главный пункт: ставьте туда фигуры и разменивайте его защитников (слон e6, конь f6)."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "Пешечный прорыв f4 — удар по пешке e5."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Давите на отсталую пешку d6: пешкой её не защитить, а поле перед ней — ваше."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Готовьте прорыв f7–f5 против пешки e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Полуоткрытая линия c: давите ладьёй на пешку c2."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Большинство на ферзевом фланге (3 против 2): в эндшпиле оно даёт проходную."
    }
   ]
  },
  "32": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Структура Найдорфа / Свешникова",
   "structure_summary": "Пешка e5 даёт чёрным пространство и активную игру, но поле d5 пешкой уже не защитить, а пешка d6 — отсталая. Белые борются за поле d5; чёрные готовят прорыв …d5 и контригру на ферзевом фланге.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "Прорыв …d5 убирает отсталую пешку d6 и снимает проблемы; до тех пор контригра — на ферзевом фланге и по линии c."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "Поле d5 — главный пункт: ставьте туда фигуры и разменивайте его защитников (слон e6, конь f6)."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "Пешечный прорыв f4 — удар по пешке e5."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Давите на отсталую пешку d6: пешкой её не защитить, а поле перед ней — ваше."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Готовьте прорыв f7–f5 против пешки e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Полуоткрытая линия c: давите ладьёй на пешку c2."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Большинство на ферзевом фланге (3 против 2): в эндшпиле оно даёт проходную."
    }
   ]
  },
  "35": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Структура Найдорфа / Свешникова",
   "structure_summary": "Пешка e5 даёт чёрным пространство и активную игру, но поле d5 пешкой уже не защитить, а пешка d6 — отсталая. Белые борются за поле d5; чёрные готовят прорыв d6–d5 и контригру на ферзевом фланге.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "Прорыв d6–d5 убирает отсталую пешку d6 и снимает проблемы; до тех пор контригра — на ферзевом фланге и по линии c."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "Поле d5 — главный пункт: ставьте туда фигуры и разменивайте его защитников (конь f6)."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Давите на отсталую пешку d6: пешкой её не защитить, а поле перед ней — ваше."
    },
    {
     "key": "pawn_break_prepare",
     "side": "white",
     "text": "Готовьте прорыв f2–f4 против пешки e5."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Готовьте прорыв f7–f5 против пешки e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Полуоткрытая линия c: давите ладьёй на пешку c2."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Большинство на ферзевом фланге (3 против 2): в эндшпиле оно даёт проходную."
    }
   ]
  },
  "43": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Структура Найдорфа / Свешникова",
   "structure_summary": "Пешка e5 даёт чёрным пространство и активную игру, но поле d5 пешкой уже не защитить, а пешка d6 — отсталая. Белые борются за поле d5; чёрные готовят прорыв d6–d5 и контригру на ферзевом фланге.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "Прорыв d6–d5 убирает отсталую пешку d6 и снимает проблемы; до тех пор контригра — на ферзевом фланге и по линии c."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "Поле d5 — главный пункт: ставьте туда фигуры и разменивайте его защитников (конь f6)."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "Пешечный прорыв f4 — удар по пешке e5."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Давите на отсталую пешку d6: пешкой её не защитить, а поле перед ней — ваше."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Готовьте прорыв f7–f5 против пешки e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Полуоткрытая линия c: давите ладьёй на пешку c2."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Большинство на ферзевом фланге (3 против 2): в эндшпиле оно даёт проходную."
    }
   ]
  },
  "50": {
   "structures": [
    "scheveningen"
   ],
   "structure_title": "Сицилианская: малый центр (Шевенинген)",
   "structure_summary": "Пешки d6 и e6 — прочный «малый центр» чёрных, за ним фигуры перестраиваются без спешки. Белые владеют пространством и атакуют на королевском фланге; чёрные отвечают контригрой на ферзевом фланге и по линии c и ждут момента для прорыва …d5.",
   "ideas": [
    {
     "key": "scheveningen.counter",
     "side": "black",
     "text": "Контригра — на ферзевом фланге и по полуоткрытой линии c; освобождающий прорыв …d5 готовьте фигурами."
    },
    {
     "key": "scheveningen.attack",
     "side": "white",
     "text": "Используйте пространство: пешечная атака на королевском фланге и прорыв e4–e5 против пешки d6."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Готовьте прорыв f7–f5 против пешки e4."
    },
    {
     "key": "rook_half_open",
     "side": "white",
     "text": "Полуоткрытая линия d: давите ладьёй на пешку d6."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Полуоткрытая линия c: давите ладьёй на пешку c2."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Большинство на ферзевом фланге (3 против 2): в эндшпиле оно даёт проходную."
    }
   ]
  },
  "57": {
   "structures": [
    "scheveningen"
   ],
   "structure_title": "Сицилианская: малый центр (Шевенинген)",
   "structure_summary": "Пешки d6 и e6 — прочный «малый центр» чёрных, за ним фигуры перестраиваются без спешки. Белые владеют пространством и атакуют на королевском фланге; чёрные отвечают контригрой на ферзевом фланге и по линии c и ждут момента для прорыва d6–d5.",
   "ideas": [
    {
     "key": "scheveningen.counter",
     "side": "black",
     "text": "Контригра — на ферзевом фланге и по полуоткрытой линии c; освобождающий прорыв d6–d5 готовьте фигурами."
    },
    {
     "key": "scheveningen.attack",
     "side": "white",
     "text": "Используйте пространство: пешечная атака на королевском фланге и прорыв e4–e5 против пешки d6."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "Пешечный прорыв f5 — удар по пешке e6."
    },
    {
     "key": "pawn_break_now",
     "side": "black",
     "text": "Пешечный прорыв …e5 — удар по пешке f4."
    },
    {
     "key": "rook_half_open",
     "side": "white",
     "text": "Полуоткрытая линия d: давите ладьёй на пешку d6."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Полуоткрытая линия c: давите ладьёй на пешку c2."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Большинство на ферзевом фланге (3 против 2): в эндшпиле оно даёт проходную."
    }
   ]
  },
  "59": {
   "structures": [
    "scheveningen"
   ],
   "structure_title": "Сицилианская: малый центр (Шевенинген)",
   "structure_summary": "Пешки d6 и e6 — прочный «малый центр» чёрных, за ним фигуры перестраиваются без спешки. Белые владеют пространством и атакуют на королевском фланге; чёрные отвечают контригрой на ферзевом фланге и по линии c и ждут момента для прорыва …d5.",
   "ideas": [
    {
     "key": "scheveningen.counter",
     "side": "black",
     "text": "Контригра — на ферзевом фланге и по полуоткрытой линии c; освобождающий прорыв …d5 готовьте фигурами."
    },
    {
     "key": "scheveningen.attack",
     "side": "white",
     "text": "Используйте пространство: пешечная атака на королевском фланге и прорыв e4–e5 против пешки d6."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Готовьте прорыв f7–f5 против пешки e4."
    },
    {
     "key": "rook_half_open",
     "side": "white",
     "text": "Полуоткрытая линия d: давите ладьёй на пешку d6."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Полуоткрытая линия c: давите ладьёй на пешку c2."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Большинство на ферзевом фланге (3 против 2): в эндшпиле оно даёт проходную."
    }
   ]
  },
  "66": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Структура Найдорфа / Свешникова",
   "structure_summary": "Пешка e5 даёт чёрным пространство и активную игру, но поле d5 пешкой уже не защитить, а пешка d6 — отсталая. Белые борются за поле d5; чёрные готовят прорыв …d5 и контригру на ферзевом фланге.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "Прорыв …d5 убирает отсталую пешку d6 и снимает проблемы; до тех пор контригра — на ферзевом фланге и по линии c."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "Поле d5 — главный пункт: ставьте туда фигуры и разменивайте его защитников (конь f6)."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "Пешечный прорыв f4 — удар по пешке e5."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Давите на отсталую пешку d6: пешкой её не защитить, а поле перед ней — ваше."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Готовьте прорыв f7–f5 против пешки e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Полуоткрытая линия c: давите ладьёй на пешку c2."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Большинство на ферзевом фланге (3 против 2): в эндшпиле оно даёт проходную."
    }
   ]
  }
 },
 "en": {
  "10": {
   "structures": [],
   "structure_title": null,
   "structure_summary": null,
   "ideas": [
    {
     "key": "pawn_break_now",
     "side": "black",
     "text": "The pawn break …d5 strikes at e4."
    },
    {
     "key": "pawn_break_prepare",
     "side": "white",
     "text": "Prepare the e4–e5 break against d6."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Prepare the f7–f5 break against e4."
    },
    {
     "key": "rook_half_open",
     "side": "white",
     "text": "Half-open d-file: press on d6 with a rook."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Half-open c-file: press on c2 with a rook."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Majority on the queenside (3 vs 2): in the endgame it can create a passed pawn."
    }
   ]
  },
  "12": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Najdorf / Sveshnikov structure",
   "structure_summary": "The e5 pawn gives Black space and active play, but d5 can no longer be covered by a pawn and the d6 pawn is backward. White fights for d5; Black prepares the …d5 break and queenside counterplay.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "The …d5 break gets rid of the backward d6 pawn and solves your problems; until then counterplay comes on the queenside and along the c-file."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "d5 is the key square: put pieces there and trade off its defenders (knight f6)."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "The pawn break f4 strikes at e5."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Attack the backward pawn on d6: no pawn can defend it, and the square in front of it is yours."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Prepare the f7–f5 break against e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Half-open c-file: press on c2 with a rook."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Majority on the queenside (3 vs 2): in the endgame it can create a passed pawn."
    }
   ]
  },
  "16": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Najdorf / Sveshnikov structure",
   "structure_summary": "The e5 pawn gives Black space and active play, but d5 can no longer be covered by a pawn and the d6 pawn is backward. White fights for d5; Black prepares the …d5 break and queenside counterplay.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "The …d5 break gets rid of the backward d6 pawn and solves your problems; until then counterplay comes on the queenside and along the c-file."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "d5 is the key square: put pieces there and trade off its defenders (bishop e6, knight f6)."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "The pawn break f4 strikes at e5."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Attack the backward pawn on d6: no pawn can defend it, and the square in front of it is yours."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Prepare the f7–f5 break against e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Half-open c-file: press on c2 with a rook."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Majority on the queenside (3 vs 2): in the endgame it can create a passed pawn."
    }
   ]
  },
  "25": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Najdorf / Sveshnikov structure",
   "structure_summary": "The e5 pawn gives Black space and active play, but d5 can no longer be covered by a pawn and the d6 pawn is backward. White fights for d5; Black prepares the …d5 break and queenside counterplay.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "The …d5 break gets rid of the backward d6 pawn and solves your problems; until then counterplay comes on the queenside and along the c-file."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "d5 is the key square: put pieces there and trade off its defenders (bishop e6, knight f6)."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "The pawn break f4 strikes at e5."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Attack the backward pawn on d6: no pawn can defend it, and the square in front of it is yours."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Prepare the f7–f5 break against e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Half-open c-file: press on c2 with a rook."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Majority on the queenside (3 vs 2): in the endgame it can create a passed pawn."
    }
   ]
  },
  "32": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Najdorf / Sveshnikov structure",
   "structure_summary": "The e5 pawn gives Black space and active play, but d5 can no longer be covered by a pawn and the d6 pawn is backward. White fights for d5; Black prepares the …d5 break and queenside counterplay.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "The …d5 break gets rid of the backward d6 pawn and solves your problems; until then counterplay comes on the queenside and along the c-file."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "d5 is the key square: put pieces there and trade off its defenders (bishop e6, knight f6)."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "The pawn break f4 strikes at e5."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Attack the backward pawn on d6: no pawn can defend it, and the square in front of it is yours."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Prepare the f7–f5 break against e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Half-open c-file: press on c2 with a rook."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Majority on the queenside (3 vs 2): in the endgame it can create a passed pawn."
    }
   ]
  },
  "35": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Najdorf / Sveshnikov structure",
   "structure_summary": "The e5 pawn gives Black space and active play, but d5 can no longer be covered by a pawn and the d6 pawn is backward. White fights for d5; Black prepares the d6–d5 break and queenside counterplay.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "The d6–d5 break gets rid of the backward d6 pawn and solves your problems; until then counterplay comes on the queenside and along the c-file."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "d5 is the key square: put pieces there and trade off its defenders (knight f6)."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Attack the backward pawn on d6: no pawn can defend it, and the square in front of it is yours."
    },
    {
     "key": "pawn_break_prepare",
     "side": "white",
     "text": "Prepare the f2–f4 break against e5."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Prepare the f7–f5 break against e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Half-open c-file: press on c2 with a rook."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Majority on the queenside (3 vs 2): in the endgame it can create a passed pawn."
    }
   ]
  },
  "43": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Najdorf / Sveshnikov structure",
   "structure_summary": "The e5 pawn gives Black space and active play, but d5 can no longer be covered by a pawn and the d6 pawn is backward. White fights for d5; Black prepares the d6–d5 break and queenside counterplay.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "The d6–d5 break gets rid of the backward d6 pawn and solves your problems; until then counterplay comes on the queenside and along the c-file."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "d5 is the key square: put pieces there and trade off its defenders (knight f6)."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "The pawn break f4 strikes at e5."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Attack the backward pawn on d6: no pawn can defend it, and the square in front of it is yours."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Prepare the f7–f5 break against e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Half-open c-file: press on c2 with a rook."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Majority on the queenside (3 vs 2): in the endgame it can create a passed pawn."
    }
   ]
  },
  "50": {
   "structures": [
    "scheveningen"
   ],
   "structure_title": "Sicilian small centre (Scheveningen)",
   "structure_summary": "Black's pawns on d6 and e6 form a solid 'small centre' behind which the pieces regroup calmly. White has more space and attacks on the kingside; Black counters on the queenside and along the c-file, waiting for the …d5 break.",
   "ideas": [
    {
     "key": "scheveningen.counter",
     "side": "black",
     "text": "Counterplay comes on the queenside and along the half-open c-file; prepare the freeing break …d5 with your pieces."
    },
    {
     "key": "scheveningen.attack",
     "side": "white",
     "text": "Use the extra space: a pawn storm on the kingside and the e4–e5 break against d6."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Prepare the f7–f5 break against e4."
    },
    {
     "key": "rook_half_open",
     "side": "white",
     "text": "Half-open d-file: press on d6 with a rook."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Half-open c-file: press on c2 with a rook."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Majority on the queenside (3 vs 2): in the endgame it can create a passed pawn."
    }
   ]
  },
  "57": {
   "structures": [
    "scheveningen"
   ],
   "structure_title": "Sicilian small centre (Scheveningen)",
   "structure_summary": "Black's pawns on d6 and e6 form a solid 'small centre' behind which the pieces regroup calmly. White has more space and attacks on the kingside; Black counters on the queenside and along the c-file, waiting for the d6–d5 break.",
   "ideas": [
    {
     "key": "scheveningen.counter",
     "side": "black",
     "text": "Counterplay comes on the queenside and along the half-open c-file; prepare the freeing break d6–d5 with your pieces."
    },
    {
     "key": "scheveningen.attack",
     "side": "white",
     "text": "Use the extra space: a pawn storm on the kingside and the e4–e5 break against d6."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "The pawn break f5 strikes at e6."
    },
    {
     "key": "pawn_break_now",
     "side": "black",
     "text": "The pawn break …e5 strikes at f4."
    },
    {
     "key": "rook_half_open",
     "side": "white",
     "text": "Half-open d-file: press on d6 with a rook."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Half-open c-file: press on c2 with a rook."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Majority on the queenside (3 vs 2): in the endgame it can create a passed pawn."
    }
   ]
  },
  "59": {
   "structures": [
    "scheveningen"
   ],
   "structure_title": "Sicilian small centre (Scheveningen)",
   "structure_summary": "Black's pawns on d6 and e6 form a solid 'small centre' behind which the pieces regroup calmly. White has more space and attacks on the kingside; Black counters on the queenside and along the c-file, waiting for the …d5 break.",
   "ideas": [
    {
     "key": "scheveningen.counter",
     "side": "black",
     "text": "Counterplay comes on the queenside and along the half-open c-file; prepare the freeing break …d5 with your pieces."
    },
    {
     "key": "scheveningen.attack",
     "side": "white",
     "text": "Use the extra space: a pawn storm on the kingside and the e4–e5 break against d6."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Prepare the f7–f5 break against e4."
    },
    {
     "key": "rook_half_open",
     "side": "white",
     "text": "Half-open d-file: press on d6 with a rook."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Half-open c-file: press on c2 with a rook."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Majority on the queenside (3 vs 2): in the endgame it can create a passed pawn."
    }
   ]
  },
  "66": {
   "structures": [
    "sicilian_d6_e5"
   ],
   "structure_title": "Najdorf / Sveshnikov structure",
   "structure_summary": "The e5 pawn gives Black space and active play, but d5 can no longer be covered by a pawn and the d6 pawn is backward. White fights for d5; Black prepares the …d5 break and queenside counterplay.",
   "ideas": [
    {
     "key": "sicilian_d6_e5.d5_break",
     "side": "black",
     "text": "The …d5 break gets rid of the backward d6 pawn and solves your problems; until then counterplay comes on the queenside and along the c-file."
    },
    {
     "key": "sicilian_d6_e5.d5",
     "side": "white",
     "text": "d5 is the key square: put pieces there and trade off its defenders (knight f6)."
    },
    {
     "key": "pawn_break_now",
     "side": "white",
     "text": "The pawn break f4 strikes at e5."
    },
    {
     "key": "target_backward",
     "side": "white",
     "text": "Attack the backward pawn on d6: no pawn can defend it, and the square in front of it is yours."
    },
    {
     "key": "pawn_break_prepare",
     "side": "black",
     "text": "Prepare the f7–f5 break against e4."
    },
    {
     "key": "rook_half_open",
     "side": "black",
     "text": "Half-open c-file: press on c2 with a rook."
    },
    {
     "key": "majority",
     "side": "white",
     "text": "Majority on the queenside (3 vs 2): in the endgame it can create a passed pawn."
    }
   ]
  }
 }
};

/** Ходы не хуже порога (кроме хода курса) по узлам карточек — для фейкового тренажёра. */
export const najdorfAlternatives: Record<string, { uci: string; san: string; win_loss: number }[]> = {
 "1": [
  {
   "uci": "d7d6",
   "san": "d6",
   "win_loss": 0.6
  },
  {
   "uci": "e7e5",
   "san": "e5",
   "win_loss": 0.7
  },
  {
   "uci": "e7e6",
   "san": "e6",
   "win_loss": 0.7
  }
 ],
 "3": [
  {
   "uci": "b8c6",
   "san": "Nc6",
   "win_loss": 0.0
  },
  {
   "uci": "e7e6",
   "san": "e6",
   "win_loss": 0.5
  },
  {
   "uci": "a7a6",
   "san": "a6",
   "win_loss": 1.9
  }
 ],
 "5": [
  {
   "uci": "g8f6",
   "san": "Nf6",
   "win_loss": 0.3
  }
 ],
 "7": [
  {
   "uci": "b8c6",
   "san": "Nc6",
   "win_loss": 1.3
  },
  {
   "uci": "e7e5",
   "san": "e5",
   "win_loss": 2.5
  },
  {
   "uci": "c8d7",
   "san": "Bd7",
   "win_loss": 2.8
  }
 ],
 "9": [
  {
   "uci": "b8c6",
   "san": "Nc6",
   "win_loss": 1.2
  },
  {
   "uci": "c8d7",
   "san": "Bd7",
   "win_loss": 2.5
  },
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 2.9
  }
 ],
 "11": [
  {
   "uci": "f6g4",
   "san": "Ng4",
   "win_loss": 0.5
  },
  {
   "uci": "e7e6",
   "san": "e6",
   "win_loss": 2.4
  },
  {
   "uci": "b8c6",
   "san": "Nc6",
   "win_loss": 2.7
  }
 ],
 "13": [
  {
   "uci": "f6g4",
   "san": "Ng4",
   "win_loss": 0.6
  },
  {
   "uci": "f8e7",
   "san": "Be7",
   "win_loss": 1.4
  },
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 2.5
  }
 ],
 "15": [
  {
   "uci": "h7h5",
   "san": "h5",
   "win_loss": 0.0
  },
  {
   "uci": "b8d7",
   "san": "Nbd7",
   "win_loss": 1.5
  },
  {
   "uci": "b8c6",
   "san": "Nc6",
   "win_loss": 1.7
  }
 ],
 "17": [
  {
   "uci": "h7h5",
   "san": "h5",
   "win_loss": 0.0
  },
  {
   "uci": "b8d7",
   "san": "Nbd7",
   "win_loss": 0.8
  },
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 0.9
  }
 ],
 "19": [
  {
   "uci": "b7b5",
   "san": "b5",
   "win_loss": 0.9
  },
  {
   "uci": "d8c7",
   "san": "Qc7",
   "win_loss": 2.2
  },
  {
   "uci": "h7h5",
   "san": "h5",
   "win_loss": 4.2
  }
 ],
 "21": [
  {
   "uci": "d8c7",
   "san": "Qc7",
   "win_loss": 1.0
  },
  {
   "uci": "a8b8",
   "san": "Rb8",
   "win_loss": 3.7
  },
  {
   "uci": "d7b6",
   "san": "Nb6",
   "win_loss": 3.8
  }
 ],
 "23": [
  {
   "uci": "f6h5",
   "san": "Nh5",
   "win_loss": 0.0
  }
 ],
 "25": [
  {
   "uci": "h7h5",
   "san": "h5",
   "win_loss": 0.7
  },
  {
   "uci": "f8e7",
   "san": "Be7",
   "win_loss": 1.7
  },
  {
   "uci": "d8c7",
   "san": "Qc7",
   "win_loss": 1.9
  }
 ],
 "27": [
  {
   "uci": "h7h5",
   "san": "h5",
   "win_loss": 0.0
  },
  {
   "uci": "f8e7",
   "san": "Be7",
   "win_loss": 1.1
  },
  {
   "uci": "d8c7",
   "san": "Qc7",
   "win_loss": 1.6
  },
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 1.9
  }
 ],
 "29": [
  {
   "uci": "b5b4",
   "san": "b4",
   "win_loss": 0.0
  },
  {
   "uci": "f8e7",
   "san": "Be7",
   "win_loss": 2.1
  },
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 2.3
  }
 ],
 "31": [
  {
   "uci": "b8d7",
   "san": "Nbd7",
   "win_loss": 0.0
  },
  {
   "uci": "b8c6",
   "san": "Nc6",
   "win_loss": 0.3
  },
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 3.1
  }
 ],
 "33": [
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 4.7
  }
 ],
 "35": [
  {
   "uci": "f8e7",
   "san": "Be7",
   "win_loss": 0.0
  },
  {
   "uci": "b8c6",
   "san": "Nc6",
   "win_loss": 1.8
  },
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 3.8
  }
 ],
 "37": [
  {
   "uci": "c8e6",
   "san": "Be6",
   "win_loss": 0.5
  },
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 0.9
  },
  {
   "uci": "c8g4",
   "san": "Bg4",
   "win_loss": 2.1
  }
 ],
 "39": [
  {
   "uci": "b7b6",
   "san": "b6",
   "win_loss": 0.0
  },
  {
   "uci": "c8e6",
   "san": "Be6",
   "win_loss": 1.0
  },
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 2.2
  }
 ],
 "41": [
  {
   "uci": "b7b6",
   "san": "b6",
   "win_loss": 0.0
  },
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 0.6
  },
  {
   "uci": "c8d7",
   "san": "Bd7",
   "win_loss": 1.6
  }
 ],
 "43": [
  {
   "uci": "c8e6",
   "san": "Be6",
   "win_loss": 0.0
  },
  {
   "uci": "f8e7",
   "san": "Be7",
   "win_loss": 0.5
  },
  {
   "uci": "b8c6",
   "san": "Nc6",
   "win_loss": 0.9
  },
  {
   "uci": "d8a5",
   "san": "Qa5",
   "win_loss": 1.1
  }
 ],
 "45": [
  {
   "uci": "a8b8",
   "san": "Rb8",
   "win_loss": 2.7
  },
  {
   "uci": "d8a5",
   "san": "Qa5",
   "win_loss": 2.9
  },
  {
   "uci": "f8e7",
   "san": "Be7",
   "win_loss": 3.2
  }
 ],
 "47": [
  {
   "uci": "f8e7",
   "san": "Be7",
   "win_loss": 0.0
  },
  {
   "uci": "a8b8",
   "san": "Rb8",
   "win_loss": 0.6
  },
  {
   "uci": "h7h5",
   "san": "h5",
   "win_loss": 1.2
  },
  {
   "uci": "d8c7",
   "san": "Qc7",
   "win_loss": 2.3
  }
 ],
 "49": [
  {
   "uci": "b8d7",
   "san": "Nbd7",
   "win_loss": 1.1
  },
  {
   "uci": "c8d7",
   "san": "Bd7",
   "win_loss": 1.7
  },
  {
   "uci": "b8c6",
   "san": "Nc6",
   "win_loss": 2.7
  }
 ],
 "51": [
  {
   "uci": "d8b6",
   "san": "Qb6",
   "win_loss": 0.0
  },
  {
   "uci": "b8d7",
   "san": "Nbd7",
   "win_loss": 2.1
  },
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 2.5
  }
 ],
 "53": [
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 0.1
  },
  {
   "uci": "b8d7",
   "san": "Nbd7",
   "win_loss": 0.9
  },
  {
   "uci": "b8c6",
   "san": "Nc6",
   "win_loss": 3.8
  }
 ],
 "55": [
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 0.0
  },
  {
   "uci": "c8d7",
   "san": "Bd7",
   "win_loss": 3.8
  },
  {
   "uci": "e8g8",
   "san": "O-O",
   "win_loss": 5.0
  }
 ],
 "57": [
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 0.6
  },
  {
   "uci": "h7h5",
   "san": "h5",
   "win_loss": 4.7
  }
 ],
 "59": [
  {
   "uci": "b8d7",
   "san": "Nbd7",
   "win_loss": 0.6
  },
  {
   "uci": "c8d7",
   "san": "Bd7",
   "win_loss": 1.3
  },
  {
   "uci": "f8e7",
   "san": "Be7",
   "win_loss": 1.3
  }
 ],
 "61": [
  {
   "uci": "c8d7",
   "san": "Bd7",
   "win_loss": 0.0
  },
  {
   "uci": "f8e7",
   "san": "Be7",
   "win_loss": 0.3
  }
 ],
 "63": [
  {
   "uci": "f8e7",
   "san": "Be7",
   "win_loss": 0.6
  },
  {
   "uci": "a8b8",
   "san": "Rb8",
   "win_loss": 3.8
  },
  {
   "uci": "d8a5",
   "san": "Qa5",
   "win_loss": 4.3
  }
 ],
 "65": [
  {
   "uci": "e7e6",
   "san": "e6",
   "win_loss": 0.7
  },
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 0.7
  },
  {
   "uci": "g7g6",
   "san": "g6",
   "win_loss": 1.2
  }
 ],
 "67": [
  {
   "uci": "b7b5",
   "san": "b5",
   "win_loss": 1.9
  },
  {
   "uci": "h7h6",
   "san": "h6",
   "win_loss": 2.2
  },
  {
   "uci": "c8e6",
   "san": "Be6",
   "win_loss": 2.2
  }
 ],
 "69": [
  {
   "uci": "b8d7",
   "san": "Nbd7",
   "win_loss": 0.0
  },
  {
   "uci": "f8e7",
   "san": "Be7",
   "win_loss": 0.1
  },
  {
   "uci": "d8c7",
   "san": "Qc7",
   "win_loss": 0.3
  }
 ],
 "71": [
  {
   "uci": "d8c7",
   "san": "Qc7",
   "win_loss": 0.8
  },
  {
   "uci": "c8b7",
   "san": "Bb7",
   "win_loss": 1.2
  },
  {
   "uci": "f8e7",
   "san": "Be7",
   "win_loss": 3.1
  }
 ]
};
