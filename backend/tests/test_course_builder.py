"""Сборщик курса на фиксированных линиях с фейковыми Explorer и движком: форма дерева,
лимиты, ветки соперника, выбор хода ученика, ключевые узлы, образцовые партии, ключ."""

import chess
import pytest

from app.courses import builder as builder_module
from app.courses.builder import (
    MAX_LINE_PLIES,
    MAX_MODEL_GAMES,
    BuildLimits,
    CourseBuilder,
    LineError,
    course_key,
    parse_line,
)
from app.courses.types import CourseNode, CourseTree
from app.engine.cache import MemoryEvalCache, fen_key
from app.explorer.types import ExplorerUnavailableError
from app.review.openings import default_openings
from app.trainer.cards import card_nodes, ideas_node_id
from tests.course_fakes import (
    ITALIAN,
    ITALIAN_GAMES,
    NAJDORF,
    NAJDORF_GAMES,
    ROSSOLIMO,
    ROSSOLIMO_GAMES,
    FakeEngine,
    GamesExplorer,
    board_after,
)

LIMITS = BuildLimits(target_plies=24, max_nodes=60)


async def build(
    line: str,
    color: chess.Color,
    games: list[tuple[str, int]],
    *,
    limits: BuildLimits = LIMITS,
    engine: FakeEngine | None = None,
    explorer: GamesExplorer | None = None,
) -> CourseTree:
    builder = CourseBuilder(explorer or GamesExplorer(games), engine or FakeEngine(), limits=limits)
    return await builder.build(parse_line(line.split()), color)


def by_id(tree: CourseTree) -> dict[int, CourseNode]:
    return {node.id: node for node in tree.nodes}


def kids(tree: CourseTree, node: CourseNode) -> list[CourseNode]:
    index = by_id(tree)
    return [index[i] for i in node.children]


def path(tree: CourseTree, node: CourseNode) -> list[CourseNode]:
    index = by_id(tree)
    out = [node]
    while out[-1].parent is not None:
        out.append(index[out[-1].parent])
    return out[::-1]


def assert_well_formed(tree: CourseTree, line: str, color: chess.Color) -> None:
    """Инварианты контракта дерева, общие для всех курсов."""
    assert CourseTree.model_validate(tree.model_dump(mode="json")) == tree
    index = by_id(tree)
    assert [n.id for n in tree.nodes] == list(range(len(tree.nodes)))
    root = tree.nodes[0]
    assert root.parent is None
    assert root.uci is None
    assert root.mover is None
    assert root.fen == chess.STARTING_FEN
    learner = "white" if color == chess.WHITE else "black"
    assert tree.color == learner
    for node in tree.nodes:
        assert node.eval is not None
        for kid in kids(tree, node):
            assert kid.parent == node.id
            assert kid.ply == node.ply + 1
            board = chess.Board(node.fen)
            move = chess.Move.from_uci(kid.uci or "")
            assert board.is_legal(move)
            assert kid.san == board.san(move)
            board.push(move)
            assert kid.fen == board.fen()
            side = "white" if chess.Board(node.fen).turn == chess.WHITE else "black"
            assert kid.mover == ("learner" if side == learner else "opponent")
        # За ученика — один ход, основной.
        if chess.Board(node.fen).turn == color:
            assert len(node.children) <= 1
            assert all(k.main for k in kids(tree, node))
        else:
            assert not any(k.main for k in kids(tree, node))
        # Идеи — ровно у ключевых узлов.
        assert (node.ideas is not None) == (node.key_moment is not None)
    # Исходная линия — цепочка от корня до line_end.
    line_nodes = path(tree, index[tree.line_end])
    assert [n.uci for n in line_nodes[1:]] == line.split()
    for node in line_nodes[:-1]:
        assert len(node.children) == 1
    assert index[tree.line_end].key_moment is not None


