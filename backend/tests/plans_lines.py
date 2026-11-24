"""Дебютные линии для тестов идей позиции (сессия 13): настоящие варианты из
`app/review/data/openings.tsv` и известных партий, позиция — после последнего хода."""

import re

import chess

LINES: dict[str, str] = {
    # Ёж и тиски Мароци.
    "hedgehog_english": "1. c4 c5 2. Nf3 Nf6 3. g3 b6 4. Bg2 Bb7 5. O-O e6 6. Nc3 Be7 7. d4 "
    "cxd4 8. Qxd4 d6 9. e4 a6",
    "hedgehog_kan": "1. e4 c5 2. Nf3 e6 3. d4 cxd4 4. Nxd4 a6 5. c4 Nf6 6. Nc3 Qc7 7. a3 b6 "
    "8. Be3 Bb7 9. f3 d6",
    "hedgehog_rd1": "1. Nf3 Nf6 2. c4 c5 3. Nc3 e6 4. g3 b6 5. Bg2 Bb7 6. O-O Be7 7. d4 cxd4 "
    "8. Qxd4 d6 9. Rd1 a6 10. b3 Nbd7",
    "accel_dragon_maroczy": "1. e4 c5 2. Nf3 Nc6 3. d4 cxd4 4. Nxd4 g6 5. c4 Bg7 6. Be3 Nf6 "
    "7. Nc3 O-O 8. Be2 d6",
    "taimanov_maroczy": "1. e4 c5 2. Nf3 e6 3. d4 cxd4 4. Nxd4 Nc6 5. Nb5 d6 6. c4 Nf6 7. N1c3 "
    "a6 8. Na3",
    "maroczy_nd4": "1. e4 c5 2. Nf3 Nc6 3. d4 cxd4 4. Nxd4 g6 5. c4 Bg7 6. Be3 Nf6 7. Nc3 Ng4 "
    "8. Qxg4 Nxd4 9. Qd1 e5",
    # Сицилианские с …e5.
    "najdorf_be2_e5": "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Be2 e5",
    "sveshnikov": "1. e4 c5 2. Nf3 Nc6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 e5 6. Ndb5 d6 7. Bg5 a6 "
    "8. Na3 b5",
    "boleslavsky": "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 Nc6 6. Be2 e5",
    "kalashnikov": "1. e4 c5 2. Nf3 Nc6 3. d4 cxd4 4. Nxd4 e5 5. Nb5 d6",
    # Малый центр и Тайманов / Кан.
    "scheveningen": "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 e6 6. Be2 a6 7. O-O Be7 "
    "8. f4 O-O",
    "keres_attack": "1. e4 c5 2. Nf3 e6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 d6 6. g4",
    "najdorf_english": "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Be3 e6 7. f3 b5",
    "taimanov_english": "1. e4 c5 2. Nf3 e6 3. d4 cxd4 4. Nxd4 Nc6 5. Nc3 Qc7 6. Be3 a6 7. Qd2 "
    "Nf6 8. O-O-O",
    "taimanov_be2": "1. e4 c5 2. Nf3 e6 3. d4 cxd4 4. Nxd4 Nc6 5. Nc3 Qc7 6. Be2 a6 7. O-O Nf6 "
    "8. Kh1",
    "kan_bd3": "1. e4 c5 2. Nf3 e6 3. d4 cxd4 4. Nxd4 a6 5. Bd3 Bc5 6. Nb3 Ba7",
    "dragon_yugoslav": "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 g6 6. Be3 Bg7 7. f3 "
    "O-O 8. Qd2 Nc6 9. Bc4 Bd7 10. O-O-O",
    # Россолимо и Нимцович: сдвоенные c-пешки.
    "rossolimo_dxc6": "1. e4 c5 2. Nf3 Nc6 3. Bb5 g6 4. Bxc6 dxc6 5. d3 Bg7 6. h3 Nf6 7. Nc3 "
    "O-O 8. Be3",
    "rossolimo_bxc6": "1. e4 c5 2. Nf3 Nc6 3. Bb5 g6 4. Bxc6 bxc6 5. O-O Bg7 6. Re1 Nh6",
    "nimzo_saemisch": "1. d4 Nf6 2. c4 e6 3. Nc3 Bb4 4. a3 Bxc3+ 5. bxc3 c5 6. e3",
    "rossolimo_g6": "1. e4 c5 2. Nf3 Nc6 3. Bb5 g6 4. O-O Bg7 5. Re1",
    # Французская цепь.
    "french_advance": "1. e4 e6 2. d4 d5 3. e5 c5 4. c3 Nc6 5. Nf3 Qb6",
    "french_steinitz": "1. e4 e6 2. d4 d5 3. Nc3 Nf6 4. e5 Nfd7 5. f4 c5 6. Nf3 Nc6 7. Be3",
    "french_tarrasch_closed": "1. e4 e6 2. d4 d5 3. Nd2 Nf6 4. e5 Nfd7 5. Bd3 c5 6. c3 Nc6",
    "caro_advance": "1. e4 c6 2. d4 d5 3. e5 Bf5 4. Nf3 e6 5. Be2",
    "french_exchange": "1. e4 e6 2. d4 d5 3. exd5 exd5",
    "french_rubinstein": "1. e4 e6 2. d4 d5 3. Nc3 dxe4 4. Nxe4 Nd7",
    "french_2d4d5": "1. e4 e6 2. d4 d5",
    # Закрытый центр, Бенони.
    "kid_mar_del_plata": "1. d4 Nf6 2. c4 g6 3. Nc3 Bg7 4. e4 d6 5. Nf3 O-O 6. Be2 e5 7. O-O "
    "Nc6 8. d5 Ne7",
    "kid_petrosian": "1. d4 Nf6 2. c4 g6 3. Nc3 Bg7 4. e4 d6 5. Nf3 O-O 6. Be2 e5 7. d5 a5",
    "czech_benoni": "1. d4 Nf6 2. c4 c5 3. d5 e5 4. Nc3 d6 5. e4 Be7",
    "ruy_chigorin_d5": "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 "
    "8. c3 O-O 9. h3 Na5 10. Bc2 c5 11. d4 Qc7 12. d5",
    "kid_exd4": "1. d4 Nf6 2. c4 g6 3. Nc3 Bg7 4. e4 d6 5. Nf3 O-O 6. Be2 e5 7. O-O exd4 8. Nxd4",
    "benoni_classical": "1. d4 Nf6 2. c4 c5 3. d5 e6 4. Nc3 exd5 5. cxd5 d6 6. e4 g6 7. Nf3 "
    "Bg7 8. Be2 O-O",
    "benoni_fianchetto": "1. d4 Nf6 2. c4 c5 3. d5 e6 4. Nc3 exd5 5. cxd5 d6 6. Nf3 g6 7. g3 "
    "Bg7 8. Bg2 O-O",
    "benoni_taimanov": "1. d4 Nf6 2. c4 c5 3. d5 e6 4. Nc3 exd5 5. cxd5 d6 6. e4 g6 7. f4 Bg7 "
    "8. Bb5+",
    # Карлсбад.
    "qgd_exchange": "1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. cxd5 exd5 5. Bg5 c6 6. e3 Be7 7. Bd3 O-O "
    "8. Qc2 Nbd7 9. Nf3 Re8 10. O-O",
    "caro_exchange": "1. e4 c6 2. d4 d5 3. exd5 cxd5 4. Bd3 Nc6 5. c3 Nf6 6. Bf4 Bg4 7. Qb3",
    "qgd_exchange_bf4": "1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. cxd5 exd5 5. Bf4 c6 6. e3 Bf5",
    "slav_exchange": "1. d4 d5 2. c4 c6 3. cxd5 cxd5 4. Nc3 Nf6",
    "qgd_orthodox": "1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. Bg5 Be7 5. e3 O-O",
    # Изолятор и висячие пешки.
    "panov": "1. e4 c6 2. d4 d5 3. exd5 cxd5 4. c4 Nf6 5. Nc3 e6 6. Nf3 Be7 7. cxd5 Nxd5",
    "qga_iqp": "1. d4 d5 2. c4 dxc4 3. Nf3 Nf6 4. e3 e6 5. Bxc4 c5 6. O-O a6 7. Qe2 cxd4 8. exd4",
    "alapin_iqp": "1. e4 c5 2. c3 d5 3. exd5 Qxd5 4. d4 Nf6 5. Nf3 e6 6. Be2 cxd4 7. cxd4",
    "tarrasch_iqp": "1. d4 d5 2. c4 e6 3. Nc3 c5 4. cxd5 exd5 5. Nf3 Nc6 6. g3 Nf6 7. Bg2 Be7 "
    "8. O-O O-O 9. dxc5 Bxc5",
    "french_tarrasch_iqp": "1. e4 e6 2. d4 d5 3. Nd2 c5 4. exd5 exd5 5. Ngf3 Nc6 6. Bb5 Bd6 "
    "7. dxc5 Bxc5",
    "tartakower_hanging": "1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. Bg5 Be7 5. e3 O-O 6. Nf3 h6 7. Bh4 "
    "b6 8. cxd5 Nxd5 9. Bxe7 Qxe7 10. Nxd5 exd5 11. Rc1 Be6 12. Qa4 c5 13. Qa3 Rc8 14. Bb5 a6 "
    "15. dxc5 bxc5",
    "semi_tarrasch_hanging": "1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. Nf3 c5 5. cxd5 Nxd5 6. e3 Nc6 "
    "7. Bd3 Be7 8. O-O O-O 9. a3 cxd4 10. exd4 Nxc3 11. bxc3 b6 12. Qe2 Bb7 13. Rd1 Rc8 14. c4",
    "panov_hanging": "1. e4 c6 2. d4 d5 3. exd5 cxd5 4. c4 Nf6 5. Nc3 e6 6. Nf3 Be7 7. cxd5 Nxd5 "
    "8. Bd3 Nc6 9. O-O O-O 10. Re1 Nxc3 11. bxc3 b6 12. Qe2 Bb7 13. Bb2 Rc8 14. c4",
    # Стоунволл, Лондон.
    "dutch_stonewall": "1. d4 f5 2. c4 Nf6 3. g3 e6 4. Bg2 d5 5. Nf3 c6 6. O-O Bd6",
    "stonewall_attack": "1. d4 d5 2. e3 Nf6 3. Bd3 c5 4. c3 Nc6 5. f4",
    "dutch_stonewall_b3": "1. d4 e6 2. c4 f5 3. Nf3 Nf6 4. g3 d5 5. Bg2 c6 6. O-O Bd6 7. b3 Qe7",
    "dutch_leningrad": "1. d4 f5 2. c4 Nf6 3. g3 g6 4. Bg2 Bg7 5. Nf3 O-O 6. O-O d6",
    "london_c5": "1. d4 d5 2. Bf4 Nf6 3. e3 c5 4. c3 Nc6 5. Nd2 e6 6. Ngf3 Bd6 7. Bg3",
    "london_kid": "1. d4 Nf6 2. Nf3 g6 3. Bf4 Bg7 4. e3 d6 5. h3 O-O 6. Be2",
    "london_qb6": "1. d4 d5 2. Nf3 Nf6 3. Bf4 c5 4. e3 Qb6 5. Nc3",
    "london_c6": "1. d4 d5 2. Bf4 c6 3. e3 Bf5",
    "colle": "1. d4 d5 2. Nf3 Nf6 3. e3 e6 4. Bd3 c5 5. c3",
    # Славянская, Каро-Канн.
    "semi_slav": "1. d4 d5 2. c4 c6 3. Nf3 Nf6 4. Nc3 e6",
    "slav_bf5": "1. d4 d5 2. c4 c6 3. Nf3 Nf6 4. e3 Bf5 5. Nc3 e6",
    "caro_nc3": "1. e4 c6 2. d4 d5 3. Nc3",
    "slav_dxc4": "1. d4 d5 2. c4 c6 3. Nf3 Nf6 4. Nc3 dxc4 5. a4 Bf5 6. e3 e6 7. Bxc4",
    "caro_classical": "1. e4 c6 2. d4 d5 3. Nc3 dxe4 4. Nxe4 Bf5 5. Ng3 Bg6 6. h4 h6 7. Nf3 Nd7 "
    "8. h5 Bh7 9. Bd3 Bxd3 10. Qxd3 e6",
    "caro_karpov": "1. e4 c6 2. d4 d5 3. Nc3 dxe4 4. Nxe4 Nd7 5. Ng5 Ngf6 6. Bd3 e6 7. N1f3 Bd6",
    "caro_bronstein": "1. e4 c6 2. d4 d5 3. Nc3 dxe4 4. Nxe4 Nf6 5. Nxf6+ gxf6",
    # Итальянская, Испанская.
    "giuoco_pianissimo": "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d3 d6 6. O-O a6 7. a4 Ba7 "
    "8. Re1 O-O 9. h3 h6 10. Nbd2",
    "two_knights_d3": "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. d3 Be7 5. O-O O-O 6. c3 d6",
    "ruy_d3": "1. e4 e5 2. Nf3 Nc6 3. Bb5 Nf6 4. d3 Bc5 5. c3 O-O 6. O-O d6",
    "italian_early": "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5",
    "greco": "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Bd2",
    # Филидор, шотландская.
    "philidor_hanham_dxe5": "1. e4 e5 2. Nf3 d6 3. d4 Nd7 4. Bc4 c6 5. dxe5 dxe5 6. O-O Be7",
    "philidor_queenless": "1. e4 d6 2. d4 Nf6 3. Nc3 e5 4. dxe5 dxe5 5. Qxd8+ Kxd8 6. Bc4 Be6 "
    "7. Bxe6 fxe6",
    "philidor_lion_dxe5": "1. e4 e5 2. Nf3 d6 3. d4 Nf6 4. Nc3 Nbd7 5. Bc4 Be7 6. dxe5 dxe5",
    "philidor_exchange": "1. e4 e5 2. Nf3 d6 3. d4 exd4 4. Nxd4 Nf6 5. Nc3 Be7 6. Be2 O-O 7. O-O "
    "Re8 8. f4",
    "scotch_four_knights": "1. e4 e5 2. Nf3 Nc6 3. d4 exd4 4. Nxd4 Nf6 5. Nc3 Bb4",
    "scotch_bc5": "1. e4 e5 2. Nf3 Nc6 3. d4 exd4 4. Nxd4 Bc5 5. Be3 Qf6 6. c3 Nge7",
    "scotch_mieses": "1. e4 e5 2. Nf3 Nc6 3. d4 exd4 4. Nxd4 Nf6 5. Nxc6 bxc6 6. e5",
    # Пешечный центр.
    "owen": "1. e4 b6 2. d4 Bb7 3. Bd3 e6 4. Nf3 c5 5. c3 Nf6 6. Qe2",
    "pirc_austrian": "1. e4 d6 2. d4 Nf6 3. Nc3 g6 4. f4 Bg7 5. Nf3 O-O",
    "grunfeld_exchange": "1. d4 Nf6 2. c4 g6 3. Nc3 d5 4. cxd5 Nxd5 5. e4 Nxc3 6. bxc3 Bg7",
    # Открытый центр.
    "two_knights_open": "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. d4 exd4 5. O-O Nxe4 6. Re1 d5 "
    "7. Bxd5 Qxd5 8. Nc3 Qa5 9. Nxe4",
    "max_lange": "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. O-O Nf6 5. d4 exd4 6. e5 d5 7. exf6 dxc4 "
    "8. Re1+ Be6 9. Ng5",
    "danish": "1. e4 e5 2. d4 exd4 3. c3 dxc3 4. Bc4 cxb2 5. Bxb2 d5 6. Bxd5",
    "start": "",
}


def play(line: str) -> chess.Board:
    board = chess.Board()
    for token in line.split():
        if not re.fullmatch(r"\d+\.+", token):
            board.push_san(token)
    return board


def board_of(name: str) -> chess.Board:
    return play(LINES[name])
