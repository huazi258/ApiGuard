# ApiGuard V0｜里程碑 1 Codex 任务卡

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

