import chess
import pytest

from app.review.material import best_capture_gain, material, material_balance, see


def see_san(fen: str, san: str) -> int:
    board = chess.Board(fen)
    return see(board, board.parse_san(san))


def test_material_and_balance() -> None:
    board = chess.Board()
    assert material(board, chess.WHITE) == 39
    assert material_balance(board, chess.BLACK) == 0

    board = chess.Board("4k3/8/8/8/8/8/PP6/R3K3 w - - 0 1")
    assert material_balance(board, chess.WHITE) == 7
    assert material_balance(board, chess.BLACK) == -7


@pytest.mark.parametrize(
    ("fen", "san", "expected"),
    [
        # Незащищённая фигура — выигрыш целиком.
        ("4k3/8/8/3n4/8/8/8/3RK3 w - - 0 1", "Rxd5", 3),
        # Ладья за коня, защищённого пешкой.
        ("4k3/8/4p3/3n4/8/8/8/3RK3 w - - 0 1", "Rxd5", -2),
        # Ферзь за защищённую пешку.
        ("4k3/8/4p3/3p4/8/8/8/3QK3 w - - 0 1", "Qxd5", -8),
        # Сдвоенные ладьи: задняя бьёт рентгеном после размена.
        ("3rk3/8/8/3p4/8/8/3R4/3RK3 w - - 0 1", "Rxd5", 1),
        ("3rk3/8/8/3p4/8/8/3R4/4K3 w - - 0 1", "Rxd5", -4),
        # Защитник связан с королём — отбить нельзя.
        ("4k3/3n4/8/1B2p3/8/5N2/8/4K3 w - - 0 1", "Nxe5", 1),
        ("4k3/3n4/8/4p3/8/5N2/8/4K3 w - - 0 1", "Nxe5", -2),
        # Король отбивает, только если поле не защищено.
        ("4k3/5p2/8/8/2B5/8/8/4KQ2 w - - 0 1", "Qxf7+", 1),
        ("4k3/5p2/8/8/8/8/8/4KQ2 w - - 0 1", "Qxf7+", -8),
        # Взятие на проходе и взятие с превращением.
        ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", "exd6", 1),
        ("r3k3/1P6/8/8/8/8/8/4K3 w - - 0 1", "bxa8=Q+", 13),
        # Не взятие: фигура встаёт под бой пешки.
        ("4k3/8/4p3/8/8/2N5/8/4K3 w - - 0 1", "Nd5", -3),
    ],
)
def test_see(fen: str, san: str, expected: int) -> None:
    assert see_san(fen, san) == expected


def test_best_capture_gain() -> None:
    board = chess.Board("4k3/8/4p3/3n4/8/8/8/3RK3 w - - 0 1")
    assert best_capture_gain(board, chess.D5) == 0  # Rxd5 невыгодно
    assert best_capture_gain(board, chess.E6) == 0  # взять нечем

    board = chess.Board("4k3/8/8/3n4/8/4P3/8/3RK3 w - - 0 1")
    assert best_capture_gain(board, chess.D5) == 3
