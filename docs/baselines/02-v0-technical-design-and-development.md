# ApiGuard V0 技术设计与开发拆分

> 文档状态：V0 技术设计最终基线  
> 上位基线：  
> 1. 《ApiGuard V0 立项与范围说明》  
> 2. 《ApiGuard V0 架构与系统边界基线》  
> 3. 前两轮已冻结的代码边界、领域契约、持久化原则、应用用例、事务边界与安全预算  
>
> 本文档冻结具体实现蓝图与开发顺序。本轮结束后不再继续宏观架构讨论；后续以仓库代码、迁移、测试输出和真实 HTTP 证据作为事实来源。

> **实现层术语统一：** 架构基线中使用的 `EvidencePackage` 和 `HumanReadableReport`，在实现层正式统一命名为 `EvidenceBundle` 和 `DerivedReport`，其业务含义和权威性边界不变。此后代码、数据库、测试和文档中统一使用新名称，不再混用旧名称。

---

## 0. 最终实现约束

ApiGuard V0 保持以下边界不变：

- 单进程、单 Uvicorn Worker 的模块化单体；
- FastAPI + Jinja2 + 少量原生 JavaScript；
- 普通 Python 显式状态机；
- 同步 SQLAlchemy 2.x + SQLite + Alembic；
- HTTPX 同步客户端；
- 单一模型供应商官方 SDK，通过供应商无关端口进入；
- Pydantic v2 用于结构化边界和不可变快照；
- pytest、Ruff、Pyright、uv；
- Dockerfile + Docker Compose；
- 不使用 LangGraph、LangChain、RAG、Worker、消息队列、React、微服务或 PostgreSQL。

本轮新增冻结常量：

| 常量 | 值 |
|---|---:|
| `OPENAPI_FETCH_TIMEOUT_SECONDS` | 10 |
| `MAX_OPENAPI_FETCH_ATTEMPTS` | 2（首次 + 最多一次临时网络重试） |
| `LLM_CALL_TIMEOUT_SECONDS` | 45 |
| `MAX_LLM_CALLS_PER_PREPARATION` | 3 |
| `MAX_LLM_TRANSIENT_RETRIES` | 1 |
| `MAX_LLM_FORMAT_REPAIRS` | 1 |
| `MAX_PLAN_STEPS` | 3 |
| `MAX_HTTP_SENDS_PER_ATTEMPT` | 3 |
| `TARGET_HTTP_REQUEST_TIMEOUT_SECONDS` | 20 |
| `VALIDATION_ATTEMPT_BUDGET_SECONDS` | 90 |
| `MAX_OPENAPI_DOCUMENT_BYTES` | 2 MiB |
| `MAX_JSON_REQUEST_BODY_BYTES` | 256 KiB |
| `MAX_SAVED_RESPONSE_BODY_BYTES` | 1 MiB |
| `MAX_INLINE_REPORT_BODY_BYTES` | 64 KiB |
| `MAX_MODEL_OUTPUT_BYTES` | 128 KiB |

模型调用顺序固定为：

1. 首次生成调用；
2. 如果首次或后续调用发生可重试的超时、限流或临时服务错误，整个准备过程最多进行一次临时重试；
3. 如果获得了模型输出但本地 Pydantic 结构校验失败，最多进行一次格式修复；
4. 实际模型调用总数不得超过三次；
5. 格式修复调用之后不再继续调用模型；
6. 不允许因计划校验失败反复调用模型。

实际发送计数达到三次后，执行器必须停止；即使计划中还有未执行逻辑步骤，也只能标记为未执行并进入确定性评估。

---

# 1. 推荐仓库结构

## 1.1 最终目录

```text
apiguard/
├── pyproject.toml
├── uv.lock
├── README.md
├── .gitignore
├── .env.example
├── alembic.ini
├── Dockerfile
├── compose.yaml
│
├── src/
│   └── apiguard/
│       ├── __init__.py
│       ├── main.py
│       ├── bootstrap.py
│       ├── config.py
│       ├── logging_config.py
│       │
│       ├── shared/
│       │   ├── enums.py
│       │   ├── ids.py
│       │   └── errors.py
│       │
│       ├── application/
│       │   ├── dto.py
│       │   ├── ports.py
│       │   ├── task_commands.py
│       │   ├── attempt_commands.py
│       │   ├── queries.py
│       │   ├── report_commands.py
│       │   └── startup.py
│       │
│       ├── tasking/
│       │   ├── models.py
│       │   ├── state_machine.py
│       │   └── policies.py
│       │
│       ├── openapi_context/
│       │   ├── models.py
│       │   ├── parser.py
│       │   └── context_builder.py
│       │
│       ├── planning/
│       │   ├── models.py
│       │   ├── generation.py
│       │   └── model_audit.py
│       │
│       ├── plan_validation/
│       │   └── validator.py
│       │
│       ├── execution/
│       │   ├── models.py
│       │   ├── request_builder.py
│       │   ├── variable_extraction.py
│       │   └── executor.py
│       │
│       ├── evaluation/
│       │   ├── models.py
│       │   ├── comparators.py
│       │   └── evaluator.py
│       │
│       ├── evidence/
│       │   ├── models.py
│       │   ├── redaction.py
│       │   ├── bundle_builder.py
│       │   └── report_view.py
│       │
│       ├── infrastructure/
│       │   ├── persistence/
│       │   │   ├── database.py
│       │   │   ├── orm.py
│       │   │   ├── mappers.py
│       │   │   ├── repositories.py
│       │   │   └── unit_of_work.py
│       │   ├── llm/
│       │   │   └── official_sdk_gateway.py
│       │   ├── http/
│       │   │   ├── openapi_source.py
│       │   │   └── target_client.py
│       │   └── reporting/
│       │       └── jinja_renderer.py
│       │
│       └── web/
│           ├── api_schemas.py
│           ├── task_routes.py
│           ├── attempt_routes.py
│           ├── report_routes.py
│           ├── page_routes.py
│           ├── templates/
│           │   ├── base.html
│           │   ├── tasks/
│           │   │   ├── create.html
│           │   │   └── detail.html
│           │   ├── plans/
│           │   │   └── review.html
│           │   ├── attempts/
│           │   │   └── detail.html
│           │   └── reports/
│           │       └── detail.html
│           └── static/
│               ├── app.js
│               └── styles.css
│
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── tests/
│   ├── unit/
│   │   ├── tasking/
│   │   ├── openapi_context/
│   │   ├── plan_validation/
│   │   ├── evaluation/
│   │   ├── execution/
│   │   └── evidence/
│   ├── integration/
│   │   ├── persistence/
│   │   ├── http/
│   │   ├── llm/
│   │   ├── api/
│   │   └── startup/
│   ├── e2e/
│   │   ├── conftest.py
│   │   ├── scenario_data.py
│   │   └── test_acceptance_scenarios.py
│   └── fixtures/
│       ├── openapi/
│       ├── plans/
│       ├── responses/
│       └── evidence/
│
├── evals/
│   └── model/
│       ├── cases.jsonl
│       ├── expected_results.json
│       └── run_eval.py
│
├── reference_service/
│   ├── Dockerfile
│   ├── README.md
│   ├── app/
│   │   ├── main.py
│   │   ├── state.py
│   │   ├── schemas.py
│   │   └── routes.py
│   └── tests/
│       └── test_reference_behaviors.py
│
└── docs/
    ├── baselines/
    │   ├── 00-v0-scope.md
    │   ├── 01-v0-architecture.md
    │   └── 02-v0-technical-design-and-development.md
    ├── codex/
    │   └── milestone-01-task-cards.md
    └── acceptance/
        └── e2e-scenarios.md
```

所有 Python 包都需要最小 `__init__.py`，但不为尚未实现的能力提前创建大量空模块。建仓首个里程碑只创建当期实际使用的模块，其余目录在对应里程碑开始时建立；上面的目录树是 V0 完成时的目标结构。

## 1.2 关键文件职责

### 应用入口与装配

| 文件 | 职责 |
|---|---|
| `main.py` | 创建 FastAPI 应用、注册生命周期和路由；不包含业务逻辑 |
| `bootstrap.py` | 读取配置并组装 Unit of Work、外部适配器和应用用例 |
| `config.py` | `pydantic-settings` 配置；包含冻结的时间、大小和次数上限 |
| `logging_config.py` | 标准 logging 初始化和任务/尝试关联字段；不得记录秘密 |

### `shared`

`shared` 只保存真正跨模块稳定的内容：

- 状态、结论、HTTP 方法等枚举；
- 业务标识类型；
- 极少量所有模块都需要的基础异常。

禁止放入：

- 通用 `utils.py`；
- SQLAlchemy 基类；
- HTTP 或模型 SDK；
- 业务编排；
- JSON 路径解析器；
- 各模块无法归类的杂项。

### `application`

| 文件 | 职责 |
|---|---|
| `dto.py` | 应用命令、查询和用例输出 DTO；不包含 FastAPI 类型 |
| `ports.py` | 少量真正外部端口 Protocol |
| `task_commands.py` | 创建、准备、确认和取消任务 |
| `attempt_commands.py` | 首次执行和重复运行；共享私有执行流程 |
| `queries.py` | 任务、尝试和证据只读查询 |
| `report_commands.py` | 派生报告重新生成 |
| `startup.py` | 启动时确定性收尾未完成尝试 |

应用层只协调状态、事务和模块调用，不理解业务自由文本、不实现比较器、不操作 SQLAlchemy Session。

