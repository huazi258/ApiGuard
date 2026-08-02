# ApiGuard

ApiGuard V0 will turn confirmed OpenAPI contract requirements and explicit business
rules into bounded, reproducible API verification evidence. It is intended for
local and test environments, not production.

## Current milestone

Milestone 1 currently includes M1-01 (quality gates) and M1-02 (configuration,
logging, and the FastAPI process-health shell). No domain model, state machine,
database, HTTP executor, model integration, or product web interface has been
implemented.

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
APIGUARD_TARGET_HTTP_REQUEST_TIMEOUT_SECONDS=30 uv run uvicorn apiguard.main:app
```

## Package layout

The project uses a `src/` layout. Runtime dependencies are FastAPI,
pydantic-settings, and Uvicorn; pytest, Ruff, Pyright, and HTTPX (for FastAPI's
TestClient) are development dependencies managed by uv.
