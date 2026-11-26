"""Классификация на синтетических оценках: пороги и порядок проверок §4.5."""

import dataclasses

import chess
import pytest
from chess.engine import Cp, Mate, Score

from app.review.classify import (
    classify_game,
    classify_move,
    is_great,
    is_obvious,
    is_recapture,
    outcome,
    reply_line,
)
from app.review.evaluate import MoveEval, evaluate_game
from app.review.openings import default_openings
from app.review.types import EngineLine, MoveClass, PositionEval
from app.review.winprob import win_percent

OPERA_13 = "3rkb1r/p2nqppp/5n2/1B2p1B1/4P3/1Q6/PPP2PPP/2KR3R w k - 3 13"
# Единственный легальный ход — Kxg2.
ONE_MOVE = "k7/8/8/8/8/8/6q1/7K w - - 0 1"


def line(score: Score, *pv: str) -> EngineLine:
    return EngineLine(score=score, pv=tuple(chess.Move.from_uci(m) for m in pv))


def move_eval(
    fen: str,
    move: str,
    before: tuple[EngineLine, ...],
    after: tuple[EngineLine, ...] = (),
    *,
    after_score: Score | None = None,
) -> MoveEval:
    """Ход из позиции `fen`; оценки — с точки зрения ходящего в каждой позиции."""
    start = chess.Board(fen)
    score_after = after[0].score if after else after_score
    assert score_after is not None
    evals = [
        PositionEval(score=before[0].score, lines=before, depth=18),
        PositionEval(score=score_after, lines=after, depth=18),
    ]
    (result,) = evaluate_game(start, [chess.Move.from_uci(move)], evals).moves
    return result


def with_delta(move: MoveEval, delta: float, win_before: float = 60.0) -> MoveEval:
    return dataclasses.replace(move, win_before=win_before, win_after=win_before - delta)


@pytest.fixture
def quiet_move() -> MoveEval:
    """1. e4 при лучшем d4: не лучший ход, без жертв."""
    return move_eval(chess.STARTING_FEN, "e2e4", (line(Cp(30), "d2d4"),), (line(Cp(-30), "e7e5"),))


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (0.0, MoveClass.BEST),
        (0.5, MoveClass.BEST),
        (0.51, MoveClass.EXCELLENT),
        (2.0, MoveClass.EXCELLENT),
        (2.01, MoveClass.GOOD),
        (5.0, MoveClass.GOOD),
        (5.01, MoveClass.INACCURACY),
        (10.0, MoveClass.INACCURACY),
        (10.01, MoveClass.MISTAKE),
        (20.0, MoveClass.MISTAKE),
        (20.01, MoveClass.BLUNDER),
        (60.0, MoveClass.BLUNDER),
    ],
)
def test_delta_thresholds(quiet_move: MoveEval, delta: float, expected: MoveClass) -> None:
    assert classify_move(with_delta(quiet_move, delta)).move_class is expected


def test_win_gain_counts_as_zero_loss(quiet_move: MoveEval) -> None:
    # Не первый ход движка, но не хуже его — тоже «лучший», как у Chess.com.
    assert classify_move(with_delta(quiet_move, -15)).move_class is MoveClass.BEST


def test_best_move() -> None:
    move = move_eval(
        chess.STARTING_FEN, "e2e4", (line(Cp(30), "e2e4", "e7e5"),), after_score=Cp(-30)
    )
    assert classify_move(move).move_class is MoveClass.BEST


def test_great_only_move() -> None:
    lines = (line(Cp(100), "e2e4"), line(Cp(-200), "d2d4"))
    move = move_eval(chess.STARTING_FEN, "e2e4", lines, after_score=Cp(-100))
    assert win_percent(Cp(100)) - win_percent(Cp(-200)) >= 20
    assert classify_move(move).move_class is MoveClass.GREAT


