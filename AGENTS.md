# ApiGuard Repository Instructions

## 1. Repository purpose

ApiGuard V0 is a bounded, requirement-driven API verification and defect-evidence tool for FastAPI/OpenAPI services.

It converts explicit OpenAPI requirements and confirmed business rules into a limited validation plan, executes real HTTP requests, performs deterministic evaluation, and produces reproducible evidence.

Do not describe the current repository as supporting capabilities that have not yet been implemented.

## 2. Sources of truth

Use project facts in this order:

1. Repository code, migrations, tests, and real command output.
2. Frozen baselines and task documents stored in the repository.
3. The current task prompt.
4. Prior agent completion reports.
5. Chat history.

Before changing code, read the documents relevant to the task. The primary frozen baselines are:

* `docs/baselines/00-v0-scope.md`
* `docs/baselines/01-v0-architecture.md`
* `docs/baselines/02-v0-technical-design-and-development.md`

Do not reinterpret or silently expand frozen V0 scope.

## 3. Working rules

Before implementation:

1. Confirm the current Git branch, HEAD, and worktree status.
2. Read the current task card and relevant baseline sections.
3. Inspect the existing implementation before proposing changes.
4. State the task scope and non-goals.
5. Run the existing quality gates to establish a clean baseline.

During implementation:

* Make the smallest change that satisfies the current task.
* Implement only one independently verifiable capability at a time.
* Do not implement later task cards opportunistically.
* Prefer deterministic Python code over model calls.
* Do not introduce abstractions without a current, concrete responsibility.
* Do not create empty future modules or generic utility layers.
* Do not overwrite or amend earlier accepted commits unless explicitly instructed.
* Preserve domain and persistence separation.
* Keep external SDKs and frameworks out of domain modules.
* Never persist runtime authentication secrets.

After implementation:

1. Run all task-specific tests.
2. Run all repository quality gates.
3. Inspect `git diff --check`.
4. Inspect `git status --short`.
5. Commit only the current task’s changes.
6. Leave the worktree clean unless the task explicitly says otherwise.

Do not claim completion without fresh command evidence.

## 4. Standard commands

Use the locked environment unless the task explicitly requires changing dependencies.

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
```

Also run every task-specific verification command defined by the current task card.

A third-party warning does not automatically justify changing dependencies. Record its complete type, message, file, and line before deciding whether action is necessary.

## 5. Frozen architecture boundaries

ApiGuard V0 uses:

* Python 3.12;
* a `src/` layout;
* a single-process modular monolith;
* FastAPI and Uvicorn;
* Jinja2 with minimal vanilla JavaScript;
* ordinary Python explicit state machines;
* synchronous SQLAlchemy 2.x;
* SQLite and Alembic;
* synchronous HTTPX;
* one official model-provider SDK behind a narrow adapter;
* Pydantic v2 at structured boundaries;
* pytest, Ruff, Pyright, and uv;
* Dockerfile and Docker Compose;
* one Uvicorn worker.

Do not introduce:

* LangGraph;
* LangChain;
* RAG;
* multiple agents;
* Celery or other workers;
* Redis or message queues;
* asynchronous SQLAlchemy;
* PostgreSQL;
* microservices;
* event sourcing;
* CQRS;
* React or Next.js;
* Kubernetes;
* autonomous runtime replanning.

A task prompt cannot casually reopen these frozen decisions. Report a conflict instead of silently changing the architecture.

## 6. Domain boundaries

Keep these ownership rules:

* `VerificationTask` owns preparation lifecycle state.
* `ValidationAttempt` owns execution lifecycle state.
* The authoritative four-state conclusion belongs only to a completed attempt and is produced through `EvaluationResult`.
* A task does not own an authoritative final conclusion.
* Reports are derived and are not part of the authoritative evidence chain.
* A rerun creates a new attempt; it does not overwrite a previous attempt.
* At most three actual target HTTP sends are allowed per attempt.
* Technical retries count toward the three-send limit.
* Target-service failures are evidence and are not automatically product API failures.

Do not bypass public domain behaviors by directly mutating lifecycle state in application code.

## 7. Dependency direction

* Web and API entry points call application use cases.
* Application code coordinates domain capabilities.
* Domain modules do not import FastAPI, SQLAlchemy, HTTPX, Jinja2, model SDKs, or infrastructure modules.
* Infrastructure implements narrow ports defined by the application or domain boundary.
* Deterministic comparison code must not query the database.
* Report generation must not mutate attempts, evaluation results, or evidence.

Do not introduce a global controller/service/repository layering scheme.

## 8. Transaction and external-call safety

When persistence and execution are implemented:

* Create and commit an attempt before the first real target request.
* Do not keep a database transaction open during network or model calls.
* Use short transactions around durable boundaries.
* Record send intent before an outbound request and finalize its result afterward.
* Never automatically resend a result-unknown side-effecting request during recovery.
* Final evaluation, sealed evidence, and attempt completion must preserve the frozen atomicity rules.
* Report generation occurs after authoritative completion and cannot change the conclusion.

## 9. Documentation and reporting

When completing a task, report:

* files created or modified;
* why each file changed;
* the implemented behavior;
* the tests added;
* every command actually run;
* real command results;
* `git diff --stat`;
* commit SHA;
* remaining work;
* known limitations;
* any conflict with a frozen baseline.

Do not report “done” without evidence.

When documentation and implementation disagree, do not guess. Identify the exact conflict and stop within the current task boundary.
