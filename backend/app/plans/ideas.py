"""Идеи позиции (сессия 13): `position_ideas(board)` собирает факты о пешках, типовые
структуры и прорывы в `PositionIdeas` — ключи планов с параметрами (клетки, ходы).

Сначала идут планы распознанных структур (для первых `MAX_STRUCTURES`), у каждой — план
владельца структуры раньше плана соперника: по первой идее с ключом `«структура».…`
шаблоны узнают владельца. Дальше — общие идеи из фактов (разносторонние рокировки,
укрытие короля, проходная, подрыв цепи, прорывы, форпосты, конь на краю, 7-я
горизонталь, слабости, открытые линии, слоны). Общая идея
пропускается, если её клетку уже разбирает план структуры. На сторону — не больше
`MAX_IDEAS_PER_SIDE` пунктов, без воды.

Ходы в параметрах: `san` — легальный ход (см. `breaks.py`), `move` — цель подготовки
в виде «c7–c5» из клеток фактов.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

import chess

from app.plans.breaks import as_mover, pawn_breaks, side_name
from app.plans.pawns import (
    PawnFacts,
    PawnView,
    is_dark,
    is_fixed,
    pawn_can_attack,
    pawn_facts,
    rel_rank,
    square_at,
)
from app.plans.structures import Match, StructureId, recognize
from app.plans.types import Idea, Outpost, PawnBreak, PositionIdeas, Weakness

MAX_STRUCTURES = 2
MAX_IDEAS_PER_SIDE = 4

_PIECE_LETTERS = {chess.KNIGHT: "N", chess.BISHOP: "B"}
_FIANCHETTO = {chess.B2: chess.H8, chess.G2: chess.A8}  # поле слона белых → угол диагонали


def _sq(square: chess.Square) -> str:
    return chess.square_name(square)


def _join(squares: Iterable[chess.Square]) -> str:
    return ",".join(_sq(s) for s in squares)


def _coords(start: chess.Square, end: chess.Square) -> str:
    return f"{_sq(start)}–{_sq(end)}"


def _move_params(brk: PawnBreak) -> dict[str, str]:
    if brk.legal_now and brk.san is not None:
        return {"san": brk.san}
    move = chess.Move.from_uci(brk.uci)
    return {"move": _coords(move.from_square, move.to_square)}


@dataclass(slots=True)
class _Draft:
    idea: Idea
    weight: int
    # Клетки, которые эта идея уже разбирает: общие идеи той же стороны про них
    # пропускаются (прорыв своей пешкой, давление на пешку соперника, форпост).
    covers: frozenset[str] = field(default_factory=frozenset)


@dataclass(slots=True)
class _Context:
    board: chess.Board
    facts: PawnFacts
    breaks: list[PawnBreak]
    drafts: list[_Draft] = field(default_factory=list)

    def add(
        self,
        key: str,
        color: chess.Color,
        weight: int,
        params: dict[str, str] | None = None,
        covers: Iterable[str] = (),
    ) -> None:
        idea = Idea(key=key, side=side_name(color), params=params or {})
        self.drafts.append(_Draft(idea, weight, frozenset(covers)))

    def covered(self, square: str, color: chess.Color) -> bool:
        side = side_name(color)
        return any(square in d.covers for d in self.drafts if d.idea.side == side)

    def side_breaks(self, color: chess.Color) -> list[PawnBreak]:
        return [b for b in self.breaks if b.side == side_name(color)]

    def push_break(self, color: chess.Color, start: chess.Square, dest: chess.Square) -> str:
        """Ход пешкой start → dest для текста: SAN, если прорыв готов, иначе «d4–d5»."""
        uci = chess.Move(start, dest).uci()
        for brk in self.side_breaks(color):
            if brk.uci == uci and brk.legal_now and brk.san is not None:
                return brk.san
        return _coords(start, dest)


def _move_param(text: str) -> dict[str, str]:
    """SAN без «–» — легальный ход; координаты «d4–d5» — цель подготовки."""
    return {"move": text} if "–" in text else {"san": text}


# --- Планы структур ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Plan:
    """Всё, что нужно планам одной структуры: владелец `own`, соперник `opp`, их пешки
    (`you`, `them`), параметры распознавания `p` и вес `base` (план владельца — первым).
    Параметры первого плана владельца заодно дают заголовок и описание структуры."""

    ctx: _Context
    key: str
    p: dict[str, str]
    own: chess.Color
    you: PawnView
    them: PawnView
    base: int

    @property
    def opp(self) -> chess.Color:
        return not self.own

    def add(
        self,
        plan: str,
        mine: bool,
        params: dict[str, str] | None = None,
        covers: Iterable[str] = (),
        step: int = 0,
    ) -> None:
        color = self.own if mine else self.opp
        self.ctx.add(f"{self.key}.{plan}", color, self.base - step, params, covers)

    def push(self, mine: bool, start: str | chess.Square, rel: int) -> dict[str, str]:
        """Параметр хода: пешка `start` идёт по своей вертикали на горизонталь `rel`."""
        color, view = (self.own, self.you) if mine else (self.opp, self.them)
        square = chess.parse_square(start) if isinstance(start, str) else start
        dest = view.square(chess.square_file(square), rel)
        return _move_param(self.ctx.push_break(color, square, dest))


def _isolani(s: _Plan) -> None:
    pawn = s.p["pawn"]
    attacks = chess.SquareSet(chess.BB_PAWN_ATTACKS[s.own][chess.parse_square(pawn)])
    s.add("activity", True, {"pawn": pawn, "squares": _join(attacks)}, covers={pawn})
    s.add("break", True, {"pawn": pawn, **s.push(True, pawn, 5)}, covers={pawn}, step=1)
    s.add(
        "blockade",
        False,
        {"pawn": pawn, "square": s.p["square"]},
        covers={s.p["square"], pawn},
        step=2,
    )
    s.add("trade", False, {"pawn": pawn}, step=3)


def _hanging(s: _Plan) -> None:
    covers = set(s.p["pawns"].split(","))
    s.add("advance", True, {"pawns": s.p["pawns"]}, covers=covers)
    s.add("pressure", False, {"pawns": s.p["pawns"]}, covers=covers, step=1)


def _carlsbad(s: _Plan) -> None:
    p = s.p
    to = _sq(s.you.square("b", 5))
    s.add(
        "minority",
        True,
        {"pawn": p["pawn"], "target": p["target"], "to": to},
        covers={p["pawn"], p["target"]},
    )
    e_pawn = chess.parse_square(p["e"])
    # План e3–e4 (Ботвинник) — у белых в ферзевом гамбите; в Каро-Канн его нет.
    if s.own == chess.WHITE and rel_rank(s.own, e_pawn) == 3 and s.you.has("f", 2, 3):
        s.add("center", True, {"pawn": p["e"], **s.push(True, e_pawn, 4)}, covers={p["e"]}, step=1)
    s.add(
        "kingside",
        False,
        {"square": p["square"], "support": p["support"]},
        covers={p["square"]},
        step=2,
    )


def _hedgehog(s: _Plan) -> None:
    b_to, d_to = s.you.square("b", 4), s.you.square("d", 4)
    s.add(
        "breaks",
        True,
        {"b_break": f"{s.p['b']}–{_sq(b_to)}", "d_break": f"{s.p['d']}–{_sq(d_to)}"},
        covers={s.p["b"], s.p["d"]},
    )
    s.add("squeeze", False, {"squares": _join((b_to, d_to))}, step=1)


def _maroczy(s: _Plan) -> None:
    pawns = f"{s.p['c']},{s.p['e']}"
    s.add("bind", True, {"pawns": pawns, "square": _sq(s.you.square("d", 5))})
    s.add("counter", False, {"pawns": pawns}, step=1)


def _scheveningen(s: _Plan) -> None:
    d = s.p["d"]
    s.add("counter", True, {"pawns": f"{d},{s.p['e']}", **s.push(True, d, 4)}, covers={d})
    e = s.them.square("e", 4)
    s.add(
        "attack",
        False,
        {"pawn": _sq(e), "target": d, **s.push(False, e, 5)},
        covers={_sq(e)},
        step=1,
    )


def _kan_taimanov(s: _Plan) -> None:
    pawn, hole = s.p["pawn"], s.p["hole"]
    s.add("counter", True, {"pawn": pawn, "hole": hole, **s.push(True, pawn, 4)}, covers={pawn})
    e = s.them.square("e", 4)
    s.add(
        "space",
        False,
        {"hole": hole, "move": _coords(e, s.them.square("e", 5))},
        covers={hole},
        step=1,
    )


def _sicilian_d6_e5(s: _Plan) -> None:
    pawn, hole = s.p["pawn"], s.p["hole"]
    e = _sq(s.you.square("e", 4))
    s.add(
        "d5_break",
        True,
        {"pawn": pawn, "hole": hole, "e": e, **s.push(True, pawn, 4)},
        covers={pawn},
    )
    board = s.ctx.board
    defenders = [
        f"{_PIECE_LETTERS[piece]}{_sq(square)}"
        for square in sorted(board.attackers(s.own, chess.parse_square(hole)))
        if (piece := board.piece_type_at(square)) in _PIECE_LETTERS
    ]
    if defenders:
        s.add("d5", False, {"square": hole, "pieces": ",".join(defenders)}, covers={hole}, step=1)
    else:
        s.add("d5_plain", False, {"square": hole}, covers={hole}, step=1)


def _french_chain(s: _Plan) -> None:
    s.add("kingside", True, {"pawn": s.p["e"], "d": s.p["d"], "e": s.p["e"]})
    s.add("queenside", False, {"base": s.p["d"]}, step=1)


def _kid_closed(s: _Plan) -> None:
    chain = f"{s.p['e']}–{s.p['d']}"
    opp_chain = f"{_sq(s.them.square('d', 3))}–{_sq(s.them.square('e', 4))}"
    s.add("queenside", True, {"chain": chain, "opp_chain": opp_chain})
    s.add("kingside", False, {"chain": opp_chain, "target": s.p["e"]}, step=1)


def _benoni(s: _Plan) -> None:
    p = s.p
    params = {
        "pawn": p["pawn"],
        "to": _sq(s.you.square("e", 5)),
        "target": p["target"],
        "d": _sq(s.you.square("d", 5)),
    }
    s.add("center", True, params, covers={p["pawn"]})
    s.add("queenside", False, step=1)


def _stonewall(s: _Plan) -> None:
    p = s.p
    s.add(
        "outpost",
        True,
        {"square": p["square"], "support": p["support"], "hole": p["hole"]},
        covers={p["square"]},
    )
    s.add("hole", False, {"square": p["hole"]}, covers={p["hole"]}, step=1)


def _london(s: _Plan) -> None:
    p = s.p
    s.add(
        "plan",
        True,
        {"bishop": p["bishop"], "square": p["square"], "pawn": p["pawn"]},
        covers={p["square"]},
    )
    s.add("counter", False, {"pawn": p["pawn"], "bishop": p["bishop"]}, step=1)
    board = s.ctx.board
    white_pawn, white_bishop = (
        chess.Piece(chess.PAWN, chess.WHITE),
        chess.Piece(chess.BISHOP, chess.WHITE),
    )
    if board.piece_at(chess.B2) == white_pawn and board.piece_at(chess.C1) != white_bishop:
        s.add("b2", False, {"pawn": "b2"}, step=2)


def _slav(s: _Plan) -> None:
    p = s.p
    s.add("solid", True, {"support": p["support"], "pawn": p["pawn"]})
    board = s.ctx.board
    if board.piece_at(chess.C8) == chess.Piece(chess.BISHOP, chess.BLACK) and s.you.has("e", 2):
        s.add("bishop", True, {"bishop": "c8", "pawn": "e7"}, step=1)
    if s.them.has("e", 4):
        s.add("tension", False, {"pawn": _sq(s.them.square("e", 4)), "target": p["pawn"]}, step=2)
    else:
        s.add("pressure", False, {"target": p["pawn"]}, step=2)


def _caro(s: _Plan) -> None:
    p = s.p
    s.add("breaks", True, {"target": p["target"], "square": p["square"]})
    s.add(
        "space",
        False,
        {"square": p["square"], "support": p["target"]},
        covers={p["square"]},
        step=1,
    )


def _italian(s: _Plan) -> None:
    p = s.p
    s.add(
        "d4",
        True,
        {"support": p["support"], "e": p["e"], **s.push(True, p["pawn"], 4)},
        covers={p["pawn"]},
    )
    s.add(
        "d5",
        False,
        {"target": _sq(s.you.square("e", 4)), "square": p["e"], **s.push(False, p["d"], 4)},
        covers={p["d"]},
        step=1,
    )


def _scotch(s: _Plan) -> None:
    p = s.p
    s.add(
        "space",
        True,
        {"pawn": p["pawn"], "d": p["d"], **s.push(True, p["pawn"], 5)},
        covers={p["pawn"]},
    )
    s.add("free", False, {"target": p["pawn"], **s.push(False, p["d"], 4)}, covers={p["d"]}, step=1)


def _doubled_c(s: _Plan) -> None:
    pawns = s.p["pawns"]
    front = chess.parse_square(pawns.split(",")[0])
    attacks = chess.SquareSet(chess.BB_PAWN_ATTACKS[s.own][front])
    covers = set(pawns.split(","))
    s.add("owner", True, {"pawns": pawns, "squares": _join(attacks)}, covers=covers)
    s.add("target", False, {"pawns": pawns}, covers=covers, step=1)


def _big_center(s: _Plan) -> None:
    s.add("hold", True, {"pawns": s.p["pawns"]})
    s.add("undermine", False, {"pawns": s.p["pawns"]}, step=1)


_PLANS = {
    StructureId.ISOLANI: _isolani,
    StructureId.HANGING_PAWNS: _hanging,
    StructureId.CARLSBAD: _carlsbad,
    StructureId.HEDGEHOG: _hedgehog,
    StructureId.MAROCZY: _maroczy,
    StructureId.SCHEVENINGEN: _scheveningen,
    StructureId.KAN_TAIMANOV: _kan_taimanov,
    StructureId.SICILIAN_D6_E5: _sicilian_d6_e5,
    StructureId.FRENCH_CHAIN: _french_chain,
    StructureId.KID_CLOSED: _kid_closed,
    StructureId.BENONI: _benoni,
    StructureId.STONEWALL: _stonewall,
    StructureId.LONDON: _london,
    StructureId.SLAV: _slav,
    StructureId.CARO: _caro,
    StructureId.ITALIAN: _italian,
    StructureId.SCOTCH: _scotch,
    StructureId.DOUBLED_C: _doubled_c,
    StructureId.BIG_CENTER: _big_center,
}


def _structure_ideas(ctx: _Context, match: Match, base: int) -> None:
    """Планы одной структуры: сначала владельца, затем соперника (`base` — вес)."""
    key = match.id.value
    if match.owner is None:
        for color in chess.COLORS:
            if match.id == StructureId.SYMMETRIC_D:
                square = _sq(PawnView(ctx.board, color).square("d", 5))
                ctx.add(f"{key}.d_file", color, base, {"square": square}, covers={"d"})
            else:  # открытый центр
                ctx.add(f"{key}.activity", color, base, covers={"d", "e"})
        return
    own = match.owner
    plan = _Plan(
        ctx, key, match.params, own, PawnView(ctx.board, own), PawnView(ctx.board, not own), base
    )
    _PLANS[match.id](plan)


# --- Общие идеи из фактов ------------------------------------------------------------------


def _wing_of_king(board: chess.Board, color: chess.Color) -> str | None:
    king = board.king(color)
    if king is None or rel_rank(color, king) > 2:
        return None
    file = chess.square_file(king)
    if file >= 6:
        return "kingside"
    if file <= 2:
        return "queenside"
    return None


def _opposite_castling(ctx: _Context) -> None:
    wings = {color: _wing_of_king(ctx.board, color) for color in chess.COLORS}
    if None in wings.values() or wings[chess.WHITE] == wings[chess.BLACK]:
        return
    if not ctx.board.queens:
        return
    for color in chess.COLORS:
        wing = wings[not color]
        assert wing is not None
        ctx.add("opposite_castling", color, 90, {"wing": wing})


# Файлы укрытия короля по флангу: (пешка фианкетто, соседние вертикали).
_SHELTER_FILES = {"kingside": (6, (5, 7)), "queenside": (1, (0, 2))}


def _king_shelter(ctx: _Context) -> None:
    """Ослабленное укрытие рокированного короля (Ласкер, «Chess Strategy», гл. VI):
    пешка g3/g6 оставляет поля f3/h3 (f6/h6) без защиты пешек — дыры, если слона их цвета
    нет; если он ещё стоит на месте фианкетто — разменяйте его. Пешка h3/h6 — «зацепка»
    для пешечного штурма, если свой король на другом фланге. Без ферзя у атакующего атаки
    на короля нет."""
    board = ctx.board
    for defender in chess.COLORS:
        attacker = not defender
        wing = _wing_of_king(board, defender)
        if wing is None or not board.pieces(chess.QUEEN, attacker):
            continue
        g_file, sides = _SHELTER_FILES[wing]
        own = PawnView(board, defender)
        if own.ranks(g_file) == [3] and all(own.ranks(f) == [2] for f in sides):
            squares = [own.square(f, 3) for f in sides]
            if not any(
                board.piece_type_at(s) == chess.PAWN or pawn_can_attack(board, defender, s)
                for s in squares
            ):
                dark = is_dark(squares[0])
                guards = [s for s in board.pieces(chess.BISHOP, defender) if is_dark(s) == dark]
                pawn = _sq(own.square(g_file, 3))
                holes = _join(squares)
                if not guards:
                    ctx.add(
                        "king_holes",
                        attacker,
                        78,
                        {"pawn": pawn, "squares": holes},
                        covers={_sq(s) for s in squares},
                    )
                elif own.square(g_file, 2) in guards and any(
                    is_dark(s) == dark for s in board.pieces(chess.BISHOP, attacker)
                ):
                    # Ниже прорывов: в дебютных структурах (староиндийская, Бенони) это
                    # побочный план, главный — у структуры.
                    ctx.add(
                        "trade_king_bishop",
                        attacker,
                        58,
                        {"bishop": _sq(own.square(g_file, 2)), "squares": holes},
                    )
        h_file = sides[1] if wing == "kingside" else sides[0]
        if own.ranks(h_file) != [3] or own.ranks(g_file) != [2]:
            continue
        if _wing_of_king(board, attacker) == wing:
            continue  # штурм пешками перед своим королём — слишком рискованно
        theirs = PawnView(board, attacker)
        ranks = theirs.ranks(g_file)
        if not ranks or ranks[0] > 3:
            continue
        start = theirs.square(g_file, ranks[0])
        dest = theirs.square(g_file, 4)
        path = [theirs.square(g_file, r) for r in range(ranks[0] + 1, 5)]
        if any(board.piece_at(s) is not None for s in path):
            continue
        ctx.add(
            "pawn_hook",
            attacker,
            74,
            {
                "pawn": _sq(own.square(h_file, 3)),
                **_move_param(ctx.push_break(attacker, start, dest)),
            },
        )


def _passed(ctx: _Context) -> None:
    for color in chess.COLORS:
        pawns = sorted(ctx.facts.side(color).passed, key=lambda s: -rel_rank(color, s))
        if not pawns or ctx.covered(_sq(pawns[0]), color):
            continue
        pawn = pawns[0]
        front = chess.square(
            chess.square_file(pawn), chess.square_rank(pawn) + (1 if color == chess.WHITE else -1)
        )
        ctx.add("passed_pawn", color, 85, {"pawn": _sq(pawn)}, covers={_sq(pawn)})
        ctx.add("blockade", not color, 84, {"pawn": _sq(pawn), "square": _sq(front)})


def _chain_base(ctx: _Context) -> None:
    for color in chess.COLORS:
        bases = {chain.base: chain for chain in ctx.facts.side(not color).chains}
        for brk in ctx.side_breaks(color):
            target = chess.parse_square(brk.target)
            if target not in bases or ctx.covered(brk.uci[:2], color):
                continue
            chain = bases[target]
            ctx.add(
                "chain_base",
                color,
                80,
                {
                    "chain": "–".join(_sq(s) for s in chain.squares),
                    "base": brk.target,
                    **_move_params(brk),
                },
                covers={brk.uci[:2]},
            )
            break


def _breaks(ctx: _Context) -> None:
    for color in chess.COLORS:
        added = 0
        for brk in ctx.side_breaks(color):
            if added == 2 or ctx.covered(brk.uci[:2], color):
                continue
            params = {"target": brk.target, **_move_params(brk)}
            if not brk.legal_now:
                key, weight = "pawn_break_prepare", 60
            elif brk.uci[2:4] == brk.target:
                # Взятие пешки: напряжение снято, вертикаль пешки открылась.
                key, weight = "pawn_capture", 68
                params["file"] = brk.uci[0]
            else:
                key, weight = "pawn_break_now", 70
            ctx.add(key, color, weight, params, covers={brk.uci[:2]})
            added += 1


def _outposts(ctx: _Context) -> None:
    for color in chess.COLORS:
        knights = ctx.board.pieces(chess.KNIGHT, color)
        if not knights:
            continue
        squares = [s for s in ctx.facts.side(color).outposts if not ctx.covered(_sq(s), color)]
        if not squares:
            continue
        occupied = [s for s in squares if s in knights]
        if occupied:
            ctx.add(
                "outpost_knight", color, 64, {"square": _sq(occupied[0])}, covers={_sq(occupied[0])}
            )
            continue
        square = min(squares, key=lambda s: (abs(3.5 - chess.square_file(s)), -rel_rank(color, s)))
        support = chess.SquareSet(
            ctx.board.attackers(color, square) & ctx.board.pieces(chess.PAWN, color)
        )
        ctx.add(
            "outpost",
            color,
            63,
            {"square": _sq(square), "support": _join(support)},
            covers={_sq(square)},
        )


def _knight_hops(square: chess.Square) -> chess.SquareSet:
    return chess.SquareSet(chess.BB_KNIGHT_ATTACKS[square])


def _knight_square_safe(board: chess.Board, knight: chess.Square, square: chess.Square) -> bool:
    """Поле для коня `knight`: свободно, не на краю, не ниже своей 3-й горизонтали, пешка
    соперника его сейчас не бьёт, а фигуры соперника бьют не больше, чем защищают свои
    (сам конь себя не защищает)."""
    color = board.color_at(knight)
    assert color is not None
    enemy = not color
    if board.piece_at(square) is not None or chess.square_file(square) in (0, 7):
        return False
    if rel_rank(color, square) < 3:
        return False
    if board.attackers_mask(enemy, square) & board.pieces_mask(chess.PAWN, enemy):
        return False
    defenders = board.attackers(color, square) - chess.SquareSet([knight])
    return len(board.attackers(enemy, square)) <= len(defenders)


def _knight_route(ctx: _Context, knight: chess.Square) -> tuple[chess.Square, ...] | None:
    """Лучший маршрут коня в один-два хода (через свободное поле): форпост, короче,
    ближе к центру, дальше вперёд (до 5-й горизонтали)."""
    board = ctx.board
    color = board.color_at(knight)
    assert color is not None
    outposts = set(ctx.facts.side(color).outposts)
    routes: list[tuple[chess.Square, ...]] = []
    for hop in _knight_hops(knight):
        if _knight_square_safe(board, knight, hop):
            routes.append((hop,))
        if board.piece_at(hop) is None:
            routes += [
                (hop, dest)
                for dest in _knight_hops(hop)
                if _knight_square_safe(board, knight, dest)
            ]
    if not routes:
        return None

    def score(route: tuple[chess.Square, ...]) -> tuple[int, int, float, int]:
        dest = route[-1]
        return (
            0 if dest in outposts else 1,
            len(route),
            abs(3.5 - chess.square_file(dest)),
            -min(rel_rank(color, dest), 5),
        )

    return min(routes, key=score)


def _knight_rim(ctx: _Context) -> None:
    """Конь на краю доски (вертикали a/h, 2–6-я горизонтали) — худшая фигура: переведите
    его в игру (Wikibooks «Minor pieces»: сила коня — от его горизонтали; Капабланка,
    §24: фигура вне игры). Маршрут — `_knight_route`."""
    board = ctx.board
    for color in chess.COLORS:
        for knight in sorted(board.pieces(chess.KNIGHT, color)):
            if chess.square_file(knight) not in (0, 7) or not 2 <= rel_rank(color, knight) <= 6:
                continue
            if ctx.covered(_sq(knight), color):
                continue
            route = _knight_route(ctx, knight)
            if route is None:
                continue
            ctx.add(
                "knight_rim",
                color,
                46,
                {"knight": _sq(knight), "route": "–".join(_sq(s) for s in (knight, *route))},
                covers={_sq(knight)},
            )
            break


def _weakness_targets(ctx: _Context) -> None:
    for color in chess.COLORS:
        theirs = ctx.facts.side(not color)
        for kind, weight, squares in (
            ("target_backward", 66, theirs.backward),
            ("target_isolated", 65, theirs.isolated),
        ):
            # Пешки a и h в дебюте редко главная цель — их не предлагаем.
            free = [
                s
                for s in squares
                if 1 <= chess.square_file(s) <= 6 and not ctx.covered(_sq(s), color)
            ]
            if free:
                pawn = min(free, key=lambda s: abs(3.5 - chess.square_file(s)))
                ctx.add(kind, color, weight, {"pawn": _sq(pawn)}, covers={_sq(pawn)})
                break
        files: dict[int, list[chess.Square]] = {}
        for square in theirs.doubled:
            files.setdefault(chess.square_file(square), []).append(square)
        for group in files.values():
            if not any(ctx.covered(_sq(s), color) for s in group):
                ctx.add(
                    "target_doubled",
                    color,
                    55,
                    {"pawns": _join(sorted(group))},
                    covers={_sq(s) for s in group},
                )
                break


def _seventh(ctx: _Context) -> None:
    """Ладья на предпоследней горизонтали соперника (7-я у белых, 2-я у чёрных): бьёт
    пешки сбоку и прижимает короля. Вторжение — по открытой линии на свободное поле, которое
    соперник не бьёт (Ласкер, партия Лазар — Ласкер; Wikibooks «Open lines»). Нужны цели:
    король соперника на последней горизонтали или хотя бы две пешки на седьмой."""
    board = ctx.board
    for color in chess.COLORS:
        rooks = board.pieces(chess.ROOK, color)
        if not rooks:
            continue
        enemy = not color
        king = board.king(enemy)
        pawns = [s for s in board.pieces(chess.PAWN, enemy) if rel_rank(color, s) == 7]
        if len(pawns) < 2 and (king is None or rel_rank(color, king) != 8):
            continue
        placed = [s for s in rooks if rel_rank(color, s) == 7]
        if placed:
            square = _sq(placed[0])
            ctx.add("rook_seventh", color, 75, {"square": square}, covers={square[0]})
            continue
        mover = as_mover(board, color)
        if mover is None:
            continue
        for rook in sorted(rooks, key=lambda s: abs(3.5 - chess.square_file(s))):
            file = chess.square_file(rook)
            if file not in ctx.facts.open_files or ctx.covered(chess.FILE_NAMES[file], color):
                continue
            target = square_at(color, file, 7)
            move = chess.Move(rook, target)
            if board.attackers_mask(enemy, target) or not mover.is_legal(move):
                continue
            ctx.add(
                "rook_to_seventh",
                color,
                72,
                {"san": mover.san(move)},
                covers={chess.FILE_NAMES[file]},
            )
            break


def _files(ctx: _Context) -> None:
    board = ctx.board
    central = sorted(ctx.facts.open_files, key=lambda f: abs(3.5 - f))
    for color in chess.COLORS:
        if not board.pieces(chess.ROOK, color):
            continue
        free = [f for f in central if not ctx.covered(chess.FILE_NAMES[f], color)]
        if free:
            if len(free) == 1:
                ctx.add("rook_open_file", color, 50, {"file": chess.FILE_NAMES[free[0]]})
            else:
                files = ",".join(chess.FILE_NAMES[f] for f in free[:2])
                ctx.add("rook_open_files", color, 50, {"files": files})
            continue
        for file in sorted(ctx.facts.side(color).half_open, key=lambda f: abs(3.5 - f)):
            if not 2 <= file <= 5:
                continue
            their = PawnView(board, not color)
            target = their.square(file, their.ranks(file)[-1])
            if ctx.covered(_sq(target), color):
                continue
            ctx.add(
                "rook_half_open", color, 45, {"file": chess.FILE_NAMES[file], "target": _sq(target)}
            )
            break


def _bishops(ctx: _Context) -> None:
    board = ctx.board
    for color in chess.COLORS:
        mine = board.pieces(chess.BISHOP, color)
        if len({is_dark(s) for s in mine}) == 2 and len(board.pieces(chess.BISHOP, not color)) < 2:
            ctx.add("bishop_pair", color, 40)
        for bishop in mine:
            fixed = [
                s
                for s in board.pieces(chess.PAWN, color)
                if 2 <= chess.square_file(s) <= 5
                and is_dark(s) == is_dark(bishop)
                and is_fixed(board, s)
            ]
            if len(fixed) >= 2 and rel_rank(color, bishop) < max(rel_rank(color, s) for s in fixed):
                pawns = sorted(fixed, key=lambda s: -rel_rank(color, s))
                ctx.add("bad_bishop", color, 42, {"bishop": _sq(bishop), "pawns": _join(pawns)})
                break
        for bishop in mine:
            target = _fianchetto_target(board, color, bishop)
            if target is not None:
                ctx.add("fianchetto", color, 35, {"bishop": _sq(bishop), "target": _sq(target)})
                break


def _fianchetto_target(
    board: chess.Board, color: chess.Color, bishop: chess.Square
) -> chess.Square | None:
    """Пешка соперника, в которую смотрит слон с большой диагонали (b2/g2, b7/g7);
    свой конь на пути не мешает — он уйдёт с открытием линии."""
    home = bishop if color == chess.WHITE else chess.square_mirror(bishop)
    if home not in _FIANCHETTO:
        return None
    corner = _FIANCHETTO[home] if color == chess.WHITE else chess.square_mirror(_FIANCHETTO[home])
    step_file = 1 if chess.square_file(corner) > chess.square_file(bishop) else -1
    step_rank = 1 if chess.square_rank(corner) > chess.square_rank(bishop) else -1
    file, rank = chess.square_file(bishop), chess.square_rank(bishop)
    while 0 <= (file := file + step_file) <= 7 and 0 <= (rank := rank + step_rank) <= 7:
        piece = board.piece_at(chess.square(file, rank))
        if piece is None:
            continue
        if piece.color == color and piece.piece_type == chess.KNIGHT:
            continue
        if piece.color != color and piece.piece_type == chess.PAWN:
            return chess.square(file, rank)
        return None
    return None


def _majority(ctx: _Context) -> None:
    for majority in ctx.facts.majorities:
        if majority.wing == "center":
            continue
        ctx.add(
            "majority",
            majority.color,
            30,
            {"wing": majority.wing, "own": str(majority.own), "other": str(majority.other)},
        )


# --- Сборка --------------------------------------------------------------------------------


def _select(drafts: list[_Draft]) -> tuple[Idea, ...]:
    """По весу (стабильно), без повторов ключа у стороны, не больше лимита на сторону."""
    ranked = sorted(drafts, key=lambda d: -d.weight)
    taken: dict[str, int] = {"white": 0, "black": 0}
    seen: set[tuple[str, str]] = set()
    result = []
    for draft in ranked:
        idea = draft.idea
        if (idea.side, idea.key) in seen or taken[idea.side] >= MAX_IDEAS_PER_SIDE:
            continue
        seen.add((idea.side, idea.key))
        taken[idea.side] += 1
        result.append(idea)
    return tuple(result)


_WEAKNESS_ORDER = ("backward", "isolated", "hanging", "doubled", "passed", "hole")


def _weaknesses(facts: PawnFacts) -> tuple[Weakness, ...]:
    result = []
    for kind in _WEAKNESS_ORDER:
        for color in chess.COLORS:
            side = facts.side(color)
            squares = {
                "backward": side.backward,
                "isolated": side.isolated,
                "hanging": side.hanging,
                "doubled": side.doubled,
                "passed": side.passed,
                "hole": side.holes,
            }[kind]
            for square in sorted(squares, key=lambda s: abs(3.5 - chess.square_file(s))):
                result.append(Weakness(side=side_name(color), square=_sq(square), kind=kind))
    return tuple(result)


def position_ideas(board: chess.Board) -> PositionIdeas:
    """Идеи позиции для обеих сторон: только то, что выводится из расстановки."""
    facts = pawn_facts(board)
    matches = recognize(board)
    ctx = _Context(board, facts, pawn_breaks(board, facts))
    for index, match in enumerate(matches[:MAX_STRUCTURES]):
        _structure_ideas(ctx, match, 200 - 10 * index)
    _opposite_castling(ctx)
    _king_shelter(ctx)
    _passed(ctx)
    _chain_base(ctx)
    _weakness_targets(ctx)
    _breaks(ctx)
    _outposts(ctx)
    _knight_rim(ctx)
    _seventh(ctx)
    _files(ctx)
    _bishops(ctx)
    _majority(ctx)
    outposts = tuple(
        Outpost(side=side_name(color), square=_sq(square))
        for color in chess.COLORS
        for square in facts.side(color).outposts
    )
    return PositionIdeas(
        structures=tuple(match.id.value for match in matches),
        ideas=_select(ctx.drafts),
        breaks=tuple(ctx.breaks),
        outposts=outposts,
        weaknesses=_weaknesses(facts),
        open_files=tuple(chess.FILE_NAMES[f] for f in facts.open_files),
        half_open_files={
            side_name(color): tuple(chess.FILE_NAMES[f] for f in facts.side(color).half_open)
            for color in chess.COLORS
        },
    )