def test_not_great_when_second_is_only_a_mistake() -> None:
    # Второй вариант хуже на ~13 win% — ошибка, но не зевок: лучший ход не единственный.
    lines = (line(Cp(50), "e2e4"), line(Cp(-60), "d2d4"))
    move = move_eval(chess.STARTING_FEN, "e2e4", lines, after_score=Cp(-50))
    assert 10 <= win_percent(Cp(50)) - win_percent(Cp(-60)) < 20
    assert classify_move(move).move_class is MoveClass.BEST
    # Но если соперник только что ошибся, единственный способ наказать — «великолепный».
    punish = classify_move(move, previous=MoveClass.MISTAKE)
    assert punish.move_class is MoveClass.GREAT


@pytest.mark.parametrize(
    ("best", "second", "great"),
    [
        (Cp(400), Cp(150), True),  # выигрыш против ничьей
        (Cp(-150), Cp(-400), True),  # ничья против проигрыша
        (Cp(400), Cp(350), False),  # граница результата, но разница — 3 win%
        (Cp(300), Cp(150), False),  # оба — ничья
        (Mate(3), Mate(5), False),  # оба — выигрыш
    ],
)
def test_great_outcome_change(best: Score, second: Score, great: bool) -> None:
    lines = (line(best, "e2e4"), line(second, "d2d4"))
    move = move_eval(chess.STARTING_FEN, "e2e4", lines, after_score=-best)
    assert win_percent(best) - win_percent(second) < 20
    assert is_great(move) is great
    assert classify_move(move).move_class is (MoveClass.GREAT if great else MoveClass.BEST)


def test_outcome_thresholds() -> None:
    assert [outcome(w) for w in (19.9, 20, 50, 80, 80.1)] == [-1, 0, 0, 0, 1]


def test_book_and_forced_come_first(quiet_move: MoveEval) -> None:
    blunder = with_delta(quiet_move, 40)
    assert classify_move(blunder, in_book=True).move_class is MoveClass.BOOK
    late = dataclasses.replace(blunder, fullmove=16)
    assert classify_move(late, in_book=True).move_class is MoveClass.BLUNDER
    last = dataclasses.replace(blunder, fullmove=15)
    assert classify_move(last, in_book=True).move_class is MoveClass.BOOK

    forced = move_eval(ONE_MOVE, "h1g2", (line(Cp(0), "h1g2"),), after_score=Cp(0))
    assert classify_move(forced).move_class is MoveClass.FORCED
    assert classify_move(forced, in_book=True).move_class is MoveClass.BOOK


def rxd7(cp: int = 800) -> MoveEval:
    """13. Rxd7 Rxd7 14. Rd1 из Оперы Морфи; оценка до и после хода — `cp`."""
    return move_eval(
        OPERA_13,
        "d1d7",
        (line(Cp(cp), "d1d7", "d8d7", "h1d1"),),
        (line(Cp(-cp), "d8d7", "h1d1"),),
    )


def test_brilliant_sacrifice() -> None:
    result = classify_move(rxd7())
    assert result.move_class is MoveClass.BRILLIANT
    assert result.sacrifice is not None
    assert result.sacrifice.squares == (chess.D7,)


def test_brilliant_conditions() -> None:
    # Уже подавляющий выигрыш (win% ≥ 97) — не brilliant, хотя жертва есть.
    crushing = classify_move(rxd7(1000))
    assert crushing.move_class is MoveClass.BEST
    assert crushing.sacrifice is not None
    # Хуже −1.0 после хода — не brilliant.
    assert classify_move(rxd7(-150)).move_class is MoveClass.BEST
    assert classify_move(rxd7(-100)).move_class is MoveClass.BRILLIANT


def test_brilliant_when_not_best_but_close() -> None:
    # Лучший — другой ход, но Δ ≤ 2: жертва ищется в PV позиции после хода.
    move = move_eval(
        OPERA_13,
        "d1d7",
        (line(Cp(810), "b5d7", "f6d7"),),
        (line(Cp(-790), "d8d7", "h1d1"),),
    )
    assert reply_line(move) == move.lines_after[0].pv
    assert classify_move(move).move_class is MoveClass.BRILLIANT

    far = dataclasses.replace(move, win_after=move.win_before - 3)
    assert classify_move(far).move_class is MoveClass.GOOD


def test_reply_line_without_engine_lines() -> None:
    move = move_eval(OPERA_13, "d1d7", (line(Cp(800)),), after_score=Cp(-800))
    assert reply_line(move) == ()
    assert classify_move(move).sacrifice is None