async def test_najdorf_for_black_shape_and_branches() -> None:
    tree = await build(NAJDORF, chess.BLACK, NAJDORF_GAMES)

    assert_well_formed(tree, NAJDORF, chess.BLACK)
    end = by_id(tree)[tree.line_end]
    assert end.ply == 10
    assert end.name == "Sicilian Defense: Najdorf Variation"
    assert len(tree.nodes) <= LIMITS.max_nodes
    assert max(n.ply for n in tree.nodes) == LIMITS.target_plies
    # После 5… a6 ход белых — соперник: три ответа с долей ≥ 10%, 6. h3 (8%) отсечён.
    replies = kids(tree, end)
    assert [r.uci for r in replies] == ["c1e3", "c1g5", "f1e2"]
    assert [r.weight for r in replies] == [
        pytest.approx(40 / 98, abs=1e-3),
        pytest.approx(30 / 98, abs=1e-3),
        pytest.approx(20 / 98, abs=1e-3),
    ]
    assert all(r.stats is not None and r.stats.source == "masters" for r in replies)
    assert replies[0].stats is not None
    assert replies[0].stats.games == 40
    # За ученика — самый популярный ход мастеров: 6. Bg5 e6 (25 из 30), 6. Be3 e5.
    assert [k.uci for k in kids(tree, replies[0])] == ["e7e5"]
    assert [k.uci for k in kids(tree, replies[1])] == ["e7e6"]
    # Исходная линия — книжная; ходы соперника в ней — с долей у мастеров.
    assert all(n.book for n in path(tree, end))
    assert path(tree, end)[1].mover == "opponent"


async def test_rossolimo_for_white() -> None:
    tree = await build(ROSSOLIMO, chess.WHITE, ROSSOLIMO_GAMES)

    assert_well_formed(tree, ROSSOLIMO, chess.WHITE)
    end = by_id(tree)[tree.line_end]
    assert end.uci == "f1b5"
    assert end.mover == "learner"
    assert end.main
    assert [r.uci for r in kids(tree, end)] == ["g7g6", "e7e6", "d7d6"]
    # После 3… g6 за белых — 4. Bxc6 (все партии мастеров).
    assert [k.san for k in kids(tree, kids(tree, end)[0])] == ["Bxc6"]
    assert card_nodes(tree)  # тренажёру есть что спрашивать


@pytest.mark.parametrize("color", [chess.WHITE, chess.BLACK])
async def test_italian_both_colors(color: chess.Color) -> None:
    tree = await build(ITALIAN, color, ITALIAN_GAMES)

    assert_well_formed(tree, ITALIAN, color)
    end = by_id(tree)[tree.line_end]
    if color == chess.WHITE:
        # 3. Bc4 — ход ученика, дальше отвечает соперник: Bc5 / Nf6 / Be7 (≥ 10%).
        assert [r.uci for r in kids(tree, end)] == ["f8c5", "g8f6", "f8e7"]
    else:
        # За чёрных — один ход: 3… Bc5 (60 партий из 100).
        assert [k.uci for k in kids(tree, end)] == ["f8c5"]
        assert kids(tree, end)[0].stats is not None
    # Дальше исходной линии у каждой карточки тренажёра есть узел с идеями на пути.
    for node in card_nodes(tree):
        if node.ply >= end.ply:
            assert ideas_node_id(tree, node.id) is not None


async def test_node_budget_spends_main_line_first() -> None:
    # Линия — 11 узлов, самая вероятная линия дальше — ещё 14 + две соседние ветки 6-го хода.
    limits = BuildLimits(target_plies=24, max_nodes=30)
    tree = await build(NAJDORF, chess.BLACK, NAJDORF_GAMES, limits=limits)

    assert len(tree.nodes) == 30
    # Самая вероятная линия (по первому ребёнку) доходит до цели, на остальные бюджета
    # хватает частично.
    node = by_id(tree)[tree.line_end]
    while node.children:
        node = kids(tree, node)[0]
    assert node.ply == limits.target_plies
    leaves = [n for n in tree.nodes if not n.children]
    assert any(n.ply < limits.target_plies for n in leaves)


async def test_branch_limits() -> None:
    one = BuildLimits(target_plies=20, max_nodes=60, opponent_branches=1)
    tree = await build(NAJDORF, chess.BLACK, NAJDORF_GAMES, limits=one)
    assert all(len(n.children) <= 1 for n in tree.nodes)

    strict = BuildLimits(target_plies=20, max_nodes=60, min_share=0.35)
    tree = await build(NAJDORF, chess.BLACK, NAJDORF_GAMES, limits=strict)
    assert [r.uci for r in kids(tree, by_id(tree)[tree.line_end])] == ["c1e3"]

    # Ни один ответ не набрал долю — берётся самый популярный.
    tiny = BuildLimits(target_plies=20, max_nodes=60, min_share=0.9)
    tree = await build(NAJDORF, chess.BLACK, NAJDORF_GAMES, limits=tiny)
    assert [r.uci for r in kids(tree, by_id(tree)[tree.line_end])] == ["c1e3"]


