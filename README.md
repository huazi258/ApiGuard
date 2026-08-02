# ApiGuard

ApiGuard V0 will turn confirmed OpenAPI contract requirements and explicit business
rules into bounded, reproducible API verification evidence. It is intended for
local and test environments, not production.

## Current milestone

Only milestone 1, task M1-01 (Python repository and quality gates) is complete.
No domain model, state machine, database, HTTP executor, model integration, or web
interface has been implemented.

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

## Package layout

The project uses a `src/` layout. The runtime dependency set is intentionally
empty at this milestone; pytest, Ruff, and Pyright are development dependencies
managed by uv.