### 七个业务能力包

| 包 | 关键职责 |
|---|---|
| `tasking` | 任务与尝试状态机、范围门禁、确认和执行意图规则 |
| `openapi_context` | OpenAPI 读取结果解析、操作提取和不可变快照 |
| `planning` | 规范化规则、候选计划和模型调用审计的供应商无关结构 |
| `plan_validation` | 单目标、三步、数据来源、比较能力和副作用的确定性校验 |
| `execution` | 从确认计划构造请求、顺序发送、变量提取和停止条件 |
| `evaluation` | 纯确定性比较和四态决策 |
| `evidence` | 脱敏、证据清单、封存和报告只读视图 |

### `infrastructure`

| 子包 | 职责 |
|---|---|
| `persistence` | SQLite/SQLAlchemy、ORM、映射、业务持久化端口和 Unit of Work |
| `llm` | 单一供应商官方 SDK 适配；供应商类型不得向外传播 |
| `http` | OpenAPI 来源获取和待测 HTTP 传输；HTTPX 类型不得向领域传播 |
| `reporting` | Jinja2 报告渲染 |

`infrastructure` 不允许成为通用杂物目录。

### Web

Web 路由只完成：

1. 解析 API 或表单输入；
2. 构造应用命令；
3. 调用一个应用用例；
4. 把应用输出转换为 HTTP 响应或模板上下文。

Web 不直接：

- 打开 Session；
- 调用模型 SDK；
- 调用 HTTPX；
- 修改 ORM 对象；
- 决定四态结论。

---

# 2. 核心类型与命名冻结

## 2.1 枚举

### 业务状态和类型

```text
VerificationTaskType
- OPENAPI_CONTRACT
- BUSINESS_RULE
- STATE_FLOW

VerificationTaskStatus
- DRAFT
- PREPARING
- AWAITING_CONFIRMATION
- READY
- CANCELLED

ValidationAttemptStatus
- EXECUTING
- COMPLETED

ValidationConclusion
- PASSED
- SUSPECTED_DEFECT
- INCONCLUSIVE
- EXECUTION_FAILED

ValidationPlanStage
- CANDIDATE
- VALIDATED
- CONFIRMED
```

### 执行枚举

```text
HttpMethod
- GET
- HEAD
- POST
- PUT
- PATCH
- DELETE

StepExecutionStatus
- PENDING
- RUNNING
- COMPLETED
- FAILED
- SKIPPED

HttpSendStatus
- DISPATCHED
- RESPONDED
- FAILED
- UNKNOWN_AFTER_INTERRUPT
```

`COMPLETED` 步骤表示已取得终止执行事实，不表示比较通过。

### 计划与比较枚举

```text
ValueSourceKind
- LITERAL
- TASK_INPUT
- PRIOR_STEP_VARIABLE

VariableExtractionSource
- STATUS_CODE
- RESPONSE_HEADER
- JSON_POINTER

ComparisonKind
- STATUS_CODE_EQUALS
- STATUS_CODE_IN
- JSON_PATH_EXISTS
- JSON_PATH_NOT_EXISTS
- JSON_VALUE_EQUALS
- JSON_VALUE_NOT_EQUALS
- JSON_VALUE_TYPE
- OPENAPI_SCHEMA_VALID
- RESPONSE_HEADER_EXISTS
- RESPONSE_HEADER_EQUALS
- NUMBER_COMPARE

NumericOperator
- GREATER_THAN
- GREATER_THAN_OR_EQUAL
- LESS_THAN
- LESS_THAN_OR_EQUAL
```

V0 不支持正则、任意表达式、脚本、数组过滤、模糊相似度或通用字符串表达式语言。

## 2.2 稳定领域对象

| 名称 | 领域分类 | 推荐表示 |
|---|---|---|
| `VerificationTask` | 生命周期实体、任务聚合根 | 普通 dataclass |
| `OpenAPIContextSnapshot` | 不可变快照 | frozen Pydantic model |
| `NormalizedRule` | 不可变候选语义快照 | frozen Pydantic model |
| `ValidationPlanSnapshot` | 不可变内容 + 单向阶段控制 | frozen Pydantic 内容模型，阶段由实体包装或受限持久化更新 |
| `ValidationAttempt` | 生命周期实体、执行聚合根 | 普通 dataclass |
| `StepExecutionRecord` | 尝试子实体 | 普通 dataclass |
| `HttpSendRecord` | 追加式实际发送子实体 | 普通 dataclass |
| `EvaluationResult` | 不可变确定性计算结果 | frozen Pydantic model |
| `EvidenceBundle` | 不可变封存实体 | frozen Pydantic model |
| `ModelCallRecord` | 规划审计记录 | frozen dataclass |
| `DerivedReport` | 派生、版本化实体 | frozen dataclass |

使用普通 dataclass 的原因是这些实体需要明确身份和受控状态转换；使用 frozen Pydantic 的对象需要跨模型、API、JSON 和持久化边界进行严格结构校验。

## 2.3 计划内部结构

### `VerificationObjective`

不可变值对象，包含：

- `task_type`；
- 唯一目标陈述；
- 目标操作范围；
- 明确的成功证明边界。

### `OperationReference`

不可变值对象，包含：

- OpenAPI 路径；
- `HttpMethod`；
- 可选 `operation_id`；
- 对应 OpenAPI 快照 ID。

### `RequestStep`

不可变值对象，包含：

- 稳定 `step_id`；
- 从 1 开始的 `step_index`；
- `OperationReference`；
- `RequestTemplate`；
- 变量提取列表；
- 预期条件列表；
- 是否允许有限技术重试。

### `RequestTemplate`

表示尚未注入运行时凭据的请求构造：

- 路径参数；
- 查询参数；
-普通请求头；
- JSON 请求体；
- 每个值的 `ValueSource`。

禁止保存运行时 Token、Cookie 或 API Key。

### `ValueSource`

表示请求值来自：

- 固定字面量；
- 用户任务输入；
- 先前步骤的已声明变量。

不得引用未来步骤或动态脚本。

### `VariableExtraction`

包含：

- 变量名；
- 来源类型；
- 来源步骤；
- Header 名称或 JSON Pointer；
- 允许的简单标量类型；
- 是否允许 `null`。

### `ExpectedCondition`

是用户确认的可观察预期，包含：

- 稳定条件 ID；
- 人类可读说明；
- 来源规则引用；
- 一个机器可执行 `ComparisonCondition`；
- 该条件是否为最终结论所必需。

### `ComparisonCondition`

只表达确定性比较：

- `ComparisonKind`；
- 实际值目标；
- 预期字面量、集合、OpenAPI Schema 引用或先前提取变量；
- 可选 `NumericOperator`。

### `ComparisonTarget`

包含：

- 对应逻辑步骤；
- 状态码、响应 Header、JSON Pointer 或 OpenAPI 响应 Schema；
- Header 名称或 JSON Pointer。

### `JsonPointer`

统一采用 RFC 6901 JSON Pointer：

- 根节点使用空字符串；
- `/data/id` 表示对象字段；
- `/items/0/name` 表示数组索引；
- `~0` 和 `~1` 分别转义 `~` 和 `/`。

不实现 JSONPath、过滤器或脚本表达式。

## 2.4 API Schema、领域对象与 ORM

### API Schema

只属于 Web 的模型包括：

- 创建任务请求；
- 准备/修订请求；
- 确认请求；
- 执行和重复运行请求；
- 查询响应包装；
- 错误响应；
- 同步执行响应；
- 报告状态响应。

API Schema 不承载领域行为。

### ORM

ORM 类型只存在于：

```text
src/apiguard/infrastructure/persistence/orm.py
```

命名使用：

- `VerificationTaskRow`
- `OpenAPISnapshotRow`
- `NormalizedRuleRow`
- `ValidationPlanSnapshotRow`
- `ValidationAttemptRow`
- `StepExecutionRecordRow`
- `HttpSendRecordRow`
- `EvaluationResultRow`
- `EvidenceBundleRow`
- `ModelCallRecordRow`
- `DerivedReportRow`

ORM 类型不得进入应用层、领域层、比较器或 Web 响应。

### 转换规则

```text
FastAPI 请求 Schema
→ application Command DTO
→ 领域构造器/用例
→ domain object
→ persistence mapper
→ ORM Row
```

查询方向：

```text
ORM Row
→ persistence mapper
→ domain object 或 application read model
→ FastAPI Response Schema / Jinja2 view model
```

禁止：

- 路由直接 `model_validate(orm_row)`；
- 把 ORM Row 当作领域实体；
- 为计划内容在 Web、领域和 ORM 中各复制一套不同结构。

复杂计划、评估和 Evidence 内容只有一套领域 Pydantic 模型；API 只进行只读包装，ORM 只保存其稳定 JSON 序列化结果。

---

# 3. 数据库表与约束冻结

SQLite 使用文本 UUID 主键、UTC 时间字符串或 SQLAlchemy 标准 UTC DateTime；具体存储格式由第一张迁移统一，不允许不同表混用。

## 3.1 `verification_tasks`

主要字段：

- `task_id` PK；
- `task_type`；
- `verification_objective`；
- `original_rule_text`；
- `openapi_source_kind`；
- `openapi_source_value`；
- `target_base_url`；
- `non_production_confirmed`；
- `test_data_json`；
- `allowed_operation_scope_json`；
- `status`；
- `current_confirmed_plan_id` nullable；
- `last_preparation_error_json` nullable；
- `created_at`；
- `updated_at`；
- `cancelled_at` nullable；
- `cancellation_reason` nullable。

