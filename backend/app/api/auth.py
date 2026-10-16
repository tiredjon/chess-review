"""Регистрация, вход, обновление токена, выход, профиль.

Access-токен — в теле ответа (клиент держит его в памяти и шлёт `Authorization: Bearer`),
refresh-токен — в httpOnly-cookie с путём `/api/v1/auth`: JavaScript его не видит,
и в остальные запросы API он не уходит.
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status

from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.api.errors import ApiError, ErrorCode
from app.api.ratelimit import limit_ip
from app.api.schemas import AuthOut, LoginIn, ProfileIn, RegisterIn, UserOut
from app.auth import service
from app.auth.service import AuthError
from app.auth.tokens import create_token
from app.core.config import Settings

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "cr_refresh"
COOKIE_PATH = "/api/v1/auth"

RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]

_STATUS = {
    ErrorCode.EMAIL_TAKEN: status.HTTP_409_CONFLICT,
    ErrorCode.INVALID_CREDENTIALS: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.REFRESH_INVALID: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.REFRESH_ROTATED: status.HTTP_401_UNAUTHORIZED,
}
_MESSAGES = {
    ErrorCode.EMAIL_TAKEN: "Этот email уже зарегистрирован",
    ErrorCode.INVALID_CREDENTIALS: "Неверный email или пароль",
    ErrorCode.REFRESH_INVALID: "Сессия истекла, войдите заново",
    ErrorCode.REFRESH_ROTATED: "Сессия только что обновлена, повторите запрос",
}


def _api_error(exc: AuthError) -> ApiError:
    return ApiError(_STATUS[exc.code], exc.code, _MESSAGES[exc.code])


def _check_origin(request: Request, settings: Settings) -> None:
    """Cookie-эндпоинты принимают запросы только со своих origin (защита от CSRF, если
    cookie когда-нибудь станет SameSite=None). Без заголовка Origin (curl) — можно."""
    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.cors_origins:
        raise ApiError(
            status.HTTP_403_FORBIDDEN, ErrorCode.ORIGIN_FORBIDDEN, "Запрос с чужого сайта"
        )


def _set_refresh_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_ttl_days * 86400,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


def _auth_out(response: Response, settings: Settings, session: service.Session) -> AuthOut:
    _set_refresh_cookie(response, settings, session.refresh_token)
    # Ответы с токенами не кэшируются ни браузером, ни прокси.
    response.headers["Cache-Control"] = "no-store"
    return AuthOut(
        access_token=create_token(settings, session.user.id),
        expires_in=settings.access_token_ttl_s,
        user=UserOut.model_validate(session.user),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, dependencies=[limit_ip("register")])
async def register(
    body: RegisterIn,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> AuthOut:
    _check_origin(request, settings)
    try:
        auth = await service.register(session, settings, body.email, body.password, body.lang)
    except AuthError as exc:
        raise _api_error(exc) from exc
    return _auth_out(response, settings, auth)


@router.post("/login", dependencies=[limit_ip("login")])
async def login(
    body: LoginIn,
    *,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> AuthOut:
    _check_origin(request, settings)
    try:
        auth = await service.login(session, settings, body.email, body.password)
    except AuthError as exc:
        raise _api_error(exc) from exc
    return _auth_out(response, settings, auth)


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    token: RefreshCookie = None,
) -> AuthOut:
    """Новый access-токен и следующий refresh-токен цепочки (ротация)."""
    _check_origin(request, settings)
    if not token:
        raise _api_error(AuthError(ErrorCode.REFRESH_INVALID))
    try:
        auth = await service.refresh(session, settings, token)
    except AuthError as exc:
        error = _api_error(exc)
        if exc.code == ErrorCode.REFRESH_INVALID:
            # Cookie больше ни на что не годен — убрать его из браузера.
            cleared = Response()
            _clear_refresh_cookie(cleared, settings)
            error.headers = {"set-cookie": cleared.headers["set-cookie"]}
        raise error from exc
    return _auth_out(response, settings, auth)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    token: RefreshCookie = None,
) -> Response:
    """Выход: отзыв refresh-токенов этого входа и удаление cookie. Access-токен живёт
    до своего срока (`ACCESS_TOKEN_TTL_S`), клиент его просто забывает."""
    _check_origin(request, settings)
    if token:
        await service.logout(session, token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(response, settings)
    return response


@router.get("/me")
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me")
async def update_me(body: ProfileIn, session: SessionDep, user: CurrentUser) -> UserOut:
    """Язык (интерфейс, объяснения, итог партии) и ники Lichess / Chess.com (по ним
    определяется цвет пользователя во вставленных PGN)."""
    fields = body.model_fields_set
    if "lang" in fields and body.lang is not None:
        user.lang = body.lang
    if "lichess_username" in fields:
        user.lichess_username = body.lichess_username or None
    if "chesscom_username" in fields:
        user.chesscom_username = body.chesscom_username or None
    await session.commit()
    return UserOut.model_validate(user)
