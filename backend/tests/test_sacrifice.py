import chess

from app.review.sacrifice import Sacrifice, find_sacrifice, offered_pieces

GREEK_GIFT = "rnbq1rk1/pppn1ppp/4p3/3pP3/1b1P4/2NB1N2/PPP2PPP/R1BQK2R w KQ - 0 7"
# Ладья d5 висит под слоном f7; ход белых.
ROOK_HANGS = "7k/5b2/8/3R4/8/8/5PPP/6K1 w - - 1 2"


def uci(*moves: str) -> list[chess.Move]:
    return [chess.Move.from_uci(m) for m in moves]


def sacrifice(fen: str, move: str, *pv: str, prior: str | None = None) -> Sacrifice | None:
    board = chess.Board(fen)
    return find_sacrifice(
        board,
        chess.Move.from_uci(move),
        uci(*pv),
        chess.Board(prior) if prior is not None else None,
    )


def test_greek_gift_is_a_sacrifice() -> None:
    # Bxh7+ Kxh7 Ng5+: слон за пешку.
    assert sacrifice(GREEK_GIFT, "d3h7", "g8h7", "f3g5", "h7g8", "d1h5") == Sacrifice(
        squares=(chess.H7,), material_drop=2
    )


def test_exchange_sacrifice() -> None:
    # Опера Морфи, 13. Rxd7 Rxd7 14. Rd1: ладья за коня.
    opera = "3rkb1r/p2nqppp/5n2/1B2p1B1/4P3/1Q6/PPP2PPP/2KR3R w k - 3 13"
    assert sacrifice(opera, "d1d7", "d8d7", "h1d1") == Sacrifice(
        squares=(chess.D7,), material_drop=2
    )


def test_declined_or_late_acceptance_is_not_a_sacrifice() -> None:
    assert sacrifice(GREEK_GIFT, "d3h7", "g8h8", "d1e2") is None
    # Соперник берёт только третьим своим ходом.
    assert sacrifice(GREEK_GIFT, "d3h7", "g8h8", "d1e2", "a7a6", "e2d1", "h8h7") is None


def test_trade_is_not_a_sacrifice() -> None:
    # Bxc6 dxc6 — размен слона на коня.
    ruy = "r1bqkbnr/1ppp1ppp/p1n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4"
    assert offered_pieces(chess.Board(ruy), chess.Move.from_uci("b5c6")) == [chess.C6]
    assert sacrifice(ruy, "b5c6", "d7c6") is None


def test_pawn_sacrifice_does_not_count() -> None:
    kings_gambit = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    assert sacrifice(kings_gambit, "f2f4", "e5f4") is None


def test_loss_is_counted_after_the_exchange_on_the_square() -> None:
    # Nd5 exd5 exd5: конь за пешку — минус 2, а не минус 3 сразу после взятия.
    fen = "rnbqkb1r/pppp1ppp/4pn2/8/4P3/2N5/PPPP1PPP/R1BQKBNR w KQkq - 0 3"
    assert sacrifice(fen, "c3d5", "e6d5", "e4d5", "f8e7") == Sacrifice(
        squares=(chess.D5,), material_drop=2
    )


def test_piece_hanging_before_opponent_move_is_not_a_new_sacrifice() -> None:
    stale = "6k1/5b2/8/3R4/8/8/5PPP/6K1 b - - 0 1"  # ладья уже висела
    fresh = "4b1k1/8/8/3R4/8/8/5PPP/6K1 b - - 0 1"  # угрозу создал ход Bf7

    assert sacrifice(ROOK_HANGS, "h2h3", "f7d5", prior=stale) is None
    assert sacrifice(ROOK_HANGS, "h2h3", "f7d5", prior=fresh) == Sacrifice(
        squares=(chess.D5,), material_drop=5
    )
    # Без истории — считается.
    assert sacrifice(ROOK_HANGS, "h2h3", "f7d5") is not None


def test_illegal_pv_is_cut() -> None:
    assert sacrifice(GREEK_GIFT, "d3h7", "a1a8") is None