允许业务更新：

- 草稿输入；
- `status`；
- 当前确认计划引用；
- 准备错误；
- 时间和取消信息。

数据库约束：

- PK `task_id`；
- 状态 CHECK；
- `READY` 与当前计划引用的一致性主要由应用层保证；
- 通过组合外键保证当前计划属于同一任务：
  `FOREIGN KEY(task_id, current_confirmed_plan_id)` 指向计划表的唯一组合。

## 3.2 `openapi_snapshots`

主要字段：

- `openapi_snapshot_id` PK；
- `task_id` FK；
- `version_no`；
- `source_kind`；
- `source_display_value`；
- `openapi_version`；
- `raw_document`；
- `raw_size_bytes`；
- `content_sha256`；
- `normalized_context_json`；
- `diagnostics_json`；
- `created_at`。

约束：

- `UNIQUE(task_id, version_no)`；
- `UNIQUE(task_id, openapi_snapshot_id)` 用于组合外键；
- 索引：`task_id`、`content_sha256`。

记录插入后禁止业务更新。

## 3.3 `model_call_records`

主要字段：

- `model_call_id` PK；
- `task_id` FK；
- `openapi_snapshot_id` FK；
- `preparation_run_id`；
- `call_sequence`；
- `call_kind`：PRIMARY、TRANSIENT_RETRY、FORMAT_REPAIR；
- `provider_name`；
- `model_name`；
- `prompt_version`；
- `status`；
- `started_at`；
- `completed_at`；
- `raw_output_text` nullable；
- `structured_output_json` nullable；
- `validation_errors_json` nullable；
- `provider_request_id` nullable；
- `token_usage_json` nullable；
- `error_json` nullable。

约束：

- `UNIQUE(preparation_run_id, call_sequence)`；
- 调用序号最多三次由应用层保证；
- 索引：`task_id`、`preparation_run_id`、`openapi_snapshot_id`。

建议适配器完成一次调用后插入终止记录；插入后禁止业务更新。

## 3.4 `normalized_rules`

主要字段：

- `normalized_rule_id` PK；
- `task_id` FK；
- `openapi_snapshot_id` FK；
- `model_call_id` FK；
- `version_no`；
- `original_rule_text`；
- `normalized_rule_json`；
- `content_sha256`；
- `created_at`。

约束：

- `UNIQUE(task_id, version_no)`；
- 索引：`task_id`、`openapi_snapshot_id`、`model_call_id`。

插入后禁止业务更新。

## 3.5 `validation_plan_snapshots`

主要字段：

- `plan_id` PK；
- `task_id` FK；
- `normalized_rule_id` FK；
- `openapi_snapshot_id` FK；
- `version_no`；
- `stage`；
- `plan_json`；
- `content_sha256`；
- `validation_issues_json` nullable；
- `validated_at` nullable；
- `confirmation_json` nullable；
- `confirmed_at` nullable；
- `created_at`。

约束：

- `UNIQUE(task_id, version_no)`；
- `UNIQUE(task_id, plan_id, openapi_snapshot_id)`；
- 阶段 CHECK；
- `CONFIRMED` 时确认信息非空的规则由应用层和测试保证；
- 索引：`task_id`、`stage`、`normalized_rule_id`、`openapi_snapshot_id`。

允许业务更新仅限：

- `CANDIDATE → VALIDATED → CONFIRMED`；
- 一次性写入校验结果和确认记录。

`plan_json` 和 `content_sha256` 插入后绝不更新。

## 3.6 `validation_attempts`

主要字段：

- `attempt_id` PK；
- `task_id` FK；
- `attempt_no`；
- `plan_id`；
- `openapi_snapshot_id`；
- `status`；
- `execution_intent_id`；
- `is_rerun`；
- `previous_attempt_id` nullable；
- `created_at`；
- `started_at`；
- `completed_at` nullable；
- `actual_send_count`；
- `evaluation_result_id` nullable；
- `evidence_bundle_id` nullable；
- `conclusion` nullable。

关系保证：

- 组合外键  
  `(task_id, plan_id, openapi_snapshot_id)`  
  指向  
  `validation_plan_snapshots(task_id, plan_id, openapi_snapshot_id)`；
- `previous_attempt_id` 指向历史尝试；
- 一对多逻辑步骤；
- 一对一评估和 EvidenceBundle。

唯一约束：

- `UNIQUE(task_id, attempt_no)`；
- `UNIQUE(task_id, execution_intent_id)`；
- SQLite 部分唯一索引：

```sql
CREATE UNIQUE INDEX uq_validation_attempt_one_executing_per_task
ON validation_attempts(task_id)
WHERE status = 'EXECUTING';
```

这条索引是单活动尝试的数据库最终防线。应用层仍必须在同一事务中检查并创建尝试，以返回清晰的业务冲突。

允许业务更新：

- `actual_send_count` 单向增加；
- 最终一次性绑定评估、Bundle、结论和完成时间；
- `EXECUTING → COMPLETED`。

禁止更新：

- 任务、计划和快照绑定；
- 执行意图；
- 尝试编号；
- 重复运行关系；
- `COMPLETED → EXECUTING`。

## 3.7 `step_execution_records`

主要字段：

- `step_record_id` PK；
- `attempt_id` FK；
- `plan_step_id`；
- `step_index`；
- `status`；
- `resolved_input_json` nullable；
- `send_count`；
- `extracted_variables_json` nullable；
- `started_at` nullable；
- `completed_at` nullable；
- `failure_reason_json` nullable；
- `skip_reason_json` nullable。

约束：

- `UNIQUE(attempt_id, step_index)`；
- `UNIQUE(attempt_id, plan_step_id)`；
- 步骤状态 CHECK；
- 索引：`attempt_id`、`status`。

允许更新仅限单向步骤状态和终止事实；终止后禁止业务更新。

## 3.8 `http_send_records`

主要字段：

- `send_record_id` PK；
- `attempt_id` FK；
- `step_record_id` FK；
- `global_send_no`；
- `send_no_in_step`；
- `is_retry`；
- `retry_reason` nullable；
- `status`；
- `method`；
- `sanitized_url`；
- `query_params_json`；
- `request_headers_json`；
- `request_body` nullable；
- `request_body_size_bytes`；
- `dispatched_at`；
- `completed_at` nullable；
- `reached_service` nullable；
- `response_status_code` nullable；
- `response_headers_json` nullable；
- `response_body` nullable；
- `response_declared_size_bytes` nullable；
- `response_captured_size_bytes` nullable；
- `response_body_sha256` nullable；
- `response_truncated`；
- `error_json` nullable。

唯一约束：

- `UNIQUE(step_record_id, send_no_in_step)`；
- `UNIQUE(attempt_id, global_send_no)`。

允许业务更新：

1. 插入 `DISPATCHED` 请求事实；
2. 一次性补充响应、错误或 `UNKNOWN_AFTER_INTERRUPT`。

终止后禁止业务更新。

应用层保证：

- `global_send_no` 从 1 连续递增；
- 总记录数不超过三；
- 技术重试属于同一步骤；
- 有副作用请求不自动重试。

## 3.9 `evaluation_results`

主要字段：

- `evaluation_result_id` PK；
- `attempt_id` FK UNIQUE；
- `plan_id` FK；
- `openapi_snapshot_id` FK；
- `evaluation_input_sha256`；
- `assertions_json`；
- `required_steps_complete`；
- `preconditions_proven`；
- `critical_evidence_missing`；
- `attribution_ambiguous`；
- `conclusion`；
- `decision_code`；
- `decision_detail_json`；
- `created_at`。

插入后禁止业务更新。

索引：

- `conclusion`；
- `plan_id`；
- `created_at`。

## 3.10 `evidence_bundles`

主要字段：

- `evidence_bundle_id` PK；
- `attempt_id` FK UNIQUE；
- `task_id` FK；
- `plan_id` FK；
- `openapi_snapshot_id` FK；
- `evaluation_result_id` FK UNIQUE；
- `bundle_format_version`；
- `manifest_json`；
- `manifest_sha256`；
- `sealed_at`。

存在即代表已封存，不增加可变 `sealed` 布尔字段。

插入后禁止业务更新。

索引：

- `task_id`；
- `plan_id`；
- `sealed_at`；
- `manifest_sha256`。

## 3.11 `derived_reports`

主要字段：

- `report_id` PK；
- `evidence_bundle_id` FK；
- `report_version`；
- `format`；
- `renderer_version`；
- `content_text`；
- `content_sha256`；
- `created_at`。

约束：

- `UNIQUE(evidence_bundle_id, report_version)`；
- 索引：`evidence_bundle_id`、`created_at`。

重新生成时插入新版本，不覆盖旧报告。失败渲染不插入报告记录。

## 3.12 不变量分工

### 数据库直接保证

- 主外键完整性；
- 任务内版本号唯一；
- 当前计划基本归属；
- 尝试精确绑定任务、计划和 OpenAPI 快照；
- 执行意图幂等；
- 单任务单 `EXECUTING` 尝试；
- 一次尝试只有一个最终评估和 Bundle；
- 步骤与发送顺序唯一；
- 状态和结论枚举取值。

### 应用层保证

