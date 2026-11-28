"""Тексты идей позиции RU / EN (сессия 13): `render(ideas, lang) -> RenderedIdeas`.

Только общепринятая теория для клубного игрока, коротко. Клетки и ходы — из параметров
идей (факты позиции); SAN — только легальные ходы (`san`), цели подготовки — координатами
(«c7–c5»). Ход чёрных в тексте — с многоточием: «…d5».

Заголовок и описание — по первой распознанной структуре. Владельца структуры (чья
изолированная пешка, у кого атака меньшинства) и клетки для текста берём из первой идеи
с ключом `«структура».…`: `position_ideas` ставит план владельца первым.

Падежей избегаем: цвет в описаниях — готовыми формами («у белых», «белым»), перечни
фигур — в скобках («конь f6, слон e6»).
"""

import re
from collections.abc import Mapping

from app.explain.templates import Lang
from app.plans.types import Idea, PositionIdeas, RenderedIdea, RenderedIdeas, Side

T = dict[Lang, str]

# Формы цвета: {Owner} — с заглавной, {owner} — им. п., {owner_gen} — род., {owner_dat} — дат.
_COLOR_FORMS: dict[Lang, dict[Side, dict[str, str]]] = {
    "ru": {
        "white": {"nom": "белые", "gen": "белых", "dat": "белым"},
        "black": {"nom": "чёрные", "gen": "чёрных", "dat": "чёрным"},
    },
    "en": {
        "white": {"nom": "White", "gen": "White", "dat": "White"},
        "black": {"nom": "Black", "gen": "Black", "dat": "Black"},
    },
}

_WINGS: dict[Lang, dict[str, dict[str, str]]] = {
    "ru": {
        "queenside": {"wing": "ферзевый", "wing_prep": "ферзевом"},
        "kingside": {"wing": "королевский", "wing_prep": "королевском"},
    },
    "en": {
        "queenside": {"wing": "queenside", "wing_prep": "queenside"},
        "kingside": {"wing": "kingside", "wing_prep": "kingside"},
    },
}

_PIECES: dict[Lang, dict[str, str]] = {
    "ru": {"N": "конь", "B": "слон"},
    "en": {"N": "knight", "B": "bishop"},
}

_AND: T = {"ru": "и", "en": "and"}


class StructureText:
    def __init__(self, title: T, summary: T) -> None:
        self.title = title
        self.summary = summary


