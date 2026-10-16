# Chess Review

Разбор шахматных партий в духе Game Review на Chess.com, но на открытом движке и с честными объяснениями:

- точность игрока за партию и по фазам (формула Lichess и приближение формулы Chess.com), рейтинг партии;
- класс каждого хода — от «блестящего» до «зевка», плюс «упущение»;
- тактические мотивы (вилка, связка, мат по последней горизонтали…) для сыгранного хода, упущенной линии и опровержения;
- объяснения человеческим языком, построенные только на фактах из анализа Stockfish (LLM по желанию; без ключа работают шаблоны);
- импорт партий с Lichess, Chess.com и вставкой PGN;
- статистика по всем партиям и пазлы из собственных ошибок с интервальным повторением;
- интерфейс и объяснения на русском и английском.

Полное ТЗ, все принятые решения и заметки по окружению — в [SPEC.md](SPEC.md).

## Стек

| Слой | Технологии |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic |
| Шахматы | python-chess, Stockfish 19 (пул UCI-процессов) |
| Очередь | ARQ на Redis: анализ и импорт — фоновые задачи |
| БД | PostgreSQL 17 |
| Auth | свой JWT (access в памяти браузера, refresh в httpOnly-cookie с ротацией), пароли — argon2id |
| LLM | Gemini / OpenAI / Anthropic через официальные SDK или без LLM (шаблоны) |
| Frontend | Next.js 16 (App Router, Cache Components), React 19, TypeScript, Tailwind 4, react-chessboard, chess.js, Recharts |
| Тесты | pytest + pytest-asyncio, Playwright (smoke) |
| Инфра | Docker Compose: postgres, redis, migrate, api, worker, web |

## Запуск

Нужны Docker (Compose v2) и `make`.

```bash
cp .env.example .env && make up
```

После старта: интерфейс — http://localhost:3000, API — http://localhost:8000 (`/docs` — OpenAPI). Порты меняются в `.env` (`WEB_PORT`, `API_PORT`, …); при смене `WEB_PORT` добавьте новый origin в `CORS_ORIGINS`.

Первый зарегистрированный пользователь получает запись dev-пользователя из начальной миграции — вместе с партиями, анализами и пазлами, которые были загружены до появления входа (отключается `AUTH_CLAIM_DEV_USER=false`).

Полезные команды (`make help` — все):

| Команда | Что делает |
|---|---|
| `make up` / `make down` | поднять / остановить весь стек |
| `make logs` | логи всех сервисов |
| `make services` | только postgres и redis (для локальной разработки и тестов) |
| `make install` | зависимости backend (`uv sync`) и web (`npm ci`) |
| `make migrate` | миграции к локальной БД |
| `make test` | линтеры, mypy, tsc и все тесты backend |
| `make test-docker` | тесты backend в Docker-образе (там есть Stockfish) |
| `make e2e` | Playwright smoke по поднятому стеку |

Локально без Docker: `make services`, затем `cd backend && uv run alembic upgrade head && uv run uvicorn app.main:create_app --factory --reload`, воркер — `uv run arq app.workers.settings.WorkerSettings`, web — `cd web && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev`. Для анализа нужен Stockfish в `PATH` (`brew install stockfish`).

## Переменные окружения

Все — в [.env.example](.env.example) с комментариями. Главные:

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `APP_ENV` | `dev` | `dev` / `test` / `prod`; в `prod` обязателен `JWT_SECRET` |
| `API_PORT`, `WEB_PORT`, `POSTGRES_PORT`, `REDIS_PORT` | 8000, 3000, 5432, 6379 | порты на хосте |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | origin фронтенда (запросы идут из браузера с cookie) |
| `DATABASE_URL`, `REDIS_URL` | localhost | для запуска вне Docker (в compose переопределяются) |
| `JWT_SECRET` | — | ключ подписи токенов; `openssl rand -base64 32`. Без него в dev ключ случайный на каждый запуск API |
| `ACCESS_TOKEN_TTL_S`, `REFRESH_TOKEN_TTL_DAYS` | 900, 30 | срок access- и refresh-токенов |
| `COOKIE_SECURE`, `COOKIE_SAMESITE` | `false`, `lax` | cookie refresh-токена: `true` за HTTPS; `none` — если web и API на разных сайтах |
| `AUTH_CLAIM_DEV_USER` | `true` | первый зарегистрированный получает данные dev-пользователя |
| `RATE_LIMIT_ENABLED` | `true` | лимиты запросов (Redis) |
| `RATE_LIMIT_IMPORT`, `RATE_LIMIT_ANALYZE`, `RATE_LIMIT_LLM` | 30/hour, 100/hour, 300/hour | на пользователя; LLM не считается при `LLM_PROVIDER=none` |
| `RATE_LIMIT_LOGIN`, `RATE_LIMIT_REGISTER` | 10/minute, 10/hour | на IP (`TRUST_FORWARDED_FOR=true` — IP из `X-Forwarded-For` за своим прокси) |
| `STOCKFISH_PATH`, `ENGINE_POOL_SIZE`, `ENGINE_THREADS`, `ENGINE_HASH_MB` | `stockfish`, 4, 1, 128 | движок и пул процессов |
| `ANALYSIS_DEPTH`, `ANALYSIS_MULTIPV` | 18, 3 | глубина анализа и число линий |
| `WORKER_MAX_JOBS`, `ANALYSIS_JOB_TIMEOUT_S` | 2, 1800 | партий одновременно в воркере и таймаут одной |
| `IMPORT_USER_AGENT`, `LICHESS_TOKEN` | — | User-Agent обязателен для Lichess; токен необязателен (быстрее выгрузка) |
| `LLM_PROVIDER` | `none` | `none` / `gemini` / `openai` / `anthropic`; ключ — `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` |
| `LLM_MODEL` | — | своя модель вместо модели по умолчанию провайдера |