- 当前计划必须处于 `CONFIRMED`；
- 计划最多三步、无分支和循环；
- 数据来源只来自用户输入或前序变量；
- 实际发送总数不超过三；
- 发送达到三次后停止；
- 有副作用请求不自动重试；
- EvidenceBundle 引用完整且哈希正确；
- `COMPLETED` 时评估、Bundle 和结论同时存在；
- 不可变记录不经过业务更新接口修改。

V0 不通过复杂触发器实现跨表和 JSON 语义。

## 3.13 SQLite 初始化

数据库连接初始化冻结为：

- 每个连接执行 `PRAGMA foreign_keys = ON`；
- 应用启动时执行 `PRAGMA journal_mode = WAL`；
- 使用 `PRAGMA synchronous = NORMAL`；
- 使用 `PRAGMA busy_timeout = 5000`；
- 单 Uvicorn Worker；
- 所有写操作使用短事务。

Alembic 迁移必须创建部分唯一索引并在集成测试中实际验证。

---

# 4. 端口与适配器契约

## 4.1 `UnitOfWork`

由应用用例调用。

暴露：

- `tasks: TaskRepository`
- `attempts: AttemptRepository`
- `evidence: EvidenceRepository`
- `commit()`
- `rollback()`

它封装事务和仓储，不暴露 SQLAlchemy Session。

测试中使用内存 Fake Unit of Work。

## 4.2 `TaskRepository`

负责任务准备聚合的持久化。

接收/返回：

- `VerificationTask`；
- OpenAPI 快照；
- `NormalizedRule`；
- 计划快照；
- 模型调用记录；
- 任务详情只读模型。

需要的业务方法概念上包括：

- 新增和读取任务；
- 保存受限任务状态变化；
- 追加 OpenAPI 快照、模型调用、规则和计划；
- 设置当前确认计划；
- 获取最新版本号和当前可确认计划。

领域可识别错误：

- `VerificationTaskNotFound`
- `TaskStateConflict`
- `PlanVersionConflict`
- `PersistenceConflict`
- `PersistenceUnavailable`

允许产生数据库副作用。

测试中使用内存字典和追加列表 Fake。

## 4.3 `AttemptRepository`

负责执行聚合。

接收/返回：

- `ValidationAttempt`；
- `StepExecutionRecord`；
- `HttpSendRecord`；
- `EvaluationResult`。

需要的方法：

- 按执行意图查找已有尝试；
- 检查和创建活动尝试；
- 追加发送边界；
- 终止发送记录；
- 更新逻辑步骤；
- 读取尝试全部执行事实；
- 完成尝试。

领域可识别错误：

- `ValidationAttemptNotFound`
- `ActiveAttemptExists`
- `DuplicateExecutionIntent`
- `AttemptStateConflict`
- `SendLimitExceeded`
- `PersistenceConflict`

允许数据库副作用。

测试中使用支持唯一性检查的内存 Fake，SQLite 约束由集成测试另行证明。

## 4.4 `EvidenceRepository`

负责：

- 插入 `EvidenceBundle`；
- 插入和读取 `DerivedReport`；
- 读取机器可读证据视图；
- 获取最新报告版本。

错误：

- `EvidenceBundleNotFound`
- `EvidenceAlreadySealed`
- `EvidenceReferenceIncomplete`
- `ReportVersionConflict`
- `PersistenceUnavailable`

Bundle 和报告只允许追加。

## 4.5 `OpenAPISource`

调用者：`PrepareVerificationTask` 经 OpenAPI 上下文模块。

输入：

- 来源类型；
- 文件路径或 URL；
- 10 秒单次超时；
- 2 MiB 上限。

返回：

- 原始字节；
- 可展示来源；
- Content-Type；
- 实际大小；
- 获取诊断。

错误：

- `OpenAPISourceUnavailable`
- `OpenAPIFetchTimeout`
- `OpenAPIDocumentTooLarge`
- `OpenAPISourceUnauthorized`
- `UnsupportedOpenAPISource`

允许文件或网络读取副作用，不修改业务状态。

测试中使用内存固定文档 Source。

解析 OpenAPI 是内部确定性函数，不另建端口。

## 4.6 `PlanGenerator`

调用者：`PrepareVerificationTask` 经 planning 模块。

输入：

- 验证目标；
- 原始规则；
- 任务类型；
- 过滤后的 OpenAPI 上下文；
- 非敏感测试数据说明；
- V0 固定限制；
- 输出 Schema；
- 格式修复时的本地校验错误。

返回：

- 供应商无关的规范化规则候选；
- 候选计划；
- 对应 `ModelCallRecord`；
- 缺失信息和歧义。

错误：

- `PlanGenerationTimeout`
- `PlanGenerationRateLimited`
- `PlanGenerationUnavailable`
- `PlanOutputTooLarge`
- `PlanOutputInvalid`

允许调用外部模型服务，但不得获得待测 API、数据库或运行时凭据。

测试中使用固定输出 Fake；模型评测使用真实适配器。

## 4.7 `TargetHttpClient`

调用者：execution 模块。

输入：

- 已完全构造的运行时请求；
- 单次 20 秒预算；
- 是否跟随重定向等冻结配置；
- 响应保存上限。

返回自定义 `TargetHttpResult`：

- `TargetHttpResponse`，或
- `TargetTransportFailure`。

不得返回 `httpx.Response`。

连接、DNS、TLS、超时等预期传输失败作为返回数据，便于形成证据；仅请求无法由适配器正确发出时抛出：

- `TargetClientConfigurationError`
- `TargetRequestConstructionError`

允许真实外部 HTTP 副作用。

测试中使用 Fake 或 HTTPX MockTransport 实现。

## 4.8 `Clock`

调用者：状态机、应用用例、执行和证据构建。

接口仅需要：

- `now_utc()`

无副作用。

测试中使用固定或可推进时间的 FakeClock。

## 4.9 `IdGenerator`

调用者：应用用例。

生成：

- task ID；
- snapshot ID；
- plan ID；
- attempt ID；
- step/send/evaluation/bundle/report ID；
- preparation run ID。

无外部副作用。

测试中使用可预测序列 FakeIdGenerator。

## 4.10 `ReportRenderer`

调用者：报告用例和首次执行后的派生报告阶段。

输入：

- 只读 Evidence 报告视图；
- 报告格式；
- 渲染器版本。

返回：

- 渲染文本；
- 格式；
- 内容摘要。

错误：

- `ReportRenderingFailed`
- `UnsupportedReportFormat`

不修改 Evidence 或尝试。

测试中使用固定文本 Fake。

## 4.11 不建立端口的确定性能力

以下保持普通函数或领域服务：

- 状态机；
- 范围检查；
- OpenAPI 解析；
- 计划校验；
- JSON Pointer 解析；
- 请求模板求值；
- 变量提取；
- 比较器；
- 四态决策表；
- 脱敏；
- Bundle 清单和哈希。

---

# 5. 应用用例冻结

## 5.1 最终用例集合

最终保留：

1. `CreateVerificationTask`
2. `PrepareVerificationTask`
3. `ConfirmValidationPlan`
4. `CancelVerificationTask`
5. `ExecuteValidationTask`
6. `RerunValidationTask`
7. `GetVerificationTask`
8. `GetValidationAttempt`
9. `GetEvidenceBundle`
10. `RegenerateDerivedReport`
11. `FinalizeInterruptedAttempts`

不单独保留 `ReviseValidationTask`。

理由：

- 修改规则、来源、测试数据或计划后必须立即产生新准备版本；
- 单独“修改但不准备”会增加一个无独立业务价值的中间状态；
- `PrepareVerificationTask` 接收可选 revision，统一处理首次准备、校验失败后的修订和已确认计划的重新准备；
- 旧计划保留，新计划重新生成、校验和确认。

`ExecuteValidationTask` 和 `RerunValidationTask` 对外分开，因为用户意图和前置条件不同；内部共享私有执行流程。

## 5.2 `CreateVerificationTask`

- 输入：任务类型、目标、规则、OpenAPI 来源、环境、非生产确认、非敏感测试数据和允许操作范围；
- 前置：无；
- 协调：tasking；
- 输出：`DRAFT` 任务；
- 事务：单个创建事务；
- 幂等：不强制；客户端重复创建是两个任务；
- 失败：输入不足以形成草稿、数据库失败。

## 5.3 `PrepareVerificationTask`

- 输入：task ID、可选修订字段、preparation request ID；
- 前置：`DRAFT`、`AWAITING_CONFIRMATION` 或无活动尝试的 `READY`；
- 协调：tasking、OpenAPI context、planning、plan validation、OpenAPISource、PlanGenerator；
- 输出：
  - 成功：任务 `AWAITING_CONFIRMATION`、OpenAPI 快照、规范化规则和 `VALIDATED` 计划；
  - 失败：任务回到 `DRAFT` 并保存明确准备错误；
- 事务：
  1. 进入 `PREPARING` 并失效当前可执行计划引用；
  2. 事务外获取 OpenAPI；
  3. 短事务追加快照；
  4. 事务外调用模型，实际每次调用结束后追加 ModelCallRecord；
  5. 短事务追加规则和候选计划；
  6. 事务外确定性校验；
  7. 短事务保存校验结果并进入 `AWAITING_CONFIRMATION` 或 `DRAFT`；
- 幂等：不使用执行级幂等；每次明确准备可以产生新版本；
- 失败：输入/范围、OpenAPI、模型、结构校验、计划校验和状态冲突。

## 5.4 `ConfirmValidationPlan`