def test_miss_flag(quiet_move: MoveEval) -> None:
    def miss(previous: MoveClass | None, delta: float) -> bool:
        return classify_move(with_delta(quiet_move, delta), previous=previous).is_miss

    assert miss(MoveClass.BLUNDER, 12)
    assert miss(MoveClass.MISTAKE, 10)
    assert miss(MoveClass.MISTAKE, 30)
    assert not miss(MoveClass.BLUNDER, 9.9)
    assert not miss(MoveClass.INACCURACY, 30)
    assert not miss(None, 30)
    # Позицию проиграл (win% после хода < 30) — это зевок, а не упущение.
    assert not miss(MoveClass.MISTAKE, 31)
    # Ошибка соперника не дала шанса (win% при лучшей игре < 60) — упускать нечего.
    small = classify_move(with_delta(quiet_move, 12, win_before=55), previous=MoveClass.BLUNDER)
    assert not small.is_miss
    result = classify_move(with_delta(quiet_move, 12), previous=MoveClass.BLUNDER)
    assert result.move_class is MoveClass.MISTAKE


def test_recapture_is_never_great() -> None:
    # 1. e4 d5 2. exd5 Qxd5: взятие в ответ — «лучший», даже если остальное проигрывает.
    board = chess.Board()
    for san in ("e4", "d5"):
        board.push_san(san)
    prior = board.copy()
    exd5 = board.push_san("exd5")
    lines = (line(Cp(0), "d8d5"), line(Cp(-300), "g8f6"))
    move = move_eval(board.fen(), "d8d5", lines, after_score=Cp(0))
    assert is_great(move)
    result = classify_move(move, prior=prior, previous_move=exd5)
    assert result.move_class is MoveClass.BEST
    assert is_recapture(chess.Board(board.fen()), move.move, prior, exd5)


def test_taking_free_material_is_never_great() -> None:
    # 1. e4 e5 2. Nf3 Qh4?? 3. Nxh4: ферзь подставлен — взять его может каждый.
    board = chess.Board()
    for san in ("e4", "e5", "Nf3", "Qh4"):
        board.push_san(san)
    lines = (line(Cp(900), "f3h4"), line(Cp(40), "b1c3"))
    move = move_eval(board.fen(), "f3h4", lines, after_score=Cp(-900))
    assert is_great(move)
    assert is_obvious(chess.Board(board.fen()), move.move)
    assert classify_move(move, previous=MoveClass.BLUNDER).move_class is MoveClass.BEST
    # Мат взятием (детский мат) — не «очевидный» ход.
    scholar = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4")
    assert not is_obvious(scholar, chess.Move.from_uci("h5f7"))


def test_classify_game_chains_book_previous_and_prior() -> None:
    # 1. e4 e5 2. Nf3 Qh4?? 3. d3?? — ферзь висит, белые не берут.
    board = chess.Board()
    moves = [board.push_san(san) for san in ("e4", "e5", "Nf3", "Qh4", "d3")]
    evals = [
        PositionEval(score=Cp(30), lines=(line(Cp(30), "e2e4"),)),
        PositionEval(score=Cp(-30), lines=(line(Cp(-30), "e7e5"),)),
        PositionEval(score=Cp(40), lines=(line(Cp(40), "g1f3"),)),
        PositionEval(score=Cp(-40), lines=(line(Cp(-40), "b8c6"),)),
        PositionEval(score=Cp(900), lines=(line(Cp(900), "f3h4"),)),
        PositionEval(score=Cp(-50), lines=(line(Cp(-50), "h4e4"),)),
    ]
    result = evaluate_game(chess.Board(), moves, evals)

    classes = classify_game(result.moves, default_openings())
    assert [c.move_class for c in classes] == [
        MoveClass.BOOK,
        MoveClass.BOOK,
        MoveClass.BOOK,
        MoveClass.BLUNDER,
        MoveClass.BLUNDER,
    ]
    assert [c.is_miss for c in classes] == [False, False, False, False, True]

    # Без книги первые ходы — лучшие.
    no_book = classify_game(result.moves)
    assert [c.move_class for c in no_book[:3]] == [MoveClass.BEST] * 3
