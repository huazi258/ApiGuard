# ApiGuard V0｜建仓交接摘要

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

