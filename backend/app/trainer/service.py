"""Тренажёр на БД: создание карточек, очередь, ответ, сводка."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import chess
from pydantic import ValidationError
from sqlalchemy import Select, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.courses.types import CourseNode, CourseTree
from app.db.models import Course, CourseStatus, TrainerAttempt, TrainerCard, UserCourse
from app.trainer.cards import (
    Expected,
    card_nodes,
    expected_moves,
    ideas_node_id,
    node_path,
    path_uci,
)
from app.trainer.check import (
    Evaluator,
    IllegalMoveError,
    Verdict,
    classify_answer,
    parse_move,
)
from app.trainer.srs import LEARNED_BOX, review_after


class CourseMissingError(Exception):
    """Курс не найден (или чужой)."""


class CourseNotReadyError(Exception):
    """Курс ещё собирается или сборка не удалась."""


class CardMissingError(Exception):
    """У пользователя нет карточки для узла."""


def course_tree(course: Course) -> CourseTree:
    if course.status != CourseStatus.READY or course.tree is None:
        raise CourseNotReadyError
    try:
        return CourseTree.model_validate(course.tree)
    except ValidationError as exc:  # дерево битое — для тренажёра курс не готов
        raise CourseNotReadyError from exc


async def get_course(session: AsyncSession, course_id: uuid.UUID) -> Course:
    course = await session.get(Course, course_id)
    if course is None:
        raise CourseMissingError
    return course


@dataclass(frozen=True, slots=True)
class NextCard:
    course_id: uuid.UUID
    node_id: int
    fen: str
    path_uci: list[str]
    color: str
    box: int
    due: bool


@dataclass(frozen=True, slots=True)
class Answer:
    verdict: Verdict
    expected: list[Expected]
    win_loss: float | None
    box: int
    next_review_at: datetime
    ideas_node_id: int | None


@dataclass(frozen=True, slots=True)
class CourseSummary:
    course_id: uuid.UUID
    name: str
    total: int
    due: int
    new: int
    learned: int


async def start_course(
    session: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID
) -> tuple[int, int]:
    """Создаёт недостающие карточки по узлам «ход за учеником». Идемпотентно.
    Курс должен быть в списке пользователя. Возвращает (всего карточек, создано)."""
    course = await get_course(session, course_id)
    owned = await session.get(UserCourse, (user_id, course_id))
    if owned is None:
        raise CourseMissingError
    tree = course_tree(course)
    rows = [
        {
            "user_id": user_id,
            "course_id": course_id,
            "node_id": node.id,
            "epd": chess.Board(node.fen).epd(),
        }
        for node in card_nodes(tree)
    ]
    created = 0
    if rows:
        stmt = (
            insert(TrainerCard)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["user_id", "course_id", "node_id"])
            .returning(TrainerCard.id)
        )
        created = len((await session.execute(stmt)).all())
    await session.commit()
    total = await session.scalar(
        select(func.count()).where(
            TrainerCard.user_id == user_id, TrainerCard.course_id == course_id
        )
    )
    return total or 0, created


async def next_card(
    session: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID | None, now: datetime
) -> NextCard | None:
    """Сначала просроченные (раньше назначенные первыми), затем новые по возрастанию `ply`."""
    if course_id is not None:
        await get_course(session, course_id)
    base = select(TrainerCard).where(TrainerCard.user_id == user_id)
    if course_id is not None:
        base = base.where(TrainerCard.course_id == course_id)

    card = await session.scalar(
        base.where(TrainerCard.next_review_at <= now)
        .order_by(TrainerCard.next_review_at, TrainerCard.created_at, TrainerCard.node_id)
        .limit(1)
    )
    due = card is not None
    if card is None:
        card = await _first_new(session, base)
    if card is None:
        return None
    course = await get_course(session, card.course_id)
    tree = course_tree(course)
    node = _node(tree, card.node_id)
    return NextCard(
        course_id=card.course_id,
        node_id=card.node_id,
        fen=node.fen,
        path_uci=path_uci(tree, node.id),
        color=tree.color,
        box=card.box,
        due=due,
    )


async def _first_new(session: AsyncSession, base: Select[Any]) -> TrainerCard | None:
    cards = (await session.scalars(base.where(TrainerCard.next_review_at.is_(None)))).all()
    if not cards:
        return None
    trees: dict[uuid.UUID, CourseTree] = {}
    best: tuple[int, str, int] | None = None
    chosen: TrainerCard | None = None
    for card in cards:
        if card.course_id not in trees:
            try:
                trees[card.course_id] = course_tree(await get_course(session, card.course_id))
            except CourseNotReadyError:
                continue
        node = next((n for n in trees[card.course_id].nodes if n.id == card.node_id), None)
        if node is None:
            continue
        key = (node.ply, str(card.course_id), card.node_id)
        if best is None or key < best:
            best, chosen = key, card
    return chosen


def _node(tree: CourseTree, node_id: int) -> CourseNode:
    for node in tree.nodes:
        if node.id == node_id:
            return node
    raise CardMissingError


async def answer_card(
    session: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    node_id: int,
    uci: str,
    *,
    hint_used: bool,
    evaluator: Evaluator,
    threshold: float,
    now: datetime,
) -> Answer:
    course = await get_course(session, course_id)
    tree = course_tree(course)
    card = await session.scalar(
        select(TrainerCard)
        .where(
            TrainerCard.user_id == user_id,
            TrainerCard.course_id == course_id,
            TrainerCard.node_id == node_id,
        )
        .with_for_update()
    )
    if card is None:
        raise CardMissingError
    node = _node(tree, node_id)
    board = chess.Board(node.fen)
    move = parse_move(board, uci)  # IllegalMoveError → 422
    expected = expected_moves(tree, node)

    in_course = move.uci() in {e.uci for e in expected}
    loss: float | None = None
    if not in_course:
        loss = await evaluator.loss_of(board, move)
    verdict = classify_answer(in_course=in_course, loss=loss, threshold=threshold)

    review = review_after(card.box, verdict, hint_used=hint_used, now=now)
    card.box = review.box
    card.next_review_at = review.next_review_at
    card.attempts += 1
    card.last_correct = verdict != "wrong"
    card.last_attempt_at = now
    session.add(TrainerAttempt(card_id=card.id, user_id=user_id, uci=move.uci(), verdict=verdict))
    await session.execute(
        update(UserCourse)
        .where(UserCourse.user_id == user_id, UserCourse.course_id == course_id)
        .values(last_studied_at=now)
    )
    await session.commit()
    return Answer(
        verdict=verdict,
        expected=expected,
        win_loss=None if loss is None else round(loss, 1),
        box=review.box,
        next_review_at=review.next_review_at,
        ideas_node_id=ideas_node_id(tree, node_id),
    )


async def summary(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> list[CourseSummary]:
    rows = (
        await session.execute(
            select(
                TrainerCard.course_id,
                Course.name,
                func.count().label("total"),
                func.count().filter(TrainerCard.next_review_at <= now).label("due"),
                func.count().filter(TrainerCard.next_review_at.is_(None)).label("new"),
                func.count().filter(TrainerCard.box >= LEARNED_BOX).label("learned"),
            )
            .join(Course, Course.id == TrainerCard.course_id)
            .where(TrainerCard.user_id == user_id)
            .group_by(TrainerCard.course_id, Course.name)
            .order_by(Course.name, TrainerCard.course_id)
        )
    ).all()
    return [CourseSummary(r.course_id, r.name, r.total, r.due, r.new, r.learned) for r in rows]


__all__ = [
    "Answer",
    "CardMissingError",
    "CourseMissingError",
    "CourseNotReadyError",
    "CourseSummary",
    "IllegalMoveError",
    "NextCard",
    "answer_card",
    "next_card",
    "node_path",
    "start_course",
    "summary",
]