- 输入：task ID、plan ID、plan content hash、环境和副作用确认；
- 前置：任务 `AWAITING_CONFIRMATION`、计划 `VALIDATED`；
- 协调：tasking、持久化；
- 输出：任务 `READY`、计划 `CONFIRMED`；
- 事务：计划确认和任务当前计划引用同一短事务；
- 幂等：确认同一计划和同一哈希重复提交返回现有成功结果；
- 失败：计划过期、哈希不一致、状态冲突、计划未校验。

## 5.5 `CancelVerificationTask`

- 输入：task ID、取消原因；
- 前置：任务非 `CANCELLED`，且没有 `EXECUTING` 尝试；
- 协调：tasking；
- 输出：`CANCELLED` 任务；
- 事务：单一短事务；
- 幂等：重复取消返回现有取消结果；
- 失败：活动尝试存在、非法状态。

## 5.6 `ExecuteValidationTask`

- 输入：task ID、`execution_intent_id`、运行时认证信息；
- 前置：任务 `READY`、当前确认计划有效、无活动尝试；
- 协调：tasking、execution、evaluation、evidence、TargetHttpClient；
- 输出：
  - `ValidationAttempt`；
  - `ValidationConclusion`；
  - `EvidenceBundle` 引用；
  - 派生报告状态；
- 事务：采用第 8 节的多个短事务；
- 幂等：强制；相同任务和执行意图只创建一个尝试；
- 失败：
  - 创建前：409/422，不创建尝试；
  - 创建后技术或环境失败：正常完成 `COMPLETED + EXECUTION_FAILED`；
  - Bundle 封存失败：尝试保留 `EXECUTING`，由启动收尾。

## 5.7 `RerunValidationTask`

- 输入：历史 attempt ID、新执行意图、运行时认证信息、环境状态已恢复确认；
- 前置：
  - 历史尝试存在；
  - 所属任务仍 `READY`；
  - 当前确认计划与历史尝试计划相同；
  - 无活动尝试；
- 协调：与首次执行相同；
- 输出：新的独立尝试、结论、Bundle 和报告状态；
- 事务：与首次执行相同；
- 幂等：强制；
- 失败：计划已失效、未确认状态恢复、活动尝试、重复意图。

## 5.8 查询用例

### `GetVerificationTask`

返回：

- 任务状态；
- 当前确认计划；
- 最新准备问题；
- 历史计划摘要；
- 历史尝试摘要。

只读短事务，无幂等问题。

### `GetValidationAttempt`

返回：

- 尝试绑定；
- 状态和结论；
- 逻辑步骤；
- 每次实际发送；
- 确定性评估摘要；
- Evidence 和报告引用。

只读短事务。

### `GetEvidenceBundle`

前置：尝试 `COMPLETED` 且 Bundle 存在。

返回完整机器可读证据，不返回明文凭据。

## 5.9 `RegenerateDerivedReport`

- 输入：EvidenceBundle ID、报告格式；
- 前置：Bundle 已封存；
- 协调：EvidenceRepository、ReportRenderer；
- 输出：新的 `DerivedReport` 版本；
- 事务：事务外渲染，短事务插入；
- 幂等：不强制；每次请求产生新报告版本；
- 失败：Bundle 不存在、渲染失败、版本冲突。

## 5.10 `FinalizeInterruptedAttempts`

- 调用者：应用启动生命周期；
- 输入：所有 `EXECUTING` 尝试；
- 前置：启动阶段，尚未接受新的执行请求；
- 协调：AttemptRepository、evaluation、evidence；
- 输出：每个遗留尝试被确定性完成；
- 事务：每个尝试独立处理；
- 幂等：必须幂等；重复启动不得生成第二个评估或 Bundle；
- 禁止：调用 TargetHttpClient；
- 失败：证据损坏、数据库不可写、评估内部错误。

---

# 6. FastAPI 产品接口契约

统一 API 前缀：

```text
/api/v1
```

## 6.1 接口表

| 方法 | 路径 | 含义 | 请求要点 | 响应要点 | 成功码 | 重要失败码 | 类型 | 幂等键 |
|---|---|---|---|---|---|---|---|---|
| POST | `/api/v1/tasks` | 创建任务 | 类型、目标、规则、来源、环境、数据 | DRAFT 任务 | 201 | 422、500 | 命令 | 否 |
| GET | `/api/v1/tasks/{task_id}` | 获取任务 | task ID | 任务、计划和尝试摘要 | 200 | 404 | 查询 | 否 |
| POST | `/api/v1/tasks/{task_id}/preparations` | 首次准备或修订后重新准备 | 可选 revision | 当前状态、规则、计划或准备错误 | 200 | 404、409、422、502、504 | 命令 | 否 |
| POST | `/api/v1/tasks/{task_id}/plan-confirmations` | 确认精确计划 | plan ID、hash、环境/副作用确认 | READY 任务和确认计划 | 200 | 404、409、422 | 命令 | 自然幂等 |
| POST | `/api/v1/tasks/{task_id}/cancellation` | 取消任务 | 原因 | CANCELLED 任务 | 200 | 404、409 | 命令 | 自然幂等 |
| POST | `/api/v1/tasks/{task_id}/attempts` | 首次执行 | 运行时凭据 | 完成尝试、结论、Bundle、报告状态 | 201/200/202 | 404、409、422、500 | 命令 | 必须 |
| POST | `/api/v1/attempts/{attempt_id}/reruns` | 重复运行 | 状态恢复确认、运行时凭据 | 新尝试、结论、Bundle、报告状态 | 201/200/202 | 404、409、422 | 命令 | 必须 |
| GET | `/api/v1/attempts/{attempt_id}` | 获取尝试 | attempt ID | 步骤、发送、评估、引用 | 200 | 404 | 查询 | 否 |
| GET | `/api/v1/attempts/{attempt_id}/evidence` | 获取权威证据 | attempt ID | EvidenceBundle | 200 | 404、409 | 查询 | 否 |
| POST | `/api/v1/attempts/{attempt_id}/reports` | 重新生成报告 | 格式 | 新报告版本 | 201 | 404、409、500 | 命令 | 否 |
| GET | `/api/v1/attempts/{attempt_id}/reports/latest` | 获取最新报告 | attempt ID | 报告内容和版本 | 200 | 404 | 查询 | 否 |

## 6.2 执行幂等

首次执行和重复运行必须要求：

```text
Idempotency-Key: <execution_intent_id>
```

相同任务和相同 Key：

- 已完成：`200 OK`，返回已有尝试；
- 仍为 `EXECUTING`：`202 Accepted`，返回现有 attempt ID；
- 不得创建第二个尝试。

新的明确重复运行必须使用新的 Key。

## 6.3 同步执行响应

执行接口完成后至少返回：

- `task_id`；
- `attempt_id`；
- `attempt_status`；
- `conclusion`；
- `plan_id`；
- `openapi_snapshot_id`；
- `actual_send_count`；
- `evaluation_summary`；
- `evidence_bundle`：
  - ID；
  - `sealed_at`；
  - `manifest_sha256`；
- `report`：
  - `status`: `AVAILABLE` 或 `FAILED`；
  - report ID，可空；
  - report version，可空；
  - 非敏感错误代码，可空。

目标 API 的连接失败、认证失败或超时是验证结果，不应让 ApiGuard 产品 API 返回 502。只要尝试成功封存，应返回正常的 201 和 `EXECUTION_FAILED` 结论。

## 6.4 Swagger 与 Jinja2

Swagger 保留用于：

- 开发；
- API 调试；
- 自动化集成测试。

产品主要流程由 Jinja2 页面完成：

- 创建任务；
- 审查规范化规则和计划；
- 确认计划；
- 输入运行时凭据并执行；
- 查看证据；
- 重复运行。

接口必须独立清晰可测，页面只是这些用例的适配层。

---

# 7. 确定性比较能力边界

## 7.1 V0 支持

| 比较条件 | 是否支持 | 边界 |
|---|---|---|
| 状态码等于 | 是 | 单个整数 |
| 状态码属于集合 | 是 | 非空整数集合 |
| JSON 字段存在 | 是 | RFC 6901 JSON Pointer |
| JSON 字段不存在 | 是 | 与值为 null 明确区分 |
| JSON 字段等于 | 是 | JSON 标量或显式 prior-step 标量 |
| JSON 字段不等于 | 是 | 用于明确前后状态差异 |
| JSON 字段类型 | 是 | string、integer、number、boolean、object、array、null |
| JSON Schema 符合 | 是 | 只引用绑定 OpenAPI 快照中的响应 Schema |
| 响应 Header 存在 | 是 | Header 名大小写不敏感 |
| 响应 Header 等于 | 是 | 一般精确值；Content-Type 比较规范化 media type |
| 字符串包含 | 否 | 不属于冻结任务必需能力，容易形成脆弱文本断言 |
| 数字大小比较 | 是 | `> >= < <=`，操作数为字面量或已声明变量 |

## 7.2 缺失与 null

JSON Pointer 解析返回三种概念结果：

1. `MISSING`：路径不存在；
2. `PRESENT_NULL`：路径存在，值为 JSON `null`；
3. `PRESENT_VALUE`：路径存在且有值。

因此：

- `JSON_PATH_EXISTS` 对 `null` 返回匹配；
- `JSON_PATH_NOT_EXISTS` 只在 `MISSING` 时匹配；
- `JSON_VALUE_TYPE null` 可以判断显式 null；
- 缺失不能自动当成 null。

## 7.3 类型规则

