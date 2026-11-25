"""Генератор dev-фикстуры курса «Сицилианская, Найдорф» за чёрных (сессия 13.7).

Только для разработки и проверки вёрстки без бэкенда 13.4: строит дерево `CourseTree` по
заданным линиям, книжность и названия — из базы дебютов (`app.review.openings`), идеи и
тексты RU/EN — настоящим `app.plans`, оценки и альтернативы для тренажёра — Stockfish,
образцовые партии — продолжение партии движком из узла (имена игроков вымышленные).

Запуск (из backend/, нужен stockfish в PATH):
    uv run python ../web/src/components/courses/fixtures/generate_najdorf.py
Пишет `najdorf-data.ts` рядом с собой."""

import json
import random
from pathlib import Path

import chess
import chess.engine
import chess.pgn

from app.plans.ideas import position_ideas
from app.plans.templates import render
from app.review.openings import default_openings
from app.review.winprob import win_percent, win_percent_from_cp

OUT = Path(__file__).with_name("najdorf-data.ts")
DEPTH = 14
ALT_THRESHOLD = 5.0
COLOR = chess.BLACK

LINE = "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6".split()

# Продолжения после исходной линии: (SAN, вес хода соперника, дети). Первый ребёнок —
# основной; у ученика — ровно один ход.
Spec = tuple[str, float, list["Spec"]]


def chain(sans: str, weights: dict[int, float] | None = None, tail: list[Spec] | None = None) -> list[Spec]:
    moves = sans.split()
    node: list[Spec] = tail or []
    for i in range(len(moves) - 1, -1, -1):
        node = [(moves[i], (weights or {}).get(i, 1.0), node)]
    return node


BRANCHES: list[Spec] = [
    (
        "Be3",
        0.42,
        [
            (
                "e5",
                1.0,
                [
                    (
                        "Nb3",
                        0.71,
                        [
                            (
                                "Be6",
                                1.0,
                                [
                                    ("f3", 0.74, chain("Be7 Qd2 O-O O-O-O Nbd7 g4 b5 g5 b4", {1: 0.81, 3: 0.88, 5: 0.9, 7: 0.85})),
                                    ("Qd2", 0.18, chain("Nbd7 f3 b5 g4 Nb6")),
                                    ("h3", 0.08, chain("Be7 g4 d5")),
                                ],
                            )
                        ],
                    ),
                    ("Nf3", 0.19, chain("Qc7 a4 Be7 Be2 O-O O-O Be6")),
                    ("Nde2", 0.1, chain("Nbd7 g3 b5 Bg2 Bb7")),
                ],
            )
        ],
    ),
    (
        "Bg5",
        0.27,
        [
            (
                "e6",
                1.0,
                [
                    ("f4", 0.83, chain("Be7 Qf3 Qc7 O-O-O Nbd7 g4 b5", {1: 0.9, 3: 0.95, 5: 0.8})),
                    ("Qf3", 0.17, chain("h6 Bh4 Nbd7 O-O-O Qc7")),
                ],
            )
        ],
    ),
    ("h3", 0.16, chain("e5 Nde2 h5 g3 b5 Bg2 Nbd7", {0: 1.0, 1: 0.78, 3: 0.92})),
]

WHITE_NAMES = ["Varga, Z.", "Lindqvist, O.", "Moreau, T.", "Okafor, E.", "Sandoval, R.", "Haugen, K."]
BLACK_NAMES = ["Petrescu, M.", "Ibarra, J.", "Kowalczyk, D.", "Rahimov, A.", "Fontaine, L.", "Brandt, S."]


def score_cp(info: chess.engine.InfoDict) -> tuple[int | None, int | None]:
    score = info["score"].white()
    return (score.score(), None) if not score.is_mate() else (None, score.mate())