## Тема Chess.com (необязательно)

По умолчанию доска — процедурная «деревянная», фигуры — набор Celtic (MIT, `web/public/pieces/`), звуков нет. Для личного использования можно положить картинки и звуки Chess.com в `web/public/chesscom/` (папка в `.gitignore`, в репозиторий не попадает):

- `pieces/{wk,wq,wr,wb,wn,wp,bk,bq,br,bb,bn,bp}.png` — фигуры, например набор `neo_wood` 300 px: `https://images.chesscomfiles.com/chess-themes/pieces/neo_wood/300/wk.png`;
- `board.png` — доска 8×8 без координат (приложение рисует свои);
- `sounds/*.mp3` — `move-self`, `move-opponent`, `capture`, `castle`, `move-check`, `promote`, `game-start`, `game-end`, `illegal`, `correct`, `incorrect`, `notify` из `https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/<имя>.mp3`.

curl и скрипты упираются в проверку Cloudflare, поэтому файлы сохраняются из обычной вкладки браузера: открыть ссылку и сохранить, или выполнить `fetch(...)` в консоли страницы на localhost (CDN отдаёт картинки с CORS). Наличие проверяется по `pieces/wk.png` и `board.png`; файлы подхватываются после перезагрузки страницы. Подробности — «Заметки по окружению» в SPEC.md.

## Тесты

```bash
make test
```

Линтеры (ruff, mypy strict, eslint, tsc) и все тесты backend: доменная логика на фиксированных позициях, API на тестовой БД `chess_review_test` (пересоздаётся на каждый прогон) и Redis-базе 15, воркер — на фейковом движке. Тесты с настоящим Stockfish пропускаются, если его нет локально; в Docker-образе — обязательны (`make test-docker`). Сетевые тесты против живых Lichess / Chess.com: `cd backend && NETWORK_TESTS=1 uv run pytest tests/test_import_live.py`.

Smoke в браузере (регистрация → вход → вставка PGN → анализ по SSE → разбор → статистика → пазл → выход) — по уже поднятому стеку, в `make test` не входит:

```bash
make up && make e2e
```

Браузер — установленный Google Chrome; без него — `cd web && npx playwright install chromium` и `E2E_CHANNEL= make e2e`. Другой адрес фронтенда — `E2E_BASE_URL=http://localhost:3001 make e2e`.

## Пазлы для уже разобранных партий

Пазлы создаются воркером сразу после анализа. Для анализов, сделанных раньше (или после изменения правил отбора), — бэкфилл:

```bash
docker compose exec worker python scripts/generate_puzzles.py
```

или локально `cd backend && PYTHONPATH=. uv run python scripts/generate_puzzles.py` (нужен Stockfish). Повторный запуск безопасен: состояние повторения уже существующих пазлов сохраняется.

## Структура репозитория

```
backend/
  app/
    api/        роуты v1 (auth, games, analyses, imports, explain, stats, puzzles), схемы, ошибки с кодами, лимиты
    auth/       пароли (argon2), JWT, refresh-токены с ротацией
    core/       конфиг, логирование, коды ошибок, разбор лимитов
    db/         модели SQLAlchemy, сессии, выбор показываемой точности
    engine/     пул Stockfish, анализатор позиций, кэш оценок
    review/     чистая доменная логика: win%, точность, классы, фазы, дебюты, мотивы, pipeline
    explain/    факты для объяснений, шаблоны RU/EN, провайдеры LLM, проверка SAN, кэш
    importers/  Lichess, Chess.com, PGN
    puzzles/    генерация пазлов и интервальное повторение
    stats/      агрегаты статистики в SQL
    workers/    ARQ-задачи: анализ, импорт, прогресс в Redis
  alembic/      миграции
  scripts/      база дебютов, калибровка точности, бэкфилл пазлов
  tests/        pytest
web/
  src/app/      страницы: (auth) — вход и регистрация, (app) — главная, партии, разбор, статистика, пазлы, профиль
  src/components/
  src/lib/      клиент API и сессии, i18n (словари RU/EN), шахматные утилиты, тема доски, звуки
  e2e/          Playwright smoke
docker-compose.yml, Makefile, .env.example, SPEC.md
```
