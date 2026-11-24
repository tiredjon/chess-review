"""Карточки тренажёра из дерева курса: узлы, где ход за учеником, и путь до них."""

from dataclasses import dataclass

from app.courses.types import CourseNode, CourseTree


def _index(tree: CourseTree) -> dict[int, CourseNode]:
    return {node.id: node for node in tree.nodes}


def learner_children(tree: CourseTree, node: CourseNode) -> list[CourseNode]:
    """Ходы ученика в позиции узла (основной ход курса — первым)."""
    by_id = _index(tree)
    kids = [by_id[i] for i in node.children if i in by_id and by_id[i].mover == "learner"]
    return sorted(kids, key=lambda kid: not kid.main)


def card_nodes(tree: CourseTree) -> list[CourseNode]:
    """Узлы — позиции перед ходом ученика: у узла есть дети с mover="learner"."""
    by_id = _index(tree)
    return [
        node
        for node in tree.nodes
        if any(i in by_id and by_id[i].mover == "learner" for i in node.children)
    ]


def node_path(tree: CourseTree, node_id: int) -> list[CourseNode]:
    """Узлы от корня до `node_id` включительно. Пусто, если узла нет (или цикл)."""
    by_id = _index(tree)
    path: list[CourseNode] = []
    current = by_id.get(node_id)
    while current is not None and len(path) <= len(by_id):
        path.append(current)
        current = None if current.parent is None else by_id.get(current.parent)
    path.reverse()
    return path


def path_uci(tree: CourseTree, node_id: int) -> list[str]:
    """Ходы UCI от начальной позиции до позиции узла."""
    return [node.uci for node in node_path(tree, node_id) if node.uci is not None]


def ideas_node_id(tree: CourseTree, node_id: int) -> int | None:
    """Ближайший к карточке узел пути (сам узел, затем предки) с непустыми идеями."""
    for node in reversed(node_path(tree, node_id)):
        if _has_ideas(node):
            return node.id
    return None


def _has_ideas(node: CourseNode) -> bool:
    ideas = node.ideas
    if ideas is None:
        return False
    return bool(
        ideas.structures
        or ideas.ideas
        or ideas.breaks
        or ideas.outposts
        or ideas.weaknesses
        or ideas.open_files
        or any(ideas.half_open_files.values())
    )


@dataclass(frozen=True, slots=True)
class Expected:
    uci: str
    san: str


def expected_moves(tree: CourseTree, node: CourseNode) -> list[Expected]:
    return [
        Expected(uci=kid.uci, san=kid.san or "") for kid in learner_children(tree, node) if kid.uci
    ]