STRUCTURES: dict[str, StructureText] = {
    "hedgehog": StructureText(
        {"ru": "Ёж", "en": "Hedgehog"},
        {
            "ru": "{Owner} держат компактную расстановку на своей третьей горизонтали, "
            "у {opponent_gen} больше пространства. Всё решают прорывы {b_break} и {d_break}: если "
            "один из них пройдёт, игра {owner_gen} оживает, если нет — {opponent} "
            "постепенно теснят.",
            "en": "{Owner} keeps a compact set-up on the third rank while {Opponent} has "
            "more space. Everything revolves around the breaks {b_break} and {d_break}: "
            "if one of them comes through, {Owner}'s game comes alive; if not, "
            "{Opponent} slowly squeezes.",
        },
    ),
    "sicilian_d6_e5": StructureText(
        {"ru": "Структура Найдорфа / Свешникова", "en": "Najdorf / Sveshnikov structure"},
        {
            "ru": "Пешка {e} даёт {owner_dat} пространство и активную игру, но поле {hole} "
            "пешкой уже не защитить, а пешка {pawn} — отсталая. {Opponent} борются за поле "
            "{hole}; {owner} готовят прорыв {move} и контригру на ферзевом фланге.",
            "en": "The {e} pawn gives {Owner} space and active play, but {hole} can no "
            "longer be covered by a pawn and the {pawn} pawn is backward. {Opponent} fights "
            "for {hole}; {Owner} prepares the {move} break and queenside counterplay.",
        },
    ),
    "scheveningen": StructureText(
        {
            "ru": "Сицилианская: малый центр (Шевенинген)",
            "en": "Sicilian small centre (Scheveningen)",
        },
        {
            "ru": "Пешки {pawns} — прочный «малый центр» {owner_gen}, за ним фигуры "
            "перестраиваются без спешки. {Opponent} владеют пространством и атакуют на "
            "королевском фланге; {owner} отвечают контригрой на ферзевом фланге и по линии "
            "c и ждут момента для прорыва {move}.",
            "en": "{Owner}'s pawns on {pawns} form a solid 'small centre' behind which the "
            "pieces regroup calmly. {Opponent} has more space and attacks on the kingside; "
            "{Owner} counters on the queenside and along the c-file, waiting for the {move} "
            "break.",
        },
    ),
    "kan_taimanov": StructureText(
        {"ru": "Сицилианская: Тайманов / Кан", "en": "Sicilian Taimanov / Kan"},
        {
            "ru": "{Owner} не спешат с ходом d-пешкой: расстановка гибкая, пешка {pawn} "
            "может пойти сразу на два поля. Зато поле {hole} пешкой уже не защитить — "
            "{opponent} стремятся его использовать и захватить пространство.",
            "en": "{Owner} keeps the d-pawn back: the set-up is flexible and the {pawn} pawn "
            "can still jump two squares. But {hole} can no longer be covered by a pawn — "
            "{Opponent} tries to exploit it and gain space.",
        },
    ),
    "maroczy": StructureText(
        {"ru": "Тиски Мароци", "en": "Maróczy Bind"},
        {
            "ru": "Пешки {pawns} держат поле {square} и отнимают у {opponent_gen} "
            "пространство. {Owner} не дают сопернику освободиться и постепенно теснят; "
            "{opponent} разменивают фигуры и готовят подрыв пешечных тисков.",
            "en": "{Owner}'s pawns on {pawns} control {square} and take space from "
            "{Opponent}. {Owner} prevents the freeing breaks and slowly squeezes; "
            "{Opponent} trades pieces and prepares to undermine the bind.",
        },
    ),
    "french_chain": StructureText(
        {"ru": "Французская пешечная цепь", "en": "French pawn chain"},
        {
            "ru": "Цепь {d}–{e} отнимает у {opponent_gen} пространство на королевском "
            "фланге, но её можно подрывать. {Owner} атакуют там, куда направлена цепь, — на "
            "королевском фланге; {opponent} бьют по основанию {d} и играют на ферзевом "
            "фланге.",
            "en": "{Owner}'s chain {d}–{e} takes space from {Opponent} on the kingside but "
            "can be undermined. {Owner} attacks where the chain points — on the kingside; "
            "{Opponent} strikes at the base {d} and plays on the queenside.",
        },
    ),
    "kid_closed": StructureText(
        {"ru": "Закрытый центр староиндийского типа", "en": "Closed centre (King's Indian type)"},
        {
            "ru": "Центр заперт: цепи {chain} у {owner_gen} и {opp_chain} у {opponent_gen} "
            "упёрлись друг в друга. Игра идёт на флангах: {owner} наступают на ферзевом "
            "фланге, {opponent} — на королевском, к королю; решает скорость.",
            "en": "The centre is locked: {Owner}'s chain {chain} and {Opponent}'s chain "
            "{opp_chain} block each other. The play is on the wings: {Owner} advances on "
            "the queenside, {Opponent} on the kingside towards the king — speed decides.",
        },
    ),
    "benoni": StructureText(
        {"ru": "Структура Бенони", "en": "Benoni structure"},
        {
            "ru": "У {owner_gen} центральное большинство и пешка {d}, у {opponent_gen} — "
            "большинство на ферзевом фланге и полуоткрытая линия e. {Owner} готовят прорыв "
            "e-пешкой, {opponent} наступают пешками ферзевого фланга.",
            "en": "{Owner} has a central majority with a pawn on {d}; {Opponent} has a "
            "queenside majority and the half-open e-file. {Owner} prepares the e-pawn break, "
            "{Opponent} advances the queenside pawns.",
        },
    ),
    "carlsbad": StructureText(
        {"ru": "Карлсбадская структура", "en": "Carlsbad structure"},
        {
            "ru": "Структура ферзевого гамбита и Каро-Канн с разменом: у {owner_gen} на "
            "ферзевом фланге меньше пешек, у {opponent_gen} — больше. {Owner} проводят "
            "атаку меньшинства, чтобы создать слабость на линии c; {opponent} играют на "
            "королевском фланге.",
            "en": "The Queen's Gambit / Caro-Kann Exchange structure: {Owner} has fewer "
            "pawns on the queenside, {Opponent} more. {Owner} runs a minority attack to "
            "create a weakness on the c-file; {Opponent} plays on the kingside.",
        },
    ),
    "isolani": StructureText(
        {"ru": "Изолированная пешка {pawn}", "en": "Isolated pawn on {pawn}"},
        {
            "ru": "У {owner_gen} изолированная пешка {pawn}: она даёт простор фигурам и "
            "опорные поля, но сама нуждается в защите. {Owner} ищут активную игру и атаку, "
            "пока фигур много; {opponent} блокируют пешку и стремятся к разменам и "
            "эндшпилю.",
            "en": "{Owner} has an isolated pawn on {pawn}: it gives the pieces space and "
            "strong squares but needs protection itself. {Owner} looks for active play and "
            "an attack while many pieces remain; {Opponent} blockades the pawn and aims for "
            "trades and an endgame.",
        },
    ),
    "hanging_pawns": StructureText(
        {"ru": "Висячие пешки {pawns}", "en": "Hanging pawns on {pawns}"},
        {
            "ru": "Висячие пешки {pawns} контролируют центр, но защитить их пешками нечем. "
            "{Owner} держат их рядом и ждут момента продвинуть одну из них; {opponent} "
            "давят на них фигурами, чтобы заставить двинуться, и блокируют.",
            "en": "{Owner}'s hanging pawns on {pawns} control the centre but have no pawn "
            "support. {Owner} keeps them side by side and waits for the moment to advance "
            "one; {Opponent} attacks them with pieces to force an advance, then blockades.",
        },
    ),
    "stonewall": StructureText(
        {"ru": "«Стоунволл»", "en": "Stonewall"},
        {
            "ru": "Пешки {owner_gen} стоят «каменной стеной» и держат поле {square}, но поле "
            "{hole} пешкой уже не защитить, а слон цвета этих пешек — «плохой». {Owner} "
            "ставят коня на {square} и атакуют на королевском фланге; {opponent} занимают "
            "{hole} и стараются разменять «хорошего» слона соперника.",
            "en": "{Owner}'s pawns form a 'stone wall' controlling {square}, but {hole} can "
            "no longer be covered by a pawn and the bishop of the pawns' colour is 'bad'. "
            "{Owner} plants a knight on {square} and attacks on the kingside; {Opponent} "
            "occupies {hole} and aims to trade off {Owner}'s good bishop.",
        },
    ),
    "london": StructureText(
        {"ru": "Лондонская система", "en": "London System"},
        {
            "ru": "{Owner} держат прочный центр (пешки {pawn} и e3), а слон {bishop} вышел "
            "за пешечную цепь заранее. План {owner_gen} — конь на {square} и игра на "
            "королевском фланге; {opponent} подрывают пешку {pawn} и давят на ферзевый "
            "фланг, откуда ушёл слон.",
            "en": "{Owner} keeps a solid centre (pawns on {pawn} and e3) and has developed "
            "the bishop to {bishop} outside the pawn chain. {Owner}'s plan is a knight on "
            "{square} and kingside play; {Opponent} undermines {pawn} and presses on the "
            "queenside the bishop has left.",
        },
    ),
    "slav": StructureText(
        {"ru": "Славянская / Каро-Канн: c6 и d5", "en": "Slav / Caro-Kann: c6 and d5"},
        {
            "ru": "Пешка {support} прочно поддерживает {pawn}, и центр {owner_gen} трудно "
            "поколебать. {Opponent} давят на пункт {pawn} и стремятся к перевесу в "
            "пространстве; {owner} спокойно развиваются и готовят освобождающие прорывы "
            "пешками c и e.",
            "en": "The {support} pawn firmly supports {pawn}, so {Owner}'s centre is hard "
            "to shake. {Opponent} presses on {pawn} and aims for more space; {Owner} "
            "develops calmly and prepares freeing breaks with the c- and e-pawns.",
        },
    ),
    "caro": StructureText(
        {"ru": "Структура Каро-Канн", "en": "Caro-Kann structure"},
        {
            "ru": "У {owner_gen} нет d-пешки, зато позиция прочная и без слабостей; у "
            "{opponent_gen} — пешка {target} и больше пространства. {Opponent} используют "
            "пространство (поле {square}, линия e); {owner} готовят освобождающие прорывы "
            "против {target}.",
            "en": "{Owner} has no d-pawn but a solid position without weaknesses; "
            "{Opponent} has the {target} pawn and more space. {Opponent} uses the space "
            "({square}, the e-file); {Owner} prepares freeing breaks against {target}.",
        },
    ),
    "italian": StructureText(
        {"ru": "Медленная итальянская", "en": "Slow Italian structure"},
        {
            "ru": "Центральные пешки держат друг друга, спешить некуда: стороны "
            "маневрируют фигурами. {Owner} готовят прорыв {move} при поддержке пешки "
            "{support}; {opponent} держат пункт {e} и ищут свой прорыв в центре.",
            "en": "The centre pawns hold each other, so there is no hurry: both sides "
            "manoeuvre. {Owner} prepares the {move} break supported by {support}; "
            "{Opponent} holds {e} and looks for a central break of their own.",
        },
    ),
    "symmetric_d": StructureText(
        {
            "ru": "Симметричная структура с открытой линией d",
            "en": "Symmetrical structure with an open d-file",
        },
        {
            "ru": "Пешки e4 и e5 стоят друг против друга, линия d открыта. Главная борьба — "
            "за эту линию и поля d4 и d5: кто займёт их ладьями и конями, тот и получит "
            "перевес; прорывы f-пешками оживляют игру.",
            "en": "The e-pawns face each other and the d-file is open. The fight is about "
            "this file and the squares d4 and d5: whoever takes them with rooks and knights "
            "gets the edge; f-pawn breaks liven up the game.",
        },
    ),
    "scotch": StructureText(
        {
            "ru": "Шотландская / Филидор с разменом: e4 против d-пешки",
            "en": "Scotch / Philidor Exchange: e4 against the d-pawn",
        },
        {
            "ru": "Центральные пешки разменялись: у {owner_gen} пешка {pawn} и больше "
            "пространства, у {opponent_gen} — пешка {d} и прочная, но тесная позиция. "
            "{Owner} играют на инициативу и готовят продвижение e-пешки; {opponent} давят "
            "на {pawn} и ждут момента для прорыва d-пешкой.",
            "en": "The centre pawns have been swapped: {Owner} has the {pawn} pawn and more "
            "space, {Opponent} the {d} pawn and a solid but cramped position. {Owner} plays "
            "for the initiative and the e-pawn advance; {Opponent} presses on {pawn} and "
            "waits for a d-pawn break.",
        },
    ),
    "doubled_c": StructureText(
        {"ru": "Сдвоенные пешки на линии c", "en": "Doubled c-pawns"},
        {
            "ru": "У {owner_gen} сдвоенные пешки {pawns}: они малоподвижны, зато держат "
            "центральные поля, а за них обычно получена пара слонов или полуоткрытая "
            "линия. {Owner} играют активно и вскрывают позицию; {opponent} держат её "
            "закрытой, блокируют пешки и стремятся к эндшпилю.",
            "en": "{Owner} has doubled pawns on {pawns}: they are inflexible but control "
            "central squares, and usually come with the bishop pair or a half-open file. "
            "{Owner} plays actively and opens the position; {Opponent} keeps it closed, "
            "blockades the pawns and heads for an endgame.",
        },
    ),
    "big_center": StructureText(
        {"ru": "Пешечный центр {pawns}", "en": "Pawn centre on {pawns}"},
        {
            "ru": "Пешки {pawns} дают {owner_dat} перевес в пространстве. {Owner} "
            "поддерживают центр фигурами и продвигают его, когда это выгодно; {opponent} "
            "подрывают его пешками и давят фигурами — центр, который не удаётся удержать, "
            "становится мишенью.",
            "en": "The pawns on {pawns} give {Owner} more space. {Owner} supports the centre "
            "with pieces and advances it when it pays; {Opponent} undermines it with pawns "
            "and piece pressure — a centre that cannot be held becomes a target.",
        },
    ),
    "open_center": StructureText(
        {"ru": "Открытый центр", "en": "Open centre"},
        {
            "ru": "Центральных пешек почти не осталось. Решают развитие, активность фигур и "
            "безопасность короля; ладьи сильны на открытых линиях, пара слонов — тоже.",
            "en": "Hardly any centre pawns are left. Development, piece activity and king "
            "safety decide; rooks are strong on the open files, and so is the bishop pair.",
        },
    ),
}

