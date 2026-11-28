"""Курсы по дебютным линиям: каталог, сборка, дерево курса, «Мои курсы» (сессия 13).

Курс — общий для всех, у кого та же линия и цвет (`courses.key`), «Мои курсы» —
`user_courses`. Чужой курс (не в списке пользователя) — 404 того же вида, что
несуществующий."""

import asyncio
import uuid
from datetime import datetime
from typing import Annotated, Literal

import chess
import structlog
from fastapi import APIRouter, Query, Request, Response, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.api.deps import ArqDep, CurrentUser, SessionDep
from app.api.errors import ApiError, ErrorCode
from app.api.ratelimit import UserLimiterDep
from app.books.courses import book_model_games
from app.courses.builder import LineError, course_key, parse_line
from app.courses.catalog import Catalog, catalog_payload, line_opening, line_pgn, line_san
from app.courses.types import BUILDER_VERSION, CourseTree
from app.db.models import Color, Course, CourseStatus, TrainerCard, UserCourse
from app.plans.templates import render
from app.plans.types import RenderedIdeas
from app.workers.courses import enqueue_course

router = APIRouter(tags=["courses"])
log = structlog.get_logger(__name__)

CoursesLang = Literal["ru", "en"]
# Каталог меняется только с базой дебютов (вместе с релизом) — сутки в кэше браузера.
CATALOG_CACHE_CONTROL = "private, max-age=86400"


class CourseIn(BaseModel):
    # Длина и легальность линии проверяются отдельно (422 `line_invalid`); здесь — только
    # защита от мусора.
    line_uci: list[Annotated[str, Field(max_length=8)]] = Field(max_length=200)
    color: Literal["white", "black"]
    source: Literal["catalog", "repertoire"] = "catalog"
    name: Annotated[str, Field(max_length=255)] | None = None


class CourseOut(BaseModel):
    id: uuid.UUID
    name: str
    eco: str | None
    color: Literal["white", "black"]
    line_uci: list[str]
    line_san: list[str]
    # Откуда курс добавлен в «Мои курсы»: catalog | repertoire.
    source: str
    status: CourseStatus
    progress: int
    error_code: str | None
    added_at: datetime
    last_studied_at: datetime | None
    built_at: datetime | None

    @classmethod
    def of(cls, course: Course, entry: UserCourse) -> "CourseOut":
        try:
            sans = line_san(parse_line(course.line_uci))
        except LineError:  # pragma: no cover — линия проверена при создании
            sans = []
        return cls(
            id=course.id,
            name=course.name,
            eco=course.eco,
            color="white" if course.color == Color.WHITE else "black",
            line_uci=list(course.line_uci),
            line_san=sans,
            source=entry.source,
            status=course.status,
            progress=course.progress,
            error_code=course.error_code,
            added_at=entry.added_at,
            last_studied_at=entry.last_studied_at,
            built_at=course.built_at,
        )


class CourseDetailOut(CourseOut):
    # Есть только у готового курса (`status` = ready); пока курс собирается — null.
    tree: CourseTree | None
    # Тексты идей узлов с `ideas` на языке запроса; ключ — id узла.
    ideas_text: dict[int, RenderedIdeas]


def _not_found() -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.COURSE_NOT_FOUND, "Курс не найден")


@router.get("/courses/catalog", response_model=Catalog)
async def courses_catalog(request: Request, user: CurrentUser) -> Response:
    """Семейства → варианты → линии базы дебютов (поиск — на клиенте). Ответ кэшируемый:
    ETag и `Cache-Control`; gzip, если клиент его принимает (JSON ≈ 0,9 МБ, gzip ≈ 0,1 МБ)."""
    payload = await asyncio.to_thread(catalog_payload)
    headers = {
        "ETag": payload.etag,
        "Cache-Control": CATALOG_CACHE_CONTROL,
        "Vary": "Accept-Encoding",
    }
    if payload.etag in request.headers.get("if-none-match", ""):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    if "gzip" in request.headers.get("accept-encoding", ""):
        return Response(
            payload.gzip,
            media_type="application/json",
            headers=headers | {"Content-Encoding": "gzip"},
        )
    return Response(payload.json, media_type="application/json", headers=headers)


