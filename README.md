# Backend Template

Production-ready FastAPI backend: async SQLAlchemy 2 + Alembic migrations, optional Redis,
JWT auth, request-correlated logging, a consistent error format, Docker and tests.

```
2026-10-06 10:25:25 Backend Template INFO    Starting Backend Template v0.1.0 (development)...
2026-10-06 10:25:25 Backend Template INFO    Initializing database connection...
2026-10-06 10:25:25 Backend Template INFO    Database connection successful (postgresql+asyncpg://postgres:***@localhost:5432/app)
2026-10-06 10:25:25 Backend Template INFO    Redis connection successful
2026-10-06 10:25:25 Backend Template INFO    Backend Template started successfully
2026-10-06 10:26:14 Backend Template WARNING Handled error path=/api/v1/auth/me code=unauthorized message=Not signed in  [990df440d022438f8b8dce19a2a05360]
2026-10-06 10:26:14 Backend Template INFO    GET /api/v1/auth/me -> 401 (4.3ms)  [990df440d022438f8b8dce19a2a05360]
```

## Project layout

```
├── alembic/                  # migrations (env.py reads DATABASE_URL from app settings)
│   └── versions/
├── scripts/
│   ├── create_superuser.py   # uv run python -m scripts.create_superuser --email ...
│   └── entrypoint.sh         # container entrypoint: migrate, then serve
├── src/
│   ├── core/                 # cross-cutting: config, logging, errors, security, lifespan
│   ├── db/                   # declarative Base + mixins, engine/session
│   ├── middleware/           # request id + access log + crash guard, CORS, GZip
│   ├── models/               # SQLAlchemy ORM models (register new ones in __init__.py)
│   ├── modules/              # API routers (one file per feature) + shared dependencies
│   ├── providers/            # external integrations (Redis cache, ...)
│   ├── schemas/              # Pydantic request/response models
│   ├── services/             # business logic, the only layer that talks to the DB
│   ├── utils/                # small helpers (pagination, time)
│   └── main.py               # create_app(): logging -> middleware -> handlers -> routers
└── tests/                    # pytest + httpx, schema built by the real migrations
```

Request flow: `modules` (HTTP) → `services` (logic) → `models` (DB). Routes stay thin; services
raise `AppError` subclasses (`NotFoundError`, `ConflictError`, ...) and never import FastAPI.

## Quick start

Requires [uv](https://docs.astral.sh/uv/). Python 3.12 is installed automatically.

```bash
uv sync                                   # create .venv and install everything
cp .env.example .env                      # then edit DATABASE_URL / JWT_SECRET_KEY
docker compose up -d db redis             # Postgres + Redis (or use your own)
uv run alembic upgrade head               # create the schema
uv run uvicorn src.main:app --reload      # http://127.0.0.1:8000/docs
```

No Docker? Set `DATABASE_URL=sqlite+aiosqlite:///./app.db` and `REDIS_URL=` in `.env`.

Create an admin account:

```bash
uv run python -m scripts.create_superuser --email admin@example.com
```

## Endpoints

| Method | Path                    | Auth       | Purpose                              |
| ------ | ----------------------- | ---------- | ------------------------------------ |
| GET    | `/`                     | –          | Service name, version, environment   |
| GET    | `/health`               | –          | Liveness probe                       |
| GET    | `/health/ready`         | –          | Readiness: checks database and Redis |
| POST   | `/api/v1/auth/register` | –          | Create an account                    |
| POST   | `/api/v1/auth/login`    | –          | OAuth2 password form → JWT           |
| GET    | `/api/v1/auth/me`       | user       | Current user                         |
| PATCH  | `/api/v1/users/me`      | user       | Update name/password                 |
| GET    | `/api/v1/users/{id}`    | self/admin | Get a user                           |
| GET    | `/api/v1/users`         | admin      | Paginated list (`limit`, `offset`)   |

In Swagger (`/docs`), click **Authorize** and log in with your email as the username.

## Migrations (Alembic)

```bash
uv run alembic revision --autogenerate -m "add posts table"   # after changing models
uv run alembic upgrade head                                    # apply
uv run alembic downgrade -1                                    # roll back one
uv run alembic check                                           # fail if models != migrations
uv run alembic upgrade head --sql                              # print SQL, don't run it
```

- New models must be imported in `src/models/__init__.py`, or autogenerate won't see them.
- Always read a generated migration before applying it. Autogenerate can't detect renames.
- Constraint names are deterministic (`src/db/base.py`), so later migrations can drop or alter them.
- Generated files are formatted with ruff automatically and named `YYYY_MM_DD_HHMM-<rev>_<slug>.py`.

## Logging

| Setting      | Values                | Use                                              |
| ------------ | --------------------- | ------------------------------------------------ |
| `LOG_FORMAT` | `console` / `json`    | colored lines for humans; JSON lines for Loki/ELK |
| `LOG_LEVEL`  | `DEBUG` … `CRITICAL`  |                                                  |
| `LOG_FILE`   | e.g. `logs/app.log`   | also writes a rotating JSON file (10 MB × 5)      |
| `DB_ECHO`    | `true` / `false`      | log every SQL statement                          |

- Every request gets an id (or reuses a valid incoming `X-Request-ID`), returned in the
  `X-Request-ID` response header and appended to **every** log line written during that request.
- One access line per request: `GET /path -> 200 (12.3ms)`. `/health` is logged at DEBUG, so
  load-balancer probes don't flood the logs.
- In your code: `logger = logging.getLogger(__name__)`, then
  `logger.info("Order paid id=%s", order.id)`. Fields passed via `extra={...}` become JSON keys.

## Errors

Every error response uses the same shape:

```json
{"error": {"code": "not_found", "message": "User not found", "details": null, "request_id": "81d9e1..."}}
```

- `raise NotFoundError("User not found")` / `ConflictError(..., code="email_taken")` from anywhere.
- Validation errors → `422 validation_error` with per-field `details`.
- Unhandled exceptions → full traceback in the log, plain `500 internal_error` to the client.

## Adding a feature (e.g. "posts")

1. `src/models/post.py` → import it in `src/models/__init__.py`
2. `uv run alembic revision --autogenerate -m "create posts"` → review → `alembic upgrade head`
3. `src/schemas/post.py`: `PostCreate`, `PostRead`, ...
4. `src/services/post_service.py`: `PostService(session)`
5. `src/modules/posts.py`: `router = APIRouter(prefix="/posts", tags=["posts"])`
6. Register it in `src/modules/router.py`, then add tests in `tests/test_posts.py`

## Development

```bash
uv run pytest                 # tests (SQLite, no services needed)
uv run ruff check --fix .     # lint
uv run ruff format .          # format
```

## Docker

```bash
docker compose up --build     # Postgres + Redis + API at http://localhost:8000
```

The image is multi-stage (uv), runs as a non-root user, applies migrations on start
(`scripts/entrypoint.sh`) and defaults to `ENVIRONMENT=production` and `LOG_FORMAT=json`.
In production, `JWT_SECRET_KEY` must be set or the app refuses to start. Use
`WEB_CONCURRENCY` to run multiple workers.