- JSON boolean 不能被当作 integer；
- integer 是没有小数部分的 JSON 数；
- number 包含 integer 和非整数数值；
- 不做字符串到数字的自动转换；
- 不做日期、金额或枚举语义推断。

## 7.4 无法解析的响应

如果某条件需要 JSON，但响应不能解析：

- 完整、未截断且计划明确期望 JSON：该条件为 `MISMATCH`；
- 响应被截断、正文缺失或传输结果未知：该条件为 `NOT_EVALUABLE`；
- 不需要 JSON 的状态码和 Header 条件仍可独立评估。

如果 OpenAPI 声明 JSON 且服务返回完整的非法 JSON，在前置条件充分时可以成为 `SUSPECTED_DEFECT` 证据。

## 7.5 比较器输入

比较器只接收：

- `ValidationPlanSnapshot`；
- `OpenAPIContextSnapshot`；
- 当前 `ValidationAttempt` 的全部 `StepExecutionRecord` 和 `HttpSendRecord`；
- 提取变量；
- 原始执行错误；
- 步骤完整性。

不得接收：

- 用户自由文本；
- 模型原始输出；
- 报告；
- ORM；
- SQLAlchemy Session；
- 其他尝试结果。

## 7.6 比较器输出

输出一个不可变 `EvaluationResult`，包含：

- 每个条件的 expected、actual、result 和 evidence reference；
- `MATCH`、`MISMATCH` 或 `NOT_EVALUABLE`；
- 必要步骤完整性；
- 前置条件证明状态；
- 关键证据缺失；
- 环境或归因歧义；
- 四态结论；
- 固定决策代码。

## 7.7 四态汇总顺序

1. **EXECUTION_FAILED**  
   技术、环境、中断或内部问题使有效验证没有完成，例如认证层阻止业务请求、连接失败、结果未知或内部执行错误。

2. **INCONCLUSIVE**  
   已获得真实响应或执行事实，但关键前置条件未证明、必要变量缺失、响应截断或存在归因歧义。即使观察到部分异常，只要关键缺失足以阻止可靠归因，也不得判定疑似缺陷。

3. **SUSPECTED_DEFECT**  
   必要步骤完成、前置条件已证明、没有关键证据缺失或归因歧义，且至少一项必要条件 `MISMATCH`。

4. **PASSED**  
   必要步骤全部完成、前置条件已证明、所有必要条件 `MATCH`，且没有关键证据缺失。

## 7.8 仍属于计划阶段的语义

比较器不能自由推理：

- 哪个接口代表用户业务动作；
- “订单已支付”是什么意思；
- 一条错误消息是否“语义上差不多”；
- 根因、严重程度和责任人；
- 未确认字段是否应该存在；
- 响应中哪个相似字段可以替代计划字段；
- 是否应该增加查询补充证据。

这些必须在模型生成、确定性校验和用户确认阶段变成明确结构。

---

# 8. 测试和 Fixture 布局

## 8.1 软件测试

### 状态机单元测试

位置：

```text
tests/unit/tasking/
```

覆盖：

- 所有合法转换；
- 所有非法反向转换；
- READY 与确认计划关系；
- 执行中不能取消；
- COMPLETED 不可恢复；
- 任务不拥有权威四态结论。

### OpenAPI 测试

位置：

```text
tests/unit/openapi_context/
tests/fixtures/openapi/
```

覆盖：

- OpenAPI 3.0 和 3.1；
- 路径、方法、参数和 JSON Schema；
- 响应状态与 Content-Type；
- 非法文档；
- 2 MiB 上限；
- 目标操作不存在或不唯一。

### 计划校验测试

覆盖：

- 单目标；
- 最多三逻辑步骤；
- 无循环、分支和并发；
- 数据来源；
- 未来变量引用；
- 最坏实际发送数；
- 三步计划禁止技术重试；
- 不支持比较条件；
- 用户确认 Hash。

### 比较器测试

覆盖每种冻结比较条件和四态决策边界，特别是：

- missing 与 null；
- bool 与 integer；
- 非法 JSON；
- 截断响应；
- 4xx/5xx 不自动等于执行失败；
- 有 mismatch 但关键证据缺失时为 INCONCLUSIVE。

### 执行器测试

覆盖：

- URL、参数、Header 和 JSON 构造；
- 运行时认证只在内存注入；
- 顺序执行；
- 三次实际发送上限；
- GET/HEAD 一次技术重试；
- 有副作用方法不重试；
- 达到三次后停止剩余步骤；
- 变量提取失败；
- 结果未知。

### 脱敏测试

覆盖：

- Authorization、Cookie、Set-Cookie、X-API-Key；
- URL 查询敏感参数；
- JSON 递归敏感字段；
- 大小写变体；
- 原始运行时对象和持久化证据对象分离。

### 持久化测试

位置：

```text
tests/integration/persistence/
```

覆盖：

- Alembic 全新升级；
- 外键；
- WAL；
- 部分唯一索引；
- 执行意图幂等；
- 不可变记录不被 Repository 更新；
- 组合外键保证尝试和计划快照一致；
- Bundle 和报告追加式版本。

### API 集成测试

覆盖全部产品接口、状态码、幂等和敏感字段不返回。

### 启动收尾测试

覆盖：

- 只有 PENDING 步骤；
- 未终止 DISPATCHED 发送；
- 完整响应但未评估；
- T4 回滚后的 EXECUTING；
- COMPLETED 但报告缺失；
- 收尾不调用 TargetHttpClient；
- 重复启动幂等。

## 8.2 模型评测

目录：

```text
evals/model/
```

模型评测不进入默认单元测试门禁。

固定指标：

- 结构化输出成功；
- 前置条件正确性；
- 动作和预期正确性；
- 正确操作映射；
- 缺失信息识别；
- 是否生成超过三步；
- 是否生成分支或动态探索；
- 是否产生不支持的比较条件；
- 候选计划通过确定性校验比例；
- 多次运行关键字段一致性。

软件测试使用固定模型输出，不能依赖真实模型。

## 8.3 参考服务测试控制

参考服务提供仅供测试 Fixture 调用的：

```text
POST /__test__/reset
```

该接口不进入 ApiGuard 验证计划，不计入三次请求上限。状态重置由测试 Fixture 执行，符合“环境恢复由用户或待测环境负责”的基线。

## 8.4 八个端到端场景

最终验收时，每个场景在重置状态后连续执行三次，共 24 次。场景 5 和 6 额外通过产品重复运行接口验证历史不覆盖。

| # | 场景 | 任务类型 | 明确规则 | 参考接口 | 预期 | 关键证据 | 重复运行 | 特殊失败 |
|---|---|---|---|---|---|---|---|---|
| 1 | 商品契约正确 | OpenAPI 契约 | 返回 200，JSON 必填字段和基础类型符合 OpenAPI | `GET /v1/items/{item_id}` | PASSED | 状态码、Content-Type、Schema 判断项 | 三次 | 无 |
| 2 | 商品契约已知错误 | OpenAPI 契约 | `name` 必填且 `price` 为 number | `GET /v1/broken-items/{item_id}` | SUSPECTED_DEFECT | 实际缺少 name 或 price 为 string | 三次 | 无 |
| 3 | 已支付订单取消被正确拒绝 | 单接口业务规则 | 已支付订单取消应返回 409 和 `ORDER_ALREADY_PAID` | `POST /v1/orders/{order_id}/cancel` | PASSED | 409、JSON `/code` 精确值 | 三次 | 无 |
| 4 | 已支付订单被错误取消 | 单接口业务规则 | 同上 | `POST /v1/broken-orders/{order_id}/cancel` | SUSPECTED_DEFECT | 实际 200 且 `/status=cancelled` | 三次 | 无 |
| 5 | 订单支付流程正确 | 三步状态流程 | 创建后支付，最终状态必须为 PAID | `POST /v1/checkout/orders` → `POST /v1/checkout/orders/{id}/pay` → `GET /v1/checkout/orders/{id}` | PASSED | 第一步提取 `/order_id`，第三步 `/status=PAID` | 三次，显式 rerun | 变量提取成功 |
| 6 | 支付接口未更新状态 | 三步状态流程 | 同上 | `/v1/broken-checkout/...` 三步 | SUSPECTED_DEFECT | 支付响应成功但最终仍 PENDING | 三次，显式 rerun | 无 |
| 7 | 会话 ID 缺失导致无法继续 | 三步状态流程 | 创建会话后必须查询并证明 ACTIVE | `POST /v1/session-flows/sessions` 后续依赖 `/session_id` | INCONCLUSIVE | 首步真实 201，但可选 session_id 缺失；后续步骤 SKIPPED | 三次 | 变量提取失败 |
| 8 | 认证未通过目标业务层 | 单接口业务规则 | 有效 API Key 时动作应成功 | `POST /v1/secure/actions` | EXECUTION_FAILED | 401、认证层标记、业务动作未到达 | 三次 | 认证失败 |

固定八场景不使用网络不可达作为验收场景；DNS、连接、TLS 和超时由执行器集成测试覆盖。

---

# 9. 开发里程碑

## 里程碑 1：仓库骨架、领域状态和质量门

输入：最终技术基线。

输出：

- 可安装 Python 3.12 项目；
- FastAPI 启动入口；
- Ruff、Pyright、pytest；
- 核心枚举和 ID；
- VerificationTask 与 ValidationAttempt 状态机；
- 第一批单元测试；
- 基线文档。

