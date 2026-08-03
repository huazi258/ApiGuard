# ApiGuard

ApiGuard V0 converts confirmed OpenAPI contract requirements and explicit business
rules into bounded, reproducible API verification evidence. It is designed for
local and test environments, not production.

## Current milestone

Milestone 1 and the Milestone 2 persistence implementation are complete.
Formal M2 sealing still requires the canonical `uv` gate in an environment where
the `uv` executable is available. Milestone 3 has not started.

- M2-01: domain entity reconstitution is complete.
- M2-02: SQLite schema and the initial Alembic migration are complete.
- M2-03: Task and Attempt ORM mappers are complete.
- M2-04: application persistence ports, repositories, and Unit of Work are complete.
- M2-05: full file-SQLite persistence acceptance is complete.

| Task | Result | Commit |
| --- | --- | --- |
| M1-01 | Python repository and quality gates | `cf3907c9e5b7adb1a2964e695444c1feaae62a4f` |
| M1-02 | Settings, logging, FastAPI shell, and `/health` | `c42e8a9275af35eacc88b70c29cd1670097a91bf` |
| M1-03 | Shared enums, IDs, and errors | `9e24836e85803f25d924a299e055be37c6a93ae1` |
| M1-04 | VerificationTask lifecycle | `7c82b86280156277d0fa8e078001a51147399344` |
| M1-05 | ValidationAttempt lifecycle | `9a26ef5d710144382796bd4c370fa50f1ae0f35c` |
| M1-06 | Baseline archiving and milestone documentation | This commit |

The PowerShell documentation-only correction is `ab88a5c92f15683ef787a1d17a500f8e8a844b17`; it is not a separate milestone task.

### Implemented in milestone 1

- Python 3.12 project, uv lockfile, pytest, Ruff, and Pyright quality gates.
- FastAPI process shell and process-only `GET /health` endpoint.
- Frozen shared enums, strong nominal ID types, and minimal domain errors.
- VerificationTask preparation, confirmation, and cancellation lifecycle.
- ValidationAttempt execution/completion lifecycle and three-send hard limit.

### Current persistence foundation

- SQLite file path configuration: `APIGUARD_DATABASE_PATH` (default
  `data/apiguard.db`).
- One SQLAlchemy Metadata with eleven structural ORM Row tables and one Alembic
  initial migration.
- File-backed SQLite connections use foreign keys, WAL, synchronous NORMAL, and
  a five-second busy timeout.
- Task and Attempt state persist and recover across Unit of Work and Engine
  recreation; executing attempts can be queried by execution intent or as a
  stable ordered list.
- EvidenceBundle and DerivedReport records are append-only. Attempt completion
  and EvidenceBundle insertion can commit atomically.

Apply the schema explicitly; application startup never migrates a database:

```bash
uv run alembic upgrade head
```

`/health` remains process-only and does not connect to SQLite.

### Not implemented

- OpenAPI reading/parsing, plan data contracts, and plan validation.
- HTTP execution and deterministic evaluation.
- Model calls, product API, report generation, and Jinja2 pages.
- Startup recovery (including handling legacy EXECUTING attempts).

See [Milestone 2 persistence acceptance](docs/milestones/milestone-02-persistence-acceptance.md).

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Setup and quality gates

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
```

## Start the application

```bash
uv run uvicorn apiguard.main:app --reload
```

`GET /health` returns `{"status": "ok"}` only when the ApiGuard process can
serve requests. It does not check a database, model provider, or verification
capability.

Non-secret settings use the `APIGUARD_` environment-variable prefix. For example:

```bash
$env:APIGUARD_TARGET_HTTP_REQUEST_TIMEOUT_SECONDS = "30"
$env:APIGUARD_DATABASE_PATH = "data/apiguard.db"
uv run uvicorn apiguard.main:app
```

## Package layout

The project uses a `src/` layout. Runtime dependencies are FastAPI,
pydantic-settings, Uvicorn, SQLAlchemy 2.x, and Alembic; pytest, Ruff, Pyright,
and HTTPX (for FastAPI's TestClient) are development dependencies managed by uv.

## Frozen project documents

- [V0 scope baseline](docs/baselines/00-v0-scope.md)
- [V0 architecture baseline](docs/baselines/01-v0-architecture.md)
- [V0 technical design and development baseline](docs/baselines/02-v0-technical-design-and-development.md)
- [Milestone 1 task cards](docs/codex/milestone-01-task-cards.md)

The technical design baseline preserves the frozen implementation naming:
`EvidencePackage` is implemented as `EvidenceBundle`, and `HumanReadableReport`
is implemented as `DerivedReport`; their business meaning and authority boundary
do not change.

## Facts and evidence

```text
仓库代码、迁移、测试和真实运行结果
> 仓库中的冻结基线与任务说明
> Codex 完成报告
> 聊天记录
```

Chat is not the source of truth for project behavior or design. ApiGuard does not
yet execute real API verification tasks.