@router.post("/courses", status_code=status.HTTP_202_ACCEPTED)
async def create_course(
    body: CourseIn,
    *,
    session: SessionDep,
    arq: ArqDep,
    user: CurrentUser,
    limiter: UserLimiterDep,
    response: Response,
) -> CourseOut:
    """Курс по линии за цвет и добавление в «Мои курсы». Идемпотентно: та же линия и цвет —
    тот же курс (200). Новый курс (или повтор упавшего) ставится в очередь сборки (202),
    лимит `course` тратят только они."""
    try:
        line = parse_line(body.line_uci)
    except LineError as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ErrorCode.LINE_INVALID,
            str(exc),
            params={"index": exc.index} if exc.index is not None else None,
        ) from exc
    color = chess.WHITE if body.color == "white" else chess.BLACK
    key = course_key(color, line)

    by_key = (
        select(Course)
        .where(Course.key == key)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    course = await session.scalar(by_key)
    build = retry = False
    if course is None:
        await limiter.hit("course")
        found_name, eco = line_opening(line)
        name = (body.name or "").strip() or found_name or line_pgn(line)
        await session.execute(
            insert(Course)
            .values(
                id=uuid.uuid4(),
                key=key,
                color=Color(body.color),
                name=name[:255],
                eco=eco,
                line_uci=[m.uci() for m in line],
                status=CourseStatus.QUEUED,
                progress=0,
                builder_version=BUILDER_VERSION,
                created_by=user.id,
            )
            .on_conflict_do_nothing(index_elements=["key"])
        )
        course = await session.scalar(by_key)
        assert course is not None
        build = True
    elif course.status == CourseStatus.FAILED:
        await limiter.hit("course")
        course.status = CourseStatus.QUEUED
        course.progress = 0
        course.error_code = None
        build = retry = True
    await session.execute(
        insert(UserCourse)
        .values(user_id=user.id, course_id=course.id, source=body.source)
        .on_conflict_do_nothing()
    )
    await session.commit()

    if build or course.status == CourseStatus.QUEUED:
        # У курса в очереди задача могла потеряться (Redis очищен); ARQ не дублирует её.
        try:
            await enqueue_course(arq, course.id, retry=retry)
        except Exception as exc:
            log.exception("course.enqueue_failed", course_id=str(course.id))
            course.status = CourseStatus.FAILED
            course.error_code = ErrorCode.ENQUEUE_FAILED
            await session.commit()
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                ErrorCode.QUEUE_UNAVAILABLE,
                "Очередь сборки курсов недоступна",
            ) from exc
    if not build:
        response.status_code = status.HTTP_200_OK
    entry = await session.get(UserCourse, (user.id, course.id))
    assert entry is not None
    await session.refresh(course)
    return CourseOut.of(course, entry)


@router.get("/courses")
async def list_courses(session: SessionDep, user: CurrentUser) -> list[CourseOut]:
    """«Мои курсы» со статусом и прогрессом сборки, недавно добавленные первыми."""
    rows = (
        await session.execute(
            select(Course, UserCourse)
            .join(UserCourse, UserCourse.course_id == Course.id)
            .where(UserCourse.user_id == user.id)
            .order_by(UserCourse.added_at.desc(), Course.id)
        )
    ).all()
    return [CourseOut.of(course, entry) for course, entry in rows]


async def _owned(
    session: SessionDep, user_id: uuid.UUID, course_id: uuid.UUID
) -> tuple[Course, UserCourse]:
    row = (
        await session.execute(
            select(Course, UserCourse)
            .join(UserCourse, UserCourse.course_id == Course.id)
            .where(UserCourse.user_id == user_id, Course.id == course_id)
        )
    ).first()
    if row is None:
        raise _not_found()
    return row[0], row[1]


@router.get("/courses/{course_id}")
async def get_course(
    course_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    lang: Annotated[CoursesLang | None, Query()] = None,
) -> CourseDetailOut:
    """Курс с деревом и текстами идей ключевых узлов; язык по умолчанию — язык пользователя.
    Пока курс собирается, `tree` = null (страница опрашивает статус и прогресс)."""
    course, entry = await _owned(session, user.id, course_id)
    chosen: CoursesLang = lang if lang is not None else ("en" if user.lang == "en" else "ru")
    tree: CourseTree | None = None
    if course.status == CourseStatus.READY and course.tree is not None:
        try:
            tree = CourseTree.model_validate(course.tree)
        except ValidationError:
            log.exception("course.tree_invalid", course_id=str(course.id))
    if tree is not None:
        # Партии из книг — по позициям дерева, без пересборки курса.
        tree.model_games = [
            *(g for g in tree.model_games if g.source != "book"),
            *book_model_games(tree),
        ]
    ideas_text = (
        {node.id: render(node.ideas, chosen) for node in tree.nodes if node.ideas is not None}
        if tree is not None
        else {}
    )
    base = CourseOut.of(course, entry)
    return CourseDetailOut(**base.model_dump(), tree=tree, ideas_text=ideas_text)


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(course_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    """Убрать курс из «Моих курсов» вместе с карточками тренажёра по нему (иначе очередь
    тренажёра продолжала бы их показывать). Сам курс остаётся — он общий."""
    await _owned(session, user.id, course_id)
    for model in (TrainerCard, UserCourse):
        await session.execute(
            delete(model).where(model.user_id == user.id, model.course_id == course_id)
        )
    await session.commit()