IDEAS: dict[str, T] = {
    # Изолятор.
    "isolani.activity": {
        "ru": "Пешка {pawn} держит поля {squares}: ставьте туда коней и играйте активно, на атаку.",
        "en": "The {pawn} pawn controls {squares}: post your knights there and play "
        "actively, for an attack.",
    },
    "isolani.break": {
        "ru": "Прорыв {move} вскрывает центр и оживляет фигуры — готовьте его.",
        "en": "The {move} break opens the centre and frees your pieces — prepare it.",
    },
    "isolani.blockade": {
        "ru": "Блокируйте пешку {pawn}: поле {square} перед ней — лучшее место для коня.",
        "en": "Blockade the {pawn} pawn: {square}, the square in front of it, is ideal for "
        "a knight.",
    },
    "isolani.trade": {
        "ru": "Меняйте фигуры: чем их меньше на доске, тем слабее пешка {pawn}.",
        "en": "Trade pieces: the fewer remain, the weaker the {pawn} pawn becomes.",
    },
    # Висячие пешки.
    "hanging_pawns.advance": {
        "ru": "Держите пешки {pawns} рядом и поддерживайте фигурами; продвигайте одну из "
        "них, когда это вскрывает игру.",
        "en": "Keep {pawns} side by side and support them with pieces; push one when it "
        "opens lines for you.",
    },
    "hanging_pawns.pressure": {
        "ru": "Атакуйте пешки {pawns} ладьями и лёгкими фигурами; когда одна из них "
        "двинется, блокируйте поле перед ней.",
        "en": "Attack {pawns} with rooks and minor pieces; once one of them advances, "
        "blockade the square in front of it.",
    },
    # Карлсбад.
    "carlsbad.minority": {
        "ru": "Атака меньшинства: пешка {pawn} идёт на {to}; после размена с пешкой "
        "{target} у соперника останется слабая пешка на линии c.",
        "en": "Minority attack: the {pawn} pawn goes to {to}; after the exchange with "
        "{target} the opponent is left with a weak pawn on the c-file.",
    },
    "carlsbad.center": {
        "ru": "Другой план — центральный прорыв {move}.",
        "en": "Another plan is the central break {move}.",
    },
    "carlsbad.kingside": {
        "ru": "Игра на королевском фланге: конь на {square} при поддержке пешки {support} "
        "и перевод фигур к королю.",
        "en": "Kingside play: a knight on {square} supported by the {support} pawn, and "
        "pieces swinging towards the king.",
    },
    # Ёж.
    "hedgehog.breaks": {
        "ru": "Не спешите: держите фигуры за пешками и готовьте прорывы {b_break} и {d_break}.",
        "en": "Be patient: keep the pieces behind the pawns and prepare the breaks "
        "{b_break} and {d_break}.",
    },
    "hedgehog.squeeze": {
        "ru": "Контролируйте поля {squares}: без прорывов у соперника нет активной игры.",
        "en": "Control {squares}: without the pawn breaks the opponent has no active play.",
    },
    # Мароци.
    "maroczy.bind": {
        "ru": "Держите поле {square} и не давайте сопернику освободиться пешечными "
        "прорывами; лишнее пространство — для манёвров фигур.",
        "en": "Hold {square} and stop the opponent's freeing pawn breaks; use the extra "
        "space to manoeuvre.",
    },
    "maroczy.counter": {
        "ru": "При нехватке места меняйте фигуры — так легче защищаться — и готовьте "
        "подрыв пешек {pawns}.",
        "en": "Short of space, trade pieces — it eases the defence — and prepare to "
        "undermine {pawns}.",
    },
    # Сицилианские.
    "scheveningen.counter": {
        "ru": "Контригра — на ферзевом фланге и по полуоткрытой линии c; освобождающий "
        "прорыв {move} готовьте фигурами.",
        "en": "Counterplay comes on the queenside and along the half-open c-file; prepare "
        "the freeing break {move} with your pieces.",
    },
    "scheveningen.attack": {
        "ru": "Используйте пространство: пешечная атака на королевском фланге и прорыв "
        "{move} против пешки {target}.",
        "en": "Use the extra space: a pawn storm on the kingside and the {move} break "
        "against {target}.",
    },
    "kan_taimanov.counter": {
        "ru": "Давление по линии c, наступление пешками ферзевого фланга и прорыв {move} в "
        "один ход.",
        "en": "Pressure on the c-file, a queenside pawn advance and the {move} break in one go.",
    },
    "kan_taimanov.space": {
        "ru": "Поле {hole} ослаблено — ищите путь туда для фигур; продвижение {move} "
        "отнимает у соперника пространство.",
        "en": "{hole} is weak — find a route there for your pieces; the advance {move} "
        "takes space from the opponent.",
    },
    "sicilian_d6_e5.d5_break": {
        "ru": "Прорыв {move} убирает отсталую пешку {pawn} и снимает проблемы; до тех пор "
        "контригра — на ферзевом фланге и по линии c.",
        "en": "The {move} break gets rid of the backward {pawn} pawn and solves your "
        "problems; until then counterplay comes on the queenside and along the c-file.",
    },
    "sicilian_d6_e5.d5": {
        "ru": "Поле {square} — главный пункт: ставьте туда фигуры и разменивайте его "
        "защитников ({pieces}).",
        "en": "{square} is the key square: put pieces there and trade off its defenders "
        "({pieces}).",
    },
    "sicilian_d6_e5.d5_plain": {
        "ru": "Поле {square} — главный пункт: ставьте туда фигуры и держите его под контролем.",
        "en": "{square} is the key square: put pieces there and keep it under control.",
    },
    # Закрытые центры.
    "french_chain.kingside": {
        "ru": "Пешка {pawn} отнимает у соперника пространство на королевском фланге — там и "
        "атакуйте, поддерживая цепь.",
        "en": "The {pawn} pawn cramps the opponent on the kingside — attack there and keep "
        "the chain supported.",
    },
    "french_chain.queenside": {
        "ru": "Контригра — на ферзевом фланге и против основания цепи {base}.",
        "en": "Counterplay lies on the queenside and against the base of the chain, {base}.",
    },
    "kid_closed.queenside": {
        "ru": "Цепь {chain} направлена на ферзевый фланг: наступайте там и вскрывайте линии.",
        "en": "Your chain {chain} points to the queenside: advance there and open lines.",
    },
    "kid_closed.kingside": {
        "ru": "Цепь {chain} направлена на королевский фланг: подрыв пешки {target} и "
        "пешечный штурм у короля.",
        "en": "Your chain {chain} points to the kingside: undermine {target} and storm the "
        "king with pawns.",
    },
    "benoni.center": {
        "ru": "Центральное большинство: продвижение пешки {pawn} до {to} подрывает пешку "
        "{target} и вскрывает центр.",
        "en": "Central majority: pushing the {pawn} pawn to {to} undermines {target} and "
        "opens the centre.",
    },
    "benoni.queenside": {
        "ru": "Большинство на ферзевом фланге: наступайте пешками a и b, давите по "
        "полуоткрытой линии e.",
        "en": "Queenside majority: advance the a- and b-pawns and press along the "
        "half-open e-file.",
    },
    "stonewall.outpost": {
        "ru": "Конь на {square} при поддержке пешек {support} и атака на королевском фланге.",
        "en": "A knight on {square} supported by {support}, and an attack on the kingside.",
    },
    "stonewall.hole": {
        "ru": "Поле {square} пешкой уже не защитить — займите его конём.",
        "en": "{square} can no longer be covered by a pawn — occupy it with a knight.",
    },
    # Системы d-пешкой.
    "london.plan": {
        "ru": "Конь на {square} при поддержке пешки {pawn}, затем игра на королевском фланге.",
        "en": "A knight on {square} supported by {pawn}, then play on the kingside.",
    },
    "london.counter": {
        "ru": "Подрывайте пешку {pawn} пешечным прорывом и стремитесь разменять активного "
        "слона {bishop}.",
        "en": "Undermine {pawn} with a pawn break and try to trade off the active bishop on "
        "{bishop}.",
    },
    "london.b2": {
        "ru": "Пешку {pawn} больше не защищает слон с c1 — давите на неё.",
        "en": "The bishop no longer guards {pawn} from c1 — put pressure on it.",
    },
    "slav.solid": {
        "ru": "Центр прочен (пешка {support} держит {pawn}); освобождающие прорывы — "
        "пешками c и e.",
        "en": "The centre is solid ({support} holds {pawn}); the freeing breaks come with "
        "the c- and e-pawns.",
    },
    "slav.bishop": {
        "ru": "Выведите слона {bishop} за пешечную цепь, пока ход пешкой {pawn} его не запер.",
        "en": "Develop the {bishop} bishop outside the pawn chain before moving the {pawn} "
        "pawn shuts it in.",
    },
    "slav.tension": {
        "ru": "Пешка {pawn} под ударом пешки {target}: продвинуть её, разменять или "
        "защитить — от этого зависит структура.",
        "en": "Your {pawn} pawn is attacked by {target}: advancing, exchanging or "
        "defending it decides the structure.",
    },
    "slav.pressure": {
        "ru": "Давите на пункт {target} и боритесь за поле e4.",
        "en": "Press on {target} and fight for the e4 square.",
    },
    "caro.breaks": {
        "ru": "Освобождающие прорывы пешками c и e против {target} — главный способ уравнять игру.",
        "en": "Freeing breaks with the c- and e-pawns against {target} are the main way to "
        "equalise.",
    },
    "caro.space": {
        "ru": "Используйте пространство: конь на {square} при поддержке пешки {support} и "
        "давление по полуоткрытой линии e.",
        "en": "Use your space: a knight on {square} supported by {support} and pressure "
        "along the half-open e-file.",
    },
    # Открытые игры.
    "italian.d4": {
        "ru": "Манёвры фигур и подготовка прорыва {move} при поддержке пешки {support}.",
        "en": "Manoeuvre your pieces and prepare the {move} break supported by {support}.",
    },
    "italian.d5": {
        "ru": "Держите пункт {square} и готовьте ответный прорыв {move} против {target}.",
        "en": "Hold {square} and prepare the counter-break {move} against {target}.",
    },
    "symmetric_d.d_file": {
        "ru": "Займите ладьёй открытую линию d и используйте поле {square} для коня.",
        "en": "Put a rook on the open d-file and use {square} for a knight.",
    },
    "scotch.space": {
        "ru": "Больше пространства в центре: продвижение {move} отнимает у соперника поля, "
        "когда оно поддержано фигурами.",
        "en": "More space in the centre: the advance {move} takes squares from the "
        "opponent once your pieces support it.",
    },
    "scotch.free": {
        "ru": "Освобождающий прорыв {move} и давление на пешку {target} по полуоткрытой линии e.",
        "en": "The freeing break {move}, and pressure on {target} along the half-open e-file.",
    },
    "doubled_c.owner": {
        "ru": "Пешки {pawns} держат поля {squares}; играйте активно фигурами, пока "
        "сдвоенность не стала слабостью.",
        "en": "{pawns} control {squares}; play actively with your pieces before the doubled "
        "pawns turn into a weakness.",
    },
    "doubled_c.target": {
        "ru": "Сдвоенные пешки {pawns} — долгосрочная цель: фиксируйте их, давите фигурами "
        "и стремитесь к эндшпилю.",
        "en": "The doubled pawns {pawns} are a long-term target: fix them, attack them with "
        "pieces and aim for an endgame.",
    },
    "big_center.hold": {
        "ru": "Поддерживайте центр {pawns} фигурами; продвижение пешки захватывает "
        "пространство, но отдаёт поля — делайте его вовремя.",
        "en": "Support the {pawns} centre with pieces; a pawn advance gains space but gives "
        "up squares — time it well.",
    },
    "big_center.undermine": {
        "ru": "Подрывайте центр {pawns} пешечными прорывами и давлением фигур.",
        "en": "Undermine the {pawns} centre with pawn breaks and piece pressure.",
    },
    "open_center.activity": {
        "ru": "Не задерживайте короля в центре, развивайте фигуры и ставьте ладьи на "
        "открытые линии.",
        "en": "Don't leave your king in the centre; develop and put your rooks on the open files.",
    },
    # Общие идеи из фактов.
    "opposite_castling": {
        "ru": "Короли на разных флангах: пешечный штурм на {wing_prep} фланге, где стоит "
        "король соперника, — решает скорость.",
        "en": "Kings on opposite wings: storm the {wing} with pawns, where the enemy king "
        "is — speed decides.",
    },
    "king_holes": {
        "ru": "После {pawn} поля {squares} у короля соперника пешками не защитить, а слона "
        "этого цвета у него нет: ведите туда ферзя и коня.",
        "en": "After {pawn} the squares {squares} next to the enemy king can't be covered by "
        "pawns, and the bishop of that colour is gone: bring your queen and a knight there.",
    },
    "trade_king_bishop": {
        "ru": "Разменяйте слона {bishop} — главного защитника короля: без него поля {squares} "
        "станут дырами.",
        "en": "Trade off the {bishop} bishop, the king's key defender: without it {squares} "
        "become holes.",
    },
    "pawn_hook": {
        "ru": "Пешка {pawn} — зацепка для штурма: наступайте {move} и вскрывайте линию к королю.",
        "en": "The {pawn} pawn is a hook for a pawn storm: advance {move} and open a file "
        "towards the king.",
    },
    "passed_pawn": {
        "ru": "Проходная пешка {pawn}: поддерживайте её фигурами и продвигайте.",
        "en": "Passed pawn on {pawn}: support it with pieces and push it.",
    },
    "blockade": {
        "ru": "Блокируйте проходную {pawn} на поле {square} — лучше всего конём.",
        "en": "Blockade the passed pawn on {pawn} at {square} — ideally with a knight.",
    },
    "chain_base": {
        "ru": "Бейте по основанию цепи соперника {chain}: {move} против пешки {base}.",
        "en": "Strike at the base of the opponent's chain {chain}: {move} against {base}.",
    },
    "pawn_break_now": {
        "ru": "Пешечный прорыв {move} — удар по пешке {target}.",
        "en": "The pawn break {move} strikes at {target}.",
    },
    "pawn_capture": {
        "ru": "Взятие {move} снимает пешечное напряжение и открывает линию {file}.",
        "en": "The capture {move} releases the pawn tension and opens the {file}-file.",
    },
    "pawn_break_prepare": {
        "ru": "Готовьте прорыв {move} против пешки {target}.",
        "en": "Prepare the {move} break against {target}.",
    },
    "outpost": {
        "ru": "Форпост {square} (опора — {support_pawns}): пешкой соперник его уже не "
        "атакует — отличное поле для коня.",
        "en": "Outpost on {square} (supported by {support_pawns}): no enemy pawn can attack "
        "it — an ideal square for a knight.",
    },
    "outpost_knight": {
        "ru": "Конь на форпосте {square}: пешкой его не прогнать — держите его там.",
        "en": "The knight on the {square} outpost cannot be chased by pawns — keep it there.",
    },
    "target_backward": {
        "ru": "Давите на отсталую пешку {pawn}: пешкой её не защитить, а поле перед ней — ваше.",
        "en": "Attack the backward pawn on {pawn}: no pawn can defend it, and the square in "
        "front of it is yours.",
    },
    "target_isolated": {
        "ru": "Давите на изолированную пешку {pawn} и блокируйте поле перед ней.",
        "en": "Attack the isolated pawn on {pawn} and blockade the square in front of it.",
    },
    "target_doubled": {
        "ru": "Сдвоенные пешки {pawns} малоподвижны — атакуйте их фигурами.",
        "en": "The doubled pawns {pawns} are inflexible — attack them with pieces.",
    },
    "knight_rim": {
        "ru": "Конь {knight} на краю доски контролирует мало полей — переведите его в игру: "
        "{route}.",
        "en": "The knight on {knight} controls few squares on the rim — bring it into play: "
        "{route}.",
    },
    "rook_seventh": {
        "ru": "Ладья {square} вторглась на предпоследнюю горизонталь соперника: бейте пешки "
        "сбоку, прижимайте короля и подключайте вторую ладью.",
        "en": "The rook on {square} has reached the opponent's second rank: pick off pawns "
        "from the side, pin the king back and bring the other rook.",
    },
    "rook_to_seventh": {
        "ru": "Вторжение {move}: ладья на предпоследней горизонтали соперника бьёт пешки "
        "сбоку и прижимает короля.",
        "en": "Invade with {move}: a rook on the opponent's second rank attacks pawns from "
        "the side and confines the king.",
    },
    "rook_open_file": {
        "ru": "Займите ладьёй открытую линию {file}.",
        "en": "Put a rook on the open {file}-file.",
    },
    "rook_open_files": {
        "ru": "Займите ладьями открытые линии ({files}).",
        "en": "Put your rooks on the open files ({files}).",
    },
    "rook_half_open": {
        "ru": "Полуоткрытая линия {file}: давите ладьёй на пешку {target}.",
        "en": "Half-open {file}-file: press on {target} with a rook.",
    },
    "bishop_pair": {
        "ru": "Пара слонов — козырь в открытой позиции: вскрывайте игру.",
        "en": "The bishop pair is an asset in open positions: open up the game.",
    },
    "bad_bishop": {
        "ru": "Слон {bishop} — «плохой»: свои пешки {pawns} заперты на полях его цвета. "
        "Выведите его за цепь или разменяйте.",
        "en": "The {bishop} bishop is 'bad': your own pawns on {pawns} are fixed on its "
        "colour. Bring it outside the chain or trade it.",
    },
    "fianchetto": {
        "ru": "Слон {bishop} с большой диагонали нацелен на пешку {target}.",
        "en": "The {bishop} bishop on the long diagonal is aimed at {target}.",
    },
    "majority": {
        "ru": "Большинство на {wing_prep} фланге ({own} против {other}): в эндшпиле оно "
        "даёт проходную.",
        "en": "Majority on the {wing} ({own} vs {other}): in the endgame it can create a "
        "passed pawn.",
    },
}

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _join(values: list[str], lang: Lang) -> str:
    if len(values) == 1:
        return values[0]
    return f"{', '.join(values[:-1])} {_AND[lang]} {values[-1]}"


