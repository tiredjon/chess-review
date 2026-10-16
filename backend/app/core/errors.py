"""Машинные коды ошибок: ответы API (`app/api/errors.py`) и ошибки фоновых задач
(`analyses.error_code`, `import_jobs.error_code`). Тексты к ним — в словарях интерфейса
(`web/src/lib/i18n`), поэтому коды менять нельзя, только добавлять."""

from enum import StrEnum


class ErrorCode(StrEnum):
    # Auth
    NOT_AUTHENTICATED = "not_authenticated"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"
    REFRESH_INVALID = "refresh_invalid"
    # Refresh-токен только что заменён (параллельное обновление): повторить с новым cookie.
    REFRESH_ROTATED = "refresh_rotated"
    ORIGIN_FORBIDDEN = "origin_forbidden"
    EMAIL_TAKEN = "email_taken"
    INVALID_CREDENTIALS = "invalid_credentials"
    RATE_LIMITED = "rate_limited"
    # Ресурсы
    GAME_NOT_FOUND = "game_not_found"
    ANALYSIS_NOT_FOUND = "analysis_not_found"
    ANALYSIS_NOT_READY = "analysis_not_ready"
    MOVE_NOT_FOUND = "move_not_found"
    IMPORT_NOT_FOUND = "import_not_found"
    PUZZLE_NOT_FOUND = "puzzle_not_found"
    PUZZLE_ATTEMPT_INVALID = "puzzle_attempt_invalid"
    INVALID_CURSOR = "invalid_cursor"
    # Публичная ссылка на разбор (`/shared/{token}`): неизвестный или отозванный токен.
    SHARE_NOT_FOUND = "share_not_found"
    # PGN
    PGN_INVALID = "pgn_invalid"
    PGN_TOO_MANY = "pgn_too_many"
    PGN_EMPTY = "pgn_empty"
    PGN_VARIANT = "pgn_variant"
    PGN_NO_MOVES = "pgn_no_moves"
    # Очередь и фоновые задачи (в т. ч. `analyses.error_code`, `import_jobs.error_code`)
    QUEUE_UNAVAILABLE = "queue_unavailable"
    ENQUEUE_FAILED = "enqueue_failed"
    INTERRUPTED = "interrupted"
    INTERNAL = "internal"
    SOURCE_USER_NOT_FOUND = "source_user_not_found"
    SOURCE_RATE_LIMITED = "source_rate_limited"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_BAD_RESPONSE = "source_bad_response"
    # Telegram-бот: у пользователя площадки нет партий в классические шахматы.
    SOURCE_NO_GAMES = "source_no_games"
    # Движок: анализ из браузера и режим исследования (сессия 11)
    ENGINE_DATA_INVALID = "engine_data_invalid"
    DEPTH_TOO_LOW = "depth_too_low"
    INVALID_FEN = "invalid_fen"
    ENGINE_UNAVAILABLE = "engine_unavailable"
    # Общие
    VALIDATION_ERROR = "validation_error"
    HTTP_ERROR = "http_error"