验收：

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest tests/unit/tasking -q
uv run python -c "from apiguard.main import app; print(app.title)"
```

不依赖模型、SQLite 业务表、前端或待测服务。

## 里程碑 2：SQLite 持久化与迁移基础

输入：里程碑 1 领域对象。

输出：

- 十一张表的首版迁移；
- 外键、WAL、部分唯一索引；
- Unit of Work 和三类持久化端口；
- 任务和尝试状态持久化；
- 遗留 EXECUTING 查询能力。

验收：

```bash
uv run alembic upgrade head
uv run pytest tests/integration/persistence -q
```

不实现真实启动收尾结论。

## 里程碑 3：OpenAPI 上下文与计划数据契约

输入：固定 OpenAPI Fixture。

输出：

- OpenAPI 来源读取；
- 10 秒超时和 2 MiB 上限；
- OpenAPI 3.0/3.1 操作上下文；
- 规范化规则和计划 Pydantic 模型；
- JSON Pointer 和数据来源类型。

验收：

```bash
uv run pytest tests/unit/openapi_context tests/unit/planning -q
```

不调用真实模型。

## 里程碑 4：计划校验与确定性比较

输入：固定候选计划、OpenAPI 快照和执行事实 Fixture。

输出：

- 计划范围校验；
- 所有冻结比较器；
- 四态决策表；
- EvaluationResult。

验收：

```bash
uv run pytest tests/unit/plan_validation tests/unit/evaluation -q
```

不依赖 HTTP 和模型。

## 里程碑 5：HTTP 执行与证据记录

输入：确认计划 Fixture、HTTPX MockTransport。

输出：

- 请求构造；
- 运行时认证注入；
- 三次实际发送上限；
- 技术重试；
- 变量提取；
- Step/Send 追加式记录；
- 脱敏和响应截断；
- EvidenceBundle 构建器。

验收：

```bash
uv run pytest tests/unit/execution tests/unit/evidence tests/integration/http -q
```

不依赖真实模型和页面。

## 里程碑 6：规则规范化与准备闭环

输入：任务草稿、OpenAPI 快照、Fake PlanGenerator；随后接入单一官方 SDK。

输出：

- 模型端口和适配器；
- 45 秒调用超时；
- 最多三次调用；
- ModelCallRecord；
- PrepareVerificationTask；
- 模型评测集和运行器。

验收：

```bash
uv run pytest tests/integration/llm tests/integration/api/test_prepare_task.py -q
uv run python evals/model/run_eval.py --use-fixtures
```

真实模型评测独立执行，不作为普通测试门禁。

## 里程碑 7：完整同步执行闭环与产品 API

输入：确认计划、Fake/Mock TargetHttpClient。

输出：

- 创建尝试门禁；
- 多短事务执行；
- 评估；
- Bundle 封存；
- COMPLETED；
- 首次执行和查询 API；
- 幂等响应。

验收：

```bash
uv run pytest tests/integration/api/test_execute_task.py -q
```

不依赖 Jinja2 产品页面。

## 里程碑 8：报告与 Jinja2 产品流程

输入：已完成尝试和 EvidenceBundle。

输出：

- Jinja2 报告；
- 报告版本；
- 创建、计划审查、确认、执行和证据页面；
- 少量原生 JS。

验收：

```bash
uv run pytest tests/integration/api tests/integration/reporting -q
```

不增加前端框架。

## 里程碑 9：重复运行与启动收尾

输入：已完成和遗留 EXECUTING 尝试。

输出：

- RerunValidationTask；
- 状态恢复确认；
- 历史不覆盖；
- FinalizeInterruptedAttempts；
- 结果未知请求不重发。

验收：

```bash
uv run pytest tests/integration/startup tests/integration/api/test_rerun.py -q
```

## 里程碑 10：参考服务、八场景与 Docker 演示

输入：完整 ApiGuard V0。

输出：

- 可重置参考 FastAPI 服务；
- 八个固定场景；
- 24 次重复运行；
- Dockerfile 和 Compose；
- 外部可审查证据。

验收：

```bash
docker compose up --build -d
uv run pytest tests/e2e -m e2e -q
docker compose down -v
```

---

# 10. 首个里程碑 Codex 任务卡

以下仅覆盖里程碑 1。每张任务卡应独立提交、独立测试和独立审核。

## 任务卡 M1-01：初始化 Python 仓库与质量门

### 背景

项目尚未建仓，需要建立可重复安装、可静态检查、可测试的最小 Python 工程。

### 目标

创建 Python 3.12、uv、pytest、Ruff 和 Pyright 的可运行项目，使空业务仓库已经具备统一质量门。

### 范围

- 初始化 Git 仓库；
- 创建 `pyproject.toml`；
- 生成 `uv.lock`；
- 配置运行和开发依赖组；
- 配置 Ruff、Pyright、pytest；
- 创建 `.gitignore`、`.env.example` 和基础 README；
- 创建最小包和导入冒烟测试。

### 非目标

- 不创建数据库表；
- 不实现领域状态机；
- 不接入模型、HTTPX 执行和页面；
- 不提前创建所有未来空目录。

### 涉及文件

创建：

- `pyproject.toml`
- `uv.lock`
- `.gitignore`
- `.env.example`
- `README.md`
- `src/apiguard/__init__.py`
- `tests/test_import.py`

### 实现约束

- Python 要求 `>=3.12,<3.13`；
- 依赖由 uv 管理；
- Ruff 同时负责格式和 lint；
- Pyright 使用 strict 或接近 strict 的项目配置；
- 不叠加 Black、isort、Flake8 或 mypy；
- 包必须使用 `src/` 布局。

### 验收标准

- 全新环境 `uv sync` 成功；
- `import apiguard` 成功；
- Ruff、Pyright 和 pytest 全部通过；
- README 写明项目定位、当前里程碑和基本命令。

### 验证命令

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
```

### Codex 必须汇报

- 创建/修改文件列表；
- `uv sync` 结果；
- 四条质量命令的原始摘要；
- 当前依赖列表；
- Git commit hash。

---

## 任务卡 M1-02：建立配置、日志和 FastAPI 启动入口

### 背景

质量门建立后，需要一个不包含业务逻辑的可启动应用外壳。

### 目标

实现配置加载、日志初始化、应用工厂和 Uvicorn 可用入口。

### 范围

- `Settings`；
- 冻结预算常量；
- 日志配置；
- `create_app()`；
- `/health` 开发健康检查；
- FastAPI 启动测试。

### 非目标

- 不注册产品业务路由；
- 不建立数据库连接；
- 不调用启动收尾；
- 不创建 Jinja2 页面；
- 不接入模型和 HTTP 客户端。

### 涉及文件

创建：

- `src/apiguard/config.py`
- `src/apiguard/logging_config.py`
- `src/apiguard/bootstrap.py`
- `src/apiguard/main.py`
- `tests/unit/test_config.py`
- `tests/integration/test_app_startup.py`

修改：

- `pyproject.toml`
- `.env.example`
- `README.md`

### 实现约束

- 使用 `pydantic-settings`；
- 默认值必须与本文档冻结预算一致；
- `main.py` 不直接创建外部客户端；
- 健康检查只证明应用进程可用，不声称核心验证能力完成；
- 日志不得输出配置中的秘密值。

### 验收标准

- `from apiguard.main import app` 成功；
- TestClient 调用 `/health` 返回 200；
- 环境变量可以覆盖非安全预算配置；
- Settings 校验非法负数或零预算；
- 所有质量门通过。

### 验证命令

```bash
uv run pytest tests/unit/test_config.py tests/integration/test_app_startup.py -q
uv run python -c "from apiguard.main import app; print(app.title)"
uv run ruff check .
uv run pyright
```

### Codex 必须汇报

- 启动方式；
- `/health` 实际响应；
- 配置测试数量和结果；
- 是否发现敏感日志风险；
- Git commit hash。

---

## 任务卡 M1-03：冻结共享枚举与标识类型

### 背景

任务和尝试状态机需要稳定、唯一的枚举和 ID 类型，后续模块必须复用同一命名。

### 目标

实现本文档冻结的核心枚举、ID 值类型和少量基础领域错误。

### 范围

- `VerificationTaskType`；
- `VerificationTaskStatus`；
- `ValidationAttemptStatus`；
- `ValidationConclusion`；
- `ValidationPlanStage`；
- `HttpMethod`；
- `StepExecutionStatus`；
- `HttpSendStatus`；
- ID 类型或 NewType；
- 非法状态转换基础错误。

### 非目标

- 不实现计划比较枚举；
- 不实现 ORM Enum；
- 不实现通用错误框架；
- 不加入 shared utils。

### 涉及文件

创建：

- `src/apiguard/shared/__init__.py`
- `src/apiguard/shared/enums.py`
- `src/apiguard/shared/ids.py`
- `src/apiguard/shared/errors.py`
- `tests/unit/shared/test_enums.py`
- `tests/unit/shared/test_ids.py`

### 实现约束

- 枚举持久化值使用大写稳定字符串；
- 不允许同义枚举；
- ID 类型不能依赖 SQLAlchemy；
- shared 不导入任何业务能力包；
- 错误只保留跨状态机真正共用的基类。

### 验收标准

- 枚举成员与本文档完全一致；
- 枚举值 JSON 序列化稳定；
- ID 类型可比较但不会与其他 ID 类型无意混用；
- shared 无反向依赖。

### 验证命令

```bash
uv run pytest tests/unit/shared -q
uv run pyright
uv run ruff check .
```

### Codex 必须汇报