def _pawns(squares: list[str], lang: Lang) -> str:
    """«пешка c5» / «пешки c5 и e5» — для перечня пешек после тире."""
    joined = _join(squares, lang)
    if lang == "ru":
        return f"пешка {joined}" if len(squares) == 1 else f"пешки {joined}"
    return f"the {joined} pawn" if len(squares) == 1 else f"the {joined} pawns"


def _values(params: Mapping[str, str], side: Side, lang: Lang) -> dict[str, str]:
    """Параметры идеи → подстановки: ход с многоточием у чёрных, перечни, фигуры, фланг."""
    values: dict[str, str] = {}
    for name, raw in params.items():
        if name == "san":
            values["move"] = f"…{raw}" if side == "black" else raw
        elif name == "pieces":
            values[name] = ", ".join(
                f"{_PIECES[lang][item[0]]} {item[1:]}" for item in raw.split(",")
            )
        elif name == "wing":
            values.update(_WINGS[lang][raw])
        else:
            values[name] = _join(raw.split(","), lang)
            if name == "support":
                values["support_pawns"] = _pawns(raw.split(","), lang)
    return values


def _colors(owner: Side, lang: Lang) -> dict[str, str]:
    forms = _COLOR_FORMS[lang]
    opponent: Side = "black" if owner == "white" else "white"
    result = {}
    for role, side in (("owner", owner), ("opponent", opponent)):
        result[role] = forms[side]["nom"]
        result[role.capitalize()] = forms[side]["nom"].capitalize()
        result[f"{role}_gen"] = forms[side]["gen"]
        result[f"{role}_dat"] = forms[side]["dat"]
    return result