def main() -> None:
    db = default_openings()
    rng = random.Random(13)
    nodes: list[dict] = []
    boards: list[chess.Board] = []
    alternatives: dict[str, list[dict]] = {}

    with chess.engine.SimpleEngine.popen_uci("stockfish") as engine:

        def add(parent: int | None, board: chess.Board, san: str | None, weight: float, book_parent: bool) -> int:
            node_id = len(nodes)
            uci = None
            if san is not None:
                move = board.parse_san(san)
                uci = move.uci()
                board = board.copy()
                board.push(move)
            info = engine.analyse(board, chess.engine.Limit(depth=DEPTH))
            cp, mate = score_cp(info)
            pv = info.get("pv") or []
            book = book_parent and db.contains(board) if san is not None else True
            opening = db.lookup(board)
            mover = None
            if san is not None:
                mover = "learner" if (not board.turn) == COLOR else "opponent"
            nodes.append(
                {
                    "id": node_id,
                    "parent": parent,
                    "children": [],
                    "ply": board.ply(),
                    "uci": uci,
                    "san": san,
                    "mover": mover,
                    "fen": board.fen(),
                    "book": book,
                    "name": opening.name if opening else None,
                    "main": False,
                    "weight": round(weight, 2),
                    "stats": None,
                    "eval": {"cp": cp, "mate": mate, "depth": DEPTH, "best_uci": pv[0].uci() if pv else None},
                    "ideas": None,
                    "key_moment": None,
                }
            )
            boards.append(board)
            if parent is not None:
                nodes[parent]["children"].append(node_id)
            return node_id

        root = add(None, chess.Board(), None, 1.0, True)
        current = root
        for san in LINE:
            current = add(current, boards[current], san, 1.0, nodes[current]["book"])
        line_end = current

        def grow(parent: int, specs: list[Spec]) -> None:
            for san, weight, kids in specs:
                child = add(parent, boards[parent], san, weight, nodes[parent]["book"])
                grow(child, kids)

        grow(line_end, BRANCHES)

        # Ход ученика — основной; партии мастеров — убывают по линии.
        for node in nodes:
            if node["mover"] == "learner":
                node["main"] = True
        nodes[root]["stats"] = None

        def stats(node_id: int, games: int) -> None:
            node = nodes[node_id]
            if node["uci"] is not None:
                ev = node["eval"]
                white_p = win_percent_from_cp(ev["cp"]) if ev["cp"] is not None else 50
                draws = round(games * rng.uniform(0.36, 0.46))
                white = round((games - draws) * (white_p / 100))
                node["stats"] = {
                    "source": "masters",
                    "games": games,
                    "white": white,
                    "draws": draws,
                    "black": games - draws - white,
                    "average_rating": rng.randint(2440, 2580),
                }
            for kid in node["children"]:
                kid_node = nodes[kid]
                share = kid_node["weight"] if kid_node["mover"] == "opponent" else rng.uniform(0.62, 0.8)
                stats(kid, max(3, round(games * share)))

        stats(root, 812_000)

        # Ключевые узлы: конец исходной линии, выход из теории, смена структуры.
        last_structures: dict[int, tuple[str, ...]] = {}
        for node in nodes:
            ideas = position_ideas(boards[node["id"]])
            parent = node["parent"]
            prev = last_structures.get(parent, ()) if parent is not None else ()
            last_structures[node["id"]] = ideas.structures or prev
            key = None
            if node["id"] == line_end:
                key = "line_end"
            elif parent is not None and nodes[parent]["book"] and not node["book"]:
                key = "book_exit"
            elif node["ply"] > 10 and ideas.structures and ideas.structures != prev:
                key = "structure"
            if key is not None:
                node["key_moment"] = key
                node["ideas"] = json.loads(ideas.model_dump_json())

        # Альтернативы для фейкового тренажёра: ходы не хуже порога, кроме хода курса.
        for node in nodes:
            learner_kids = [nodes[k] for k in node["children"] if nodes[k]["mover"] == "learner"]
            if not learner_kids:
                continue
            board = boards[node["id"]]
            infos = engine.analyse(board, chess.engine.Limit(depth=DEPTH), multipv=4)
            best = win_percent(infos[0]["score"].pov(board.turn))
            alts = []
            for info in infos:
                move = info["pv"][0]
                if move.uci() in {k["uci"] for k in learner_kids}:
                    continue
                loss = max(0.0, best - win_percent(info["score"].pov(board.turn)))
                if loss <= ALT_THRESHOLD:
                    alts.append({"uci": move.uci(), "san": board.san(move), "win_loss": round(loss, 1)})
            alternatives[str(node["id"])] = alts

        # Образцовые партии: из ключевых узлов и листьев — продолжение движком.
        model_games = []
        anchors = [n for n in nodes if n["key_moment"] in ("structure", "book_exit") or (not n["children"] and n["ply"] > 14)]
        for i, anchor in enumerate(anchors[:7]):
            board = boards[anchor["id"]].copy()
            for _ in range(rng.randint(34, 52)):
                if board.is_game_over():
                    break
                infos = engine.analyse(board, chess.engine.Limit(depth=10), multipv=2)
                pick = infos[0] if len(infos) == 1 or rng.random() < 0.8 else infos[1]
                board.push(pick["pv"][0])
            info = engine.analyse(board, chess.engine.Limit(depth=12))
            white_score = info["score"].white().score(mate_score=10_000)
            result = board.result(claim_draw=True)
            if result == "*":
                result = "1-0" if white_score > 150 else "0-1" if white_score < -150 else "1/2-1/2"
            game = chess.pgn.Game.from_board(board)
            year = rng.randint(2012, 2025)
            white_name, black_name = WHITE_NAMES[i % 6], BLACK_NAMES[(i + 2) % 6]
            white_rating, black_rating = rng.randint(2480, 2720), rng.randint(2480, 2720)
            game.headers.update(
                {
                    "Event": "Fixture Open",
                    "Site": "?",
                    "Date": f"{year}.??.??",
                    "White": white_name,
                    "Black": black_name,
                    "Result": result,
                    "WhiteElo": str(white_rating),
                    "BlackElo": str(black_rating),
                }
            )
            game.headers.pop("Round", None)
            pgn = str(game).strip()
            model_games.append(
                {
                    "id": f"fx{i + 1:02d}",
                    "node_id": anchor["id"],
                    "white": white_name,
                    "black": black_name,
                    "white_rating": white_rating,
                    "black_rating": black_rating,
                    "year": year,
                    "result": result,
                    "pgn": pgn,
                }
            )

    tree = {"version": 1, "color": "black", "line_end": line_end, "nodes": nodes, "model_games": model_games}
    ideas_text = {
        lang: {
            str(n["id"]): json.loads(render(position_ideas(boards[n["id"]]), lang).model_dump_json())
            for n in nodes
            if n["ideas"] is not None
        }
        for lang in ("ru", "en")
    }

    def dump(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, indent=1)

    OUT.write_text(
        "// Сгенерировано generate_najdorf.py — не править руками. Dev-фикстура (сессия 13.7):\n"
        "// дерево курса «Найдорф за чёрных», идеи RU/EN из app.plans, оценки Stockfish.\n"
        'import type { CourseTree, RenderedIdeas } from "@/lib/courses-api";\n\n'
        f"export const najdorfTree: CourseTree = {dump(tree)};\n\n"
        "export const najdorfIdeas: Record<\"ru\" | \"en\", Record<string, RenderedIdeas>> = "
        f"{dump(ideas_text)};\n\n"
        "/** Ходы не хуже порога (кроме хода курса) по узлам карточек — для фейкового тренажёра. */\n"
        "export const najdorfAlternatives: Record<string, { uci: string; san: string; win_loss: number }[]> = "
        f"{dump(alternatives)};\n",
        encoding="utf-8",
    )
    print(f"nodes={len(nodes)} key={sum(1 for n in nodes if n['ideas'])} games={len(model_games)} -> {OUT}")


if __name__ == "__main__":
    main()