- 最终枚举和值；
- ID 实现选择及理由；
- import 依赖检查；
- 测试结果；
- Git commit hash。

---

## 任务卡 M1-04：实现 VerificationTask 最小实体与状态机

### 背景

任务状态拥有准备和确认生命周期，是后续所有应用用例的门禁基础。

### 目标

实现 `VerificationTask` 最小 dataclass、状态转换和核心不变量。

### 范围

- 创建 DRAFT 任务；
- `DRAFT → PREPARING`；
- `PREPARING → DRAFT`；
- `PREPARING → AWAITING_CONFIRMATION`；
- `AWAITING_CONFIRMATION → PREPARING`；
- `AWAITING_CONFIRMATION → READY`；
- `READY → PREPARING`；
- 合法取消；
- 当前确认计划引用规则；
- 非法转换错误。

### 非目标

- 不实现 OpenAPI、规则和计划完整对象；
- 计划引用暂时只使用稳定 ID；
- 不实现数据库；
- 不实现 FastAPI 路由；
- 不实现执行尝试创建。

### 涉及文件

创建：

- `src/apiguard/tasking/__init__.py`
- `src/apiguard/tasking/models.py`
- `src/apiguard/tasking/state_machine.py`
- `src/apiguard/tasking/policies.py`
- `tests/unit/tasking/test_verification_task_state_machine.py`

### 实现约束

- 状态只能通过明确方法改变；
- 不允许公共代码直接赋值状态；
- READY 必须有确认计划 ID；
- 离开 READY 进入 PREPARING 时清空当前可执行计划引用；
- CANCELLED 为终态；
- Task 不包含四态结论字段；
- 使用 FakeClock 或显式时间输入，禁止在实体内直接调用系统时间。

### 验收标准

- 每条合法转换有测试；
- 每条禁止反向转换有测试；
- READY 无计划引用会失败；
- CANCELLED 不能恢复；
- Task 类型中不存在 conclusion；
- 测试不依赖 FastAPI、SQLAlchemy 或 Pydantic Settings。

### 验证命令

```bash
uv run pytest tests/unit/tasking/test_verification_task_state_machine.py -q
uv run pyright
uv run ruff check .
```

### Codex 必须汇报

- 状态转换表；
- 失败错误类型；
- 测试用例数量；
- 对 READY 不变量的证明；
- Git commit hash。

---

## 任务卡 M1-05：实现 ValidationAttempt 最小实体与状态机

### 背景

验证尝试拥有执行生命周期和四态结论绑定规则，必须与任务状态严格分离。

### 目标

实现 `ValidationAttempt` 最小实体及 `EXECUTING → COMPLETED` 状态机。

### 范围

- 创建 EXECUTING 尝试；
- 固定绑定 task、plan、OpenAPI snapshot 和 execution intent；
- 首次/重复运行标识；
- 实际发送计数；
- 最终完成；
- conclusion、evaluation ID 和 evidence ID 同时绑定；
- COMPLETED 终态。

### 非目标

- 不实现 HTTP 发送；
- 不实现 StepExecutionRecord 和 HttpSendRecord 的完整请求响应字段；
- 不实现数据库单活动尝试约束；
- 不实现评估和 Bundle 内容。

### 涉及文件

修改：

- `src/apiguard/tasking/models.py`
- `src/apiguard/tasking/state_machine.py`

创建：

- `tests/unit/tasking/test_validation_attempt_state_machine.py`

### 实现约束

- EXECUTING 时 conclusion/evaluation/evidence 必须为空；
- COMPLETED 时三者必须同时存在；
- 发送计数只允许增加且不得超过三；
- 绑定字段创建后不可替换；
- COMPLETED 不允许回到 EXECUTING；
- Attempt 不能修改 VerificationTask 状态；
- 使用显式时间输入。

### 验收标准

- 创建和完成路径通过；
- 缺少任一最终引用不能完成；
- 第四次发送计数增加被拒绝；
- COMPLETED 后所有状态修改被拒绝；
- 任务状态和尝试状态测试相互独立。

### 验证命令

```bash
uv run pytest tests/unit/tasking/test_validation_attempt_state_machine.py -q
uv run pytest tests/unit/tasking -q
uv run pyright
uv run ruff check .
```

### Codex 必须汇报

- 最终实体字段；
- 完成不变量测试证据；
- 三次发送上限测试证据；
- Git commit hash。

---

## 任务卡 M1-06：保存项目基线并完成里程碑说明

### 背景

项目的重要结论必须进入仓库，聊天不能成为唯一事实来源。

### 目标

把三份冻结基线和首个里程碑任务卡保存到仓库，并更新 README 的事实来源说明。

### 范围

- 保存范围基线；
- 保存架构基线；
- 保存本文档；
- 保存里程碑 1 任务卡；
- README 链接基线、启动方式和质量命令；
- 写明代码、迁移、测试和真实运行结果优先于聊天。

### 非目标

- 不重新编辑或扩展基线；
- 不添加未冻结技术；
- 不写每日复盘或项目管理模板；
- 不创建未来全部 Codex 任务。

### 涉及文件

创建：

- `docs/baselines/00-v0-scope.md`
- `docs/baselines/01-v0-architecture.md`
- `docs/baselines/02-v0-technical-design-and-development.md`
- `docs/codex/milestone-01-task-cards.md`

修改：

- `README.md`

### 实现约束

- 两份上位基线内容原样保存；
- 本文档作为第三份正式基线；
- 任务卡不得擅自扩大范围；
- README 不宣称尚未实现的核心能力已经完成。

### 验收标准

- 所有文档路径存在；
- README 链接有效；
- 文档中的命令与项目实际配置一致；
- 全部质量门仍通过。

### 验证命令

```bash
test -f docs/baselines/00-v0-scope.md
test -f docs/baselines/01-v0-architecture.md
test -f docs/baselines/02-v0-technical-design-and-development.md
test -f docs/codex/milestone-01-task-cards.md
uv run ruff check .
uv run pyright
uv run pytest -q
```

### Codex 必须汇报

- 文档文件列表；
- 是否原样保存上位基线；
- README 链接检查；
- 最终完整质量门结果；
- 里程碑 1 的提交列表和最终 HEAD commit hash。

---

# 11. 建仓前仍未决定的问题

没有阻止建仓或里程碑 1 的未决问题。

以下问题已明确推迟到对应实现里程碑，在该阶段开始前做一次局部选择即可，不重新打开宏观架构：

1. **单一模型供应商和具体模型名称**  
   最迟在里程碑 6 开始前决定。必须使用官方 SDK，且不改变 `PlanGenerator` 契约。

2. **成熟 OpenAPI 3.0/3.1 解析/校验库的具体组合**  
   最迟在里程碑 3 开始前用小型技术验证决定。不得自己实现完整 OpenAPI 解析器。

3. **Jinja2 报告的首个默认格式**  
   推荐默认 HTML，并保留机器可读 Evidence JSON；具体视觉模板在里程碑 8 决定，不影响领域对象。

4. **模型 Prompt 具体内容和版本号**  
   在里程碑 6 根据模型评测集冻结，不属于领域或执行架构。

除此之外，包名、Python 版本、API 前缀、状态、表名、端口、比较能力、预算、里程碑和首批任务均已冻结。

---

# 12. 最终自检与冻结结论

## 12.1 与上位基线一致

- 保留三类任务和单目标；
- 最多三逻辑步骤；
- 最多三实际 HTTP 发送；
- 用户确认精确计划；
- 模型只参与语义转换；
- 确定性程序拥有执行和四态判定；
- 报告不成为事实来源；
- 重复运行创建新尝试；
- 真实 HTTP 和证据是完成证明。

## 12.2 未引入非目标

未加入：

- LangGraph、LangChain；
- RAG、多 Agent；
- Worker、队列；
- React；
- PostgreSQL；
- 微服务；
- CI/CD 平台集成；
- 生产监控；
- 自动修复；
- 任意表达式语言。

## 12.3 抽象和依赖检查

- 只为外部能力建立七类端口；
- 比较器和校验器保持确定性内部代码；
- Web 不接触 ORM；
- 应用层不接触 SQLAlchemy Session；
- HTTPX 和供应商 SDK 类型不向领域传播；
- shared 保持最小。

## 12.4 状态与数据库一致性

- 任务状态和尝试状态分别拥有；
- SQLite 部分唯一索引保证单活动尝试；
- 组合外键保证尝试绑定正确计划和快照；
- Bundle 插入即封存；
- COMPLETED 与评估、Bundle、结论同事务形成；
- 报告在事务提交后派生。

## 12.5 事务和恢复检查

- OpenAPI、模型、待测 HTTP 和报告渲染均在数据库事务外；
- 每次发送前后使用短事务；
- 结果未知请求不重发；
- 达到三次发送后停止；
- 启动收尾不调用待测 HTTP；
- SQLite 单进程可实现。

## 12.6 开发反馈检查

从任务卡 M1-01 开始，每个任务均能产生：

- 独立 Git 提交；
- 明确文件变化；
- 可运行验证命令；
- 可审查测试证据；
- 不依赖后续模型、数据库或页面。

## 12.7 正式冻结

《ApiGuard V0 技术设计与开发拆分》至此完成冻结。

下一步不再继续宏观设计，而是：

1. 将三份基线保存到项目源；
2. 建立 GitHub 仓库；
3. 将任务卡 M1-01 交给 Codex；
4. Codex 按任务卡实现、测试和提交；
5. 以 Diff、测试输出和真实运行结果进行阶段评审。
