"""Ошибки API с машинным кодом.

Ответ ошибки: `{"detail": "<текст для отладки>", "code": "<код>", "params": {...}}`.
Интерфейс показывает текст по `code` и `params` на языке пользователя (словари
`web/src/lib/i18n`), `detail` — для curl и логов. Ошибки валидации запроса —
`code = "validation_error"`, `detail` — список FastAPI как раньше.

Коды — `app/core/errors.py`; те же коды пишутся в `analyses.error_code` /
`import_jobs.error_code`.
"""

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import ErrorCode

__all__ = ["ApiError", "ErrorCode", "install_error_handlers"]


class ApiError(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code, message, headers=headers)
        self.code = code
        self.params = params or {}


def _body(detail: Any, code: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"detail": detail, "code": code, "params": params or {}}


async def _api_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return JSONResponse(
        _body(exc.detail, exc.code, exc.params), exc.status_code, headers=exc.headers
    )


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return JSONResponse(
        _body(exc.detail, ErrorCode.HTTP_ERROR), exc.status_code, headers=exc.headers
    )


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return JSONResponse(_body(jsonable_encoder(exc.errors()), ErrorCode.VALIDATION_ERROR), 422)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
