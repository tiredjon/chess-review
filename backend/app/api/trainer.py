"""Тренажёр дебютов: очередь карточек и ответы (сессия 13)."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Query, Request, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DatabaseDep, SessionDep, SettingsDep
from app.api.errors import ApiError, ErrorCode
from app.api.ratelimit import limit_user
from app.engine.analyzer import PositionEngine
from app.engine.cache import DbEvalCache
from app.engine.pool import EngineError
from app.trainer import service
from app.trainer.check import Evaluator, IllegalMoveError

router = APIRouter(tags=["trainer"])
log = structlog.get_logger(__name__)


class StartOut(BaseModel):
    course_id: uuid.UUID
    total: int
    created: int


class NextCardOut(BaseModel):
    course_id: uuid.UUID
    node_id: int
    fen: str
    path_uci: list[str]
    color: Literal["white", "black"]
    box: int
    # True — повторение просроченной карточки, False — новая.
    due: bool


class AnswerIn(BaseModel):
    uci: str = Field(min_length=4, max_length=5)
    hint_used: bool = False


class ExpectedMove(BaseModel):
    uci: str
    san: str


class AnswerOut(BaseModel):
    verdict: Literal["main", "alternative", "wrong"]
    expected: list[ExpectedMove]
    # Потеря win% против лучшего хода; None — ход курса (движок не вызывался).
    win_loss: float | None
    box: int
    next_review_at: datetime
    ideas_node_id: int | None


class CourseSummaryOut(BaseModel):
    course_id: uuid.UUID
    name: str
    total: int
    due: int
    new: int
    learned: int


def _now() -> datetime:
    return datetime.now(UTC)


def _not_found() -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.COURSE_NOT_FOUND, "Курс не найден")


def _not_ready() -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, ErrorCode.COURSE_NOT_READY, "Курс ещё не готов")


@router.post("/trainer/courses/{course_id}/start")
async def start(course_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> StartOut:
    """Создаёт карточки всех узлов «ход за учеником»; повторный вызов ничего не дублирует."""
    try:
        total, created = await service.start_course(session, user.id, course_id)
    except service.CourseMissingError as exc:
        raise _not_found() from exc
    except service.CourseNotReadyError as exc:
        raise _not_ready() from exc
    return StartOut(course_id=course_id, total=total, created=created)


@router.get("/trainer/next")
async def next_card(
    session: SessionDep, user: CurrentUser, course_id: Annotated[uuid.UUID | None, Query()] = None
) -> NextCardOut | None:
    """Ближайшая карточка: просроченные, затем новые по порядку линии; `null`, если пусто."""
    try:
        card = await service.next_card(session, user.id, course_id, _now())
    except service.CourseMissingError as exc:
        raise _not_found() from exc
    except service.CourseNotReadyError as exc:
        raise _not_ready() from exc
    if card is None:
        return None
    return NextCardOut(
        course_id=card.course_id,
        node_id=card.node_id,
        fen=card.fen,
        path_uci=card.path_uci,
        color="white" if card.color == "white" else "black",
        box=card.box,
        due=card.due,
    )


@router.post(
    "/trainer/courses/{course_id}/nodes/{node_id}/answer", dependencies=[limit_user("trainer")]
)
async def answer(  # noqa: PLR0917
    request: Request,
    course_id: uuid.UUID,
    node_id: int,
    body: AnswerIn,
    session: SessionDep,
    user: CurrentUser,
    settings: SettingsDep,
    db: DatabaseDep,
) -> AnswerOut:
    """Проверка хода: ход курса — `main`; иначе движок (пул режима исследования) сравнивает
    потерю win% с порогом `COURSE_ALT_THRESHOLD`: `alternative` или `wrong`."""
    engine: PositionEngine = request.app.state.explore_engine
    evaluator = Evaluator(engine, DbEvalCache(db.sessionmaker), settings.course_engine_depth)
    try:
        result = await service.answer_card(
            session,
            user.id,
            course_id,
            node_id,
            body.uci,
            hint_used=body.hint_used,
            evaluator=evaluator,
            threshold=settings.course_alt_threshold,
            now=_now(),
        )
    except service.CourseMissingError as exc:
        raise _not_found() from exc
    except service.CourseNotReadyError as exc:
        raise _not_ready() from exc
    except service.CardMissingError as exc:
        raise ApiError(
            status.HTTP_404_NOT_FOUND, ErrorCode.TRAINER_CARD_NOT_FOUND, "Карточка не найдена"
        ) from exc
    except IllegalMoveError as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.VALIDATION_ERROR, str(exc)
        ) from exc
    except (EngineError, OSError) as exc:
        log.warning("trainer.engine_failed", error=repr(exc))
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            ErrorCode.ENGINE_UNAVAILABLE,
            "Движок недоступен",
        ) from exc
    return AnswerOut(
        verdict=result.verdict,
        expected=[ExpectedMove(uci=e.uci, san=e.san) for e in result.expected],
        win_loss=result.win_loss,
        box=result.box,
        next_review_at=result.next_review_at,
        ideas_node_id=result.ideas_node_id,
    )


@router.get("/trainer/summary")
async def summary(session: SessionDep, user: CurrentUser) -> list[CourseSummaryOut]:
    """По курсам пользователя с карточками: всего, пора повторять, новых, выучено (коробка ≥ 3)."""
    rows = await service.summary(session, user.id, _now())
    return [
        CourseSummaryOut(
            course_id=r.course_id,
            name=r.name,
            total=r.total,
            due=r.due,
            new=r.new,
            learned=r.learned,
        )
        for r in rows
    ]