def _format(template: str, values: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        return values[match.group(1)]

    return _PLACEHOLDER.sub(replace, template)


def render_idea(idea: Idea, lang: Lang) -> RenderedIdea:
    text = _format(IDEAS[idea.key][lang], _values(idea.params, idea.side, lang))
    return RenderedIdea(key=idea.key, side=idea.side, text=text)


def _structure(ideas: PositionIdeas, lang: Lang) -> tuple[str | None, str | None]:
    if not ideas.structures:
        return None, None
    sid = ideas.structures[0]
    text = STRUCTURES[sid]
    owner = next((i for i in ideas.ideas if i.key.startswith(f"{sid}.")), None)
    if owner is None:
        values: dict[str, str] = {}
    else:
        values = {**_values(owner.params, owner.side, lang), **_colors(owner.side, lang)}
    try:
        return _format(text.title[lang], values), _format(text.summary[lang], values)
    except KeyError:
        # Идеи без плана структуры (собраны не `position_ideas`): только название.
        return _PLACEHOLDER.sub("", text.title[lang]).strip(), None


def render(ideas: PositionIdeas, lang: Lang) -> RenderedIdeas:
    """Тексты идей на языке пользователя (RU / EN)."""
    title, summary = _structure(ideas, lang)
    return RenderedIdeas(
        structures=ideas.structures,
        structure_title=title,
        structure_summary=summary,
        ideas=tuple(render_idea(idea, lang) for idea in ideas.ideas),
    )