async def test_bad_master_move_replaced_by_engine_best() -> None:
    # После 6. Be2 e5 движок даёт белым (на ходу) +400: e5 у мастеров — заметно хуже.
    after_be2 = board_after(NAJDORF + " f1e2")
    after_e5 = board_after(NAJDORF + " f1e2 e7e5")
    engine = FakeEngine(scores={fen_key(after_e5): 400}, best={fen_key(after_be2): "e7e6"})

    tree = await build(NAJDORF, chess.BLACK, NAJDORF_GAMES, engine=engine)

    be2 = next(r for r in kids(tree, by_id(tree)[tree.line_end]) if r.uci == "f1e2")
    assert [k.uci for k in kids(tree, be2)] == ["e7e6"]
    # Ход движка, которого нет у мастеров, — без статистики.
    assert kids(tree, be2)[0].stats is None


async def test_small_loss_keeps_master_move() -> None:
    # Потеря 2 пункта win% — в пределах порога 5: остаётся ход мастеров.
    after_e5 = board_after(NAJDORF + " f1e2 e7e5")
    engine = FakeEngine(scores={fen_key(after_e5): 20})

    tree = await build(NAJDORF, chess.BLACK, NAJDORF_GAMES, engine=engine)

    be2 = next(r for r in kids(tree, by_id(tree)[tree.line_end]) if r.uci == "f1e2")
    assert [k.uci for k in kids(tree, be2)] == ["e7e5"]


async def test_second_popular_move_when_first_fails() -> None:
    # 6. Bg5: e6 (25) плох, Nbd7 (5 из 30 — 17% ≥ 10%) проходит.
    after_e6 = board_after(NAJDORF + " c1g5 e7e6")
    tree = await build(
        NAJDORF, chess.BLACK, NAJDORF_GAMES, engine=FakeEngine(scores={fen_key(after_e6): 500})
    )
    bg5 = next(r for r in kids(tree, by_id(tree)[tree.line_end]) if r.uci == "c1g5")
    assert [k.uci for k in kids(tree, bg5)] == ["b8d7"]


async def test_without_master_data_engine_only() -> None:
    engine = FakeEngine()
    tree = await build(NAJDORF, chess.BLACK, [], engine=engine)

    assert_well_formed(tree, NAJDORF, chess.BLACK)
    # Одна линия движка до цели, без статистики мастеров.
    assert all(len(n.children) <= 1 for n in tree.nodes)
    assert len(tree.nodes) == LIMITS.target_plies + 1
    assert all(n.stats is None for n in tree.nodes)
    assert all(n.weight == 1.0 for n in tree.nodes)
    assert tree.model_games == []


async def test_key_moments() -> None:
    tree = await build(NAJDORF, chess.BLACK, NAJDORF_GAMES)
    index = by_id(tree)
    openings = default_openings()

    reasons = {n.key_moment for n in tree.nodes} - {None}
    assert reasons == {"book_exit", "structure", "line_end"}
    for node in tree.nodes:
        parent = index[node.parent] if node.parent is not None else None
        if node.key_moment == "book_exit":
            assert parent is not None
            assert parent.book
            assert not node.book
            assert not openings.contains(chess.Board(node.fen))
        if node.key_moment == "structure":
            assert node.ideas is not None
            assert node.ideas.structures
            assert parent is not None
            assert parent.ideas is None or parent.ideas.structures != node.ideas.structures
        if not node.children:
            assert node.key_moment is not None  # конец линии курса
    # 6. Be3 e5 — сицилианская структура d6–e5 появилась и держится.
    be3_e5 = kids(tree, kids(tree, index[tree.line_end])[0])[0]
    assert be3_e5.uci == "e7e5"
    assert be3_e5.ideas is not None
    assert "sicilian_d6_e5" in be3_e5.ideas.structures


