# Milestone 2 persistence acceptance

## Scope

M2 delivers domain reconstitution, the frozen eleven-table SQLite schema and
single initial Alembic migration, Task/Attempt mappers, application persistence
ports, SQLAlchemy repositories, and a synchronous Unit of Work. It does not
deliver OpenAPI reading, planning, HTTP execution, model calls, product APIs,
report generation, or startup recovery.

## Results index

- M2-01: entity reconstitution.
- M2-02: SQLite ORM schema and initial migration.
- M2-03: Task and Attempt value conversion and mapping.
- M2-04: persistence ports, repositories, and Unit of Work.
- M2-05: file-SQLite/Alembic integration acceptance.

## Acceptance evidence

The integration suite creates empty temporary files through `alembic upgrade
head`, then verifies Task READY/CANCELLED and Attempt EXECUTING/COMPLETED
recovery across Engine recreation, execution-intent lookup, append-only
evidence, atomic completion, and rollback on a final constraint failure.

## Verification

```bash
uv sync
uv run alembic upgrade head
uv run pytest tests/integration/persistence -q
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

The known non-blocking warning is Starlette's third-party TestClient warning
about its HTTPX usage. Milestone 3 begins with OpenAPI context and plan data
contracts. The canonical `uv` gate remains pending when the host environment
does not provide a `uv` executable; locked `.venv` verification is supplementary.