async def test_model_games_from_key_nodes() -> None:
    explorer = GamesExplorer(NAJDORF_GAMES)
    tree = await build(NAJDORF, chess.BLACK, NAJDORF_GAMES, explorer=explorer)
    index = by_id(tree)

    assert 0 < len(tree.model_games) <= MAX_MODEL_GAMES
    assert len({g.id for g in tree.model_games}) == len(tree.model_games)
    for game in tree.model_games:
        node = index[game.node_id]
        assert node.key_moment is not None
        assert explorer.passes(game.id, chess.Board(node.fen))
        assert game.pgn.startswith("[White")
    # Глубже — раньше.
    plies = [index[g.node_id].ply for g in tree.model_games]
    assert plies == sorted(plies, reverse=True)


async def test_model_game_download_failure_skips_game() -> None:
    explorer = GamesExplorer(NAJDORF_GAMES, fail_games=True)
    tree = await build(NAJDORF, chess.BLACK, NAJDORF_GAMES, explorer=explorer)
    assert tree.model_games == []
    assert explorer.game_calls


async def test_explorer_failure_propagates() -> None:
    with pytest.raises(ExplorerUnavailableError):
        await build(NAJDORF, chess.BLACK, [], explorer=GamesExplorer([], fail=True))


async def test_long_line_extends_target() -> None:
    games = NAJDORF_GAMES[:1]
    line = games[0][0]
    limits = BuildLimits(target_plies=10, max_nodes=60)
    tree = await build(line, chess.BLACK, games, limits=limits)
    assert by_id(tree)[tree.line_end].ply == 22
    assert max(n.ply for n in tree.nodes) == 22 + builder_module.MIN_BEYOND_PLIES


async def test_progress_and_eval_cache() -> None:
    seen: list[int] = []

    async def progress(percent: int) -> None:
        seen.append(percent)

    cache = MemoryEvalCache()
    engine = FakeEngine()
    builder = CourseBuilder(
        GamesExplorer(ITALIAN_GAMES), engine, limits=LIMITS, cache=cache, progress=progress
    )
    first = await builder.build(parse_line(ITALIAN.split()), chess.WHITE)
    assert seen == sorted(set(seen))
    assert seen[-1] == 100
    calls = engine.calls
    assert calls > 0
    assert len(cache) > 0

    # Вторая сборка с тем же кэшем — без движка, то же дерево.
    again = CourseBuilder(GamesExplorer(ITALIAN_GAMES), engine, limits=LIMITS, cache=cache)
    second = await again.build(parse_line(ITALIAN.split()), chess.WHITE)
    assert engine.calls == calls
    assert second == first


async def test_node_eval_white_pov() -> None:
    # Позиция после 1. e4: на ходу чёрные, движок даёт им −30 → глазами белых +30.
    after_e4 = board_after("e2e4")
    tree = await build("e2e4", chess.WHITE, [], engine=FakeEngine(scores={fen_key(after_e4): -30}))
    node = by_id(tree)[1]
    assert node.eval is not None
    assert node.eval.cp == 30
    assert node.eval.mate is None
    assert node.eval.best_uci is not None
    assert node.eval.depth == LIMITS.engine_depth


def test_parse_line() -> None:
    assert [m.uci() for m in parse_line(["e2e4", "E7E5"])] == ["e2e4", "e7e5"]
    # Рокировка «король берёт ладью» → обычная запись.
    line = ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5", "e1h1"]
    assert parse_line(line)[-1].uci() == "e1g1"
    with pytest.raises(LineError) as exc:
        parse_line(["e2e4", "e2e4"])
    assert exc.value.index == 1
    with pytest.raises(LineError) as exc:
        parse_line(["zz"])
    assert exc.value.index == 0
    with pytest.raises(LineError):
        parse_line([])
    with pytest.raises(LineError):
        parse_line(["g1f3", "g8f6", "f3g1", "f6g8"] * (MAX_LINE_PLIES // 4 + 1))


def test_course_key(monkeypatch: pytest.MonkeyPatch) -> None:
    line = parse_line(NAJDORF.split())
    key = course_key(chess.BLACK, line)
    assert len(key) == 64
    assert course_key(chess.BLACK, parse_line(NAJDORF.split())) == key
    assert course_key(chess.WHITE, line) != key
    assert course_key(chess.BLACK, line[:-1]) != key
    # e1h1 и e1g1 — одна линия.
    castle = "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5"
    assert course_key(chess.WHITE, parse_line((castle + " e1h1").split())) == course_key(
        chess.WHITE, parse_line((castle + " e1g1").split())
    )
    monkeypatch.setattr(builder_module, "BUILDER_VERSION", 99)
    assert course_key(chess.BLACK, line) != key
