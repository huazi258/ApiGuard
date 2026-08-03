# ApiGuard V0｜里程碑 3 Codex 任务卡

> 文档状态：Milestone 3 开发任务冻结版
> 适用仓库：`huazi258/ApiGuard`
> 开发基线：`main` / `5a4f7a5c324cac4b7988548d53fb77cc2a699da7`
> 上位文档：
> 1. `docs/baselines/00-v0-scope.md`
> 2. `docs/baselines/01-v0-architecture.md`
> 3. `docs/baselines/02-v0-technical-design-and-development.md`
> 4. `docs/milestones/milestone-03-openapi-context-and-plan-contracts.md`
>
> 以下只覆盖 Milestone 3。每张任务卡必须独立提交、独立测试、独立审核。Codex 不得在当前任务中提前实现下一任务或后续里程碑能力。

---

# 0. 全局开发规则

## 0.1 开始前必须确认

每张任务开始前执行并汇报：

```bash
git branch --show-current
git rev-parse HEAD
git status --short
uv sync --locked
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

要求：

- 分支和 HEAD 与当前任务基线一致；
-工作区无未解释修改；
-现有全量测试和质量门通过；
-若 HEAD 已变化，先读取变化，不得按旧任务卡猜测当前实现。

## 0.2 开发方法

每张任务按以下顺序执行：

1. 读取本任务和相关冻结设计；
2.检查已有实现和命名；
3.写失败测试；
4.运行测试，确认因缺失当前能力而失败；
5.实现最小代码；
6.运行专项测试；
7.运行全量测试和质量门；
8.执行 `git diff --check`；
9.检查 `git status --short`；
10.只提交当前任务文件；
11.提交后保持工作区干净。

## 0.3 全局技术约束

- Python `>=3.12,<3.13`；
-使用 uv 和锁文件；
-Pydantic v2 用于公开结构化契约；
-同步 HTTPX；
-PyYAML SafeLoader；
-模块化单体；
-领域和 planning 不导入 FastAPI、SQLAlchemy、HTTPX 或第三方 OpenAPI 对象；
-外部适配器不得泄漏框架类型；
-所有公开快照深层不可变；
-所有稳定错误使用 ApiGuard 自己的 code；
-不得依赖公网、真实模型、真实待测 API 或 SQLite。

## 0.4 全局非目标

所有 M3 任务都不得实现：

- 模型 SDK、Prompt、模型调用；
-真实规则规范化或计划生成；
-计划确定性校验；
-用户确认；
-待测 API HTTP 执行；
-运行时变量求值；
-响应比较；
-`EvaluationResult`；
-四态结论；
-`EvidenceBundle`；
-报告和页面；
-新数据库迁移；
-新 Repository/Unit of Work 接口；
-任务准备用例；
-启动恢复；
-RAG、多 Agent、队列、Worker 或通用工作流引擎。

## 0.5 每张任务必须汇报

- 当前分支、起始 HEAD 和工作区状态；
-创建/修改文件列表；
-实现行为；
-测试清单；
-实际运行命令和结果；
-`git diff --stat`；
-提交 SHA；
-提交后 `git status --short`；
-剩余工作；
-已知限制；
-是否发现与冻结基线冲突。

---

# 1. 任务顺序

| 任务 | 独立交付能力 |
|---|---|
| M3-00 | 保存 M3 冻结设计与任务卡 |
| M3-01 | RFC 6901 JsonPointer、来源契约与本地读取 |
| M3-02 | 远程 HTTP OpenAPI 来源读取 |
| M3-03 | 严格 UTF-8、JSON 和 YAML 文档解析 |
| M3-04 | OpenAPIContextSnapshot 不可变数据契约 |
| M3-05 | 文档内 `$ref` 解析与追溯 |
| M3-06 | OpenAPI 3.0/3.1 SchemaContext 投影 |
| M3-07 | 选中 operation 的完整上下文构建 |
| M3-08 | NormalizedRule 与规划基础值 |
| M3-09 | ValidationPlanSnapshot 完整数据契约 |
| M3-10 | 固定 Fixture、golden 与阶段验收 |
| M3-11 | 正式封板 Milestone 3 |

执行顺序固定。不得把 M3-04 至 M3-07 并行实现，也不得在 M3-08 之前实现完整计划模型。

---

# 2. 任务卡 M3-00：保存 M3 设计基线与任务卡

## 背景

M3 的问题、范围、OpenAPI 子集、数据契约、引用规则、Fixture 和技术选型已经完成设计冻结。开发前必须把结论保存进仓库，聊天不能成为唯一事实来源。

## 目标

保存两份正式文档，使 Codex 后续能够只依赖仓库任务和冻结设计进行实现。

## 范围

创建：

```text
docs/milestones/milestone-03-openapi-context-and-plan-contracts.md
docs/codex/milestone-03-task-cards.md
```

第一份保存：

- M3 问题、输入、输出和完成证据；
-范围与非目标；
-来源读取；
-解析与快照边界；
-OpenAPI 3.0/3.1 最小支持；
-operation/参数/request/response/Schema 数据契约；
-`$ref` 和错误分类；
-planning 数据契约；
-Fixture 和验收；
-技术选型；
-实现前修正；
-架构不变量。

第二份保存本任务拆分。

## 非目标

- 不修改 Python 代码；
-不修改依赖；
-不创建空模块；
-不修改数据库；
-不宣称 M3 已实现；
-不重新编辑三份 V0 全局基线。

## 验收标准

- 两个文件存在；
-README 仍准确写明 M3 尚未开始；
-文档不包含聊天 citation 标记；
-文档不遗漏 M3 非目标；
-路径和命令与仓库一致；
-现有质量门无回归。

## 验证命令

Linux/macOS：

```bash
test -f docs/milestones/milestone-03-openapi-context-and-plan-contracts.md
test -f docs/codex/milestone-03-task-cards.md
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
git diff --check
```

PowerShell 使用 `Test-Path` 进行等价文件检查。

## 推荐提交

```text
docs: freeze milestone 3 design and task cards
```

## 评审重点

- 设计是否完整进入仓库；
-是否错误修改上位基线；
-是否提前声明 M3 已完成；
-文档之间是否互相冲突。

---

# 3. 任务卡 M3-01：JsonPointer、来源契约与本地读取

## 背景

OpenAPI 内容进入系统前需要稳定来源描述、读取结果、错误分类和 RFC 6901 Pointer 值对象。本任务先建立纯数据契约和本地文件来源，不处理网络和文档语义。

## 目标

实现：

- RFC 6901 `JsonPointer`；
-OpenAPI 来源契约；
-本地文件来源读取；
-2 MiB 硬限制；
-原始字节 SHA-256；
-稳定来源错误。

## 范围

创建：

```text
src/apiguard/shared/json_pointer.py
src/apiguard/openapi_context/__init__.py
src/apiguard/openapi_context/source.py
src/apiguard/infrastructure/openapi/__init__.py
src/apiguard/infrastructure/openapi/local_source.py
tests/unit/shared/test_json_pointer.py
tests/unit/openapi_context/test_source_contracts.py
tests/unit/openapi_context/test_local_source.py
```

修改：

```text
pyproject.toml
uv.lock
```

增加直接生产依赖：

```toml
pydantic>=2.10,<3
```

## 必须产生的接口

### `JsonPointer`

- 从字符串严格构造；
-根为 `""`；
-非根以 `/` 开始；
-只允许 `~0`、`~1`；
-序列化为字符串；
-可比较、可 hash；
-可返回解码 tokens；
-不执行实际 JSON 求值。

### 来源契约

```text
OpenAPISourceKind
OpenAPISourceDescriptor
OpenAPISourceAttemptOutcome
OpenAPISourceReadAttempt
OpenAPISourceReadResult
OpenAPISourceErrorCode
OpenAPISourceError
OpenAPISource Protocol
```

### 本地适配器

```text
LocalFileOpenAPISource
```

## 实现约束

- Descriptor 构造不得访问文件系统；
-本地适配器负责存在性、目录、普通文件、权限和大小；
-本地来源不重试；
-正好 2 MiB 成功；
-2 MiB + 1 byte 失败；
-超限不得返回截断正文；
-`content_sha256` 依据完整原始 bytes；
-相对路径展示值不得自动绝对路径化；
-返回对象深层不可变；
-不引入 HTTPX；
-不解析 JSON/YAML。

## 先写的失败测试

至少覆盖：

-根 Pointer；
-普通 Pointer；
-`~0`、`~1`；
-`/` 空 key；
-`#` fragment 拒绝；
-JSONPath 拒绝；
-非法 `~2` 和结尾 `~`；
-普通文件成功；
-未知扩展名成功；
-文件不存在；
-目录；
-空文件；
-无权限；
-正好 2 MiB；
-2 MiB + 1；
-预检查后文件增长；
-SHA-256；
-相对路径展示值；
-结果不可变。

## 非目标

- 远程 HTTP；
-重试；
-文本解码；
-OpenAPI 版本；
-快照；
-数据库。

## 验收标准

- 本地 JSON/YAML 都作为 bytes 成功读取；
-所有来源错误映射为稳定 code；
-结果不泄漏文件对象；
-失败不返回部分内容；
-`JsonPointer` 公共 JSON 是字符串；
-所有专项和全量质量门通过。

## 专项验证

```bash
uv run pytest \
  tests/unit/shared/test_json_pointer.py \
  tests/unit/openapi_context/test_source_contracts.py \
  tests/unit/openapi_context/test_local_source.py \
  -q
```

## 推荐提交

```text
feat: add local openapi source contracts
```

## 评审重点

- Descriptor 是否偷偷访问文件系统；
-是否把路径绝对化；
-是否误把 Pointer 求值提前实现；
-大小边界是否真实防止超量读取。

---

# 4. 任务卡 M3-02：远程 HTTP OpenAPI 来源读取

## 背景

本地来源完成后，需要同步 HTTPX 适配器读取远程 OpenAPI，同时严格控制超时、大小、重试、重定向和敏感信息。

## 目标

实现受预算约束的远程 HTTP/HTTPS OpenAPI 原始字节读取。

## 范围

创建：

```text
src/apiguard/infrastructure/openapi/http_source.py
tests/unit/openapi_context/test_http_source.py
```

修改：

```text
pyproject.toml
uv.lock
```

把：

```toml
httpx>=0.28,<1
```

移入生产依赖，并从 dev group 删除重复声明。

## 必须实现

- 同步 HTTP/HTTPS GET；
-不发送认证 Header/Cookie；
-不跟随重定向；
-单次 10 秒整体预算；
-最多两次 attempt；
-一次临时网络重试；
-2 MiB 流式硬限制；
-Content-Type 保存；
-query value 全部脱敏；
-稳定 HTTP/网络错误分类；
-失败 attempt 保留已接收字节数；
-第二次读取必须从头开始。

## 实现约束

不能仅设置 HTTPX 各阶段 timeout 后声称整体 10 秒预算已满足。实现需要可测试 deadline：

- 通过可注入 monotonic clock 或内部 deadline；
-预算覆盖连接、TLS、响应头和正文流；
-测试不实际等待 10 秒。

只重试：

- timeout；
-临时 DNS/连接问题；
-连接重置/正文中断；
-502/503/504。

不重试：

-401/403；
-404/410；
-429；
-500；
-TLS 证书失败；
-redirect；
-empty；
-too large。

## 先写的失败测试

必须覆盖：

-200 JSON；
-200 YAML；
-错误或缺失 Content-Type；
-200 HTML 仍为来源成功；
-204；
-301/302/303/307/308；
-401/403；
-404/410；
-429；
-500；
-503 → 200；
-503 → 503；
-timeout → 200；
-timeout → timeout；
-TLS failure 不重试；
-Content-Length 超限；
-无 Content-Length 流式超限；
-Content-Length 小于实际正文；
-部分正文中断后第二次成功；
-URL 用户信息拒绝；
-query 脱敏；
-fragment 拒绝；
-FTP 拒绝。

全部使用 MockTransport 或等价受控 transport。

## 非目标

- 来源认证；
-重定向；
-外部 `$ref`；
-待测业务接口；
-正文解析；
-异步 HTTPX。

## 验收标准

- 单次 attempt 和重试事实准确；
-超限立即停止，不返回部分正文；
-失败正文不拼接；
-所有用户可见 URL 已脱敏；
-外部类型不越过来源端口；
-专项和全量质量门通过。

## 专项验证

```bash
uv run pytest tests/unit/openapi_context/test_http_source.py -q
```

## 推荐提交

```text
feat: add bounded remote openapi reading
```

## 评审重点

- “10 秒”是否只是配置名而非真实 deadline；
-重试条件是否扩大；
-是否跟随 redirect；
-是否把远程 OpenAPI 请求与未来 TargetHttpClient 混在一起。

---

# 5. 任务卡 M3-03：严格 OpenAPI 文档解析

## 背景

来源层只保证取得完整 bytes，不判断编码和文档语法。现在需要把 bytes 转为无重复键、JSON 兼容的普通数据树。

## 目标

实现严格 UTF-8、JSON-first、Safe YAML fallback 的文档解析器。

## 范围

创建：

```text
src/apiguard/openapi_context/document_parser.py
tests/unit/openapi_context/test_document_parser.py
```

修改：

```text
pyproject.toml
uv.lock
```

增加生产依赖：

```toml
PyYAML>=6.0.3,<7
```

## 必须产生的内部对象

```text
DecodedOpenAPIDocument
OpenAPIDocumentFormat
ParsedOpenAPIDocument
OpenAPIDocumentErrorCode
OpenAPIDocumentError
```

## 实现约束

- 只支持 UTF-8 和 UTF-8 BOM；
-明确 UTF-16/32 BOM 拒绝；
-HTTP 非 UTF-8 charset 拒绝；
-先严格 JSON，失败后 Safe YAML；
-JSON object pair hook 检测重复键；
-JSON `parse_constant` 拒绝 NaN/Infinity；
-YAML 从 SafeLoader 派生；
-YAML 重复 key 必须拒绝；
-最终必须是字符串 key 的 JSON 兼容树；
-禁止日期、bytes、set、自定义对象、递归 alias；
-不得修改 `OpenAPISourceReadResult`；
-不得判断 OpenAPI 版本。

## 先写的失败测试

-UTF-8 JSON；
-UTF-8 YAML；
-BOM；
-非法 UTF-8；
-UTF-16 BOM；
-HTTP charset 非 UTF-8；
-JSON 根对象；
-YAML 根对象；
-JSON 根数组；
-YAML 根列表；
-普通文本；
-HTML；
-JSON 顶层和嵌套重复键；
-YAML 顶层和嵌套重复键；
-非字符串 key；
-NaN/Infinity；
-YAML 日期；
-自定义 tag；
-递归 alias；
-解析器不修改输入。

## 非目标

- `openapi` 字段；
-info/paths；
-operation；
-`$ref`；
-快照；
-第三方完整规范校验。

## 验收标准

- 读取成功但语法失败能清晰分层；
-解析结果只含普通 JSON 值；
-错误 code 不依赖 PyYAML/JSONDecoder 原始文本；
-`ParsedOpenAPIDocument` 不暴露给 planning；
-专项和全量质量门通过。

## 专项验证

```bash
uv run pytest tests/unit/openapi_context/test_document_parser.py -q
```

## 推荐提交

```text
feat: add strict openapi document parsing
```

## 评审重点

- SafeLoader 是否真的严格；
-重复键是否被覆盖；
-YAML 日期等对象是否泄漏；
-解析器是否开始做 OpenAPI 语义判断。

---

# 6. 任务卡 M3-04：OpenAPIContextSnapshot 数据契约

## 背景

来源和解析完成后，需要先冻结公开领域数据模型，再实现 resolver 和 builder，避免实现反向决定契约。

## 目标

实现 M3 已冻结的不可变 OpenAPI 上下文数据契约，不从文档构造它们。

## 范围

创建：

```text
src/apiguard/openapi_context/models.py
tests/unit/openapi_context/test_context_models.py
```

## 必须实现的模型类别

- OpenAPI 版本和文档 metadata；
-operation key/context；
-parameter 和 serialization；
-media type；
-request body；
-response selector/context；
-SchemaContext 与约束；
-security；
-server candidates；
-diagnostics；
-reference resolution record；
-OpenAPIContextSnapshot。

## 接口要求

复用已有：

```text
HttpMethod
OpenAPIContextSnapshotId
```

不得新建同义枚举或字符串替代。

## 实现约束

- 所有公开模型 `frozen=True`；
-`extra="forbid"`；
-嵌套 tuple；
-无原始 dict；
-无 raw bytes；
-无 HTTPX/SQLAlchemy/第三方 OpenAPI 类型；
-Response default 使用判别联合；
-只接受精确小写 `default` 的输入表示；
-无显式 server 时为空；
-`SchemaKind.ANY` 可携带 conditional object/array constraints；
-`SuggestedValueContext.authoritative` 固定 false；
-`ServerCandidateContext.authoritative_for_execution` 固定 false；
-敏感凭据字段不存在。

## 先写的失败测试

-每类模型合法构造；
-非法 extra field；
-顶层赋值失败；
-嵌套 property/tuple 修改失败；
-model dump/model validate 往返；
-raw_document 字段不存在；
-第三方对象不可序列化进入；
-response exact/default 联合；
-default 大小写；
-ANY + object constraints；
-additionalProperties 三态；
-readOnly/writeOnly 冲突；
-server candidate 不权威。

## 非目标

- 文档读取；
-文档解析；
-引用解析；
-Schema 投影；
-operation 构建；
-Schema 实例校验；
-持久化。

## 验收标准

- 手工 3.0/3.1 快照对象可严格构造；
-深层不可变；
-JSON 往返相等；
-领域模型与第三方库隔离；
-契约内容与冻结文档一致；
-专项和全量质量门通过。

## 专项验证

```bash
uv run pytest tests/unit/openapi_context/test_context_models.py -q
```

## 推荐提交

```text
feat: add openapi context data contracts
```

## 评审重点

- 是否把完整 OpenAPI 对象图搬进领域模型；
-是否只冻结顶层但嵌套可变；
-是否创建未来执行字段；
-是否错误合成 server。

---

# 7. 任务卡 M3-05：文档内 `$ref` 解析与追溯

## 背景

选中 operation 的参数、请求体、响应和 Schema 可能引用 components。M3 必须在不访问外部资源的情况下解析受限引用并形成追溯记录。

## 目标

实现纯内存、文档内、类型安全的 `$ref` resolver。

## 范围

创建：

```text
src/apiguard/openapi_context/references.py
tests/unit/openapi_context/test_reference_resolution.py
```

## 必须实现

- fragment-only `$ref`；
-RFC 6901 pointer；
-Schema、Parameter、RequestBody、Response、SecurityScheme 五类目标；
-目标类型检查；
-同类型多跳；
-最大 32 跳；
-活动栈循环检测；
-成功缓存；
-3.0 Reference Object sibling 诊断；
-3.1 Reference Object summary/description override；
-3.1 Schema `$ref` sibling 拒绝；
-ReferenceResolutionRecord。

## 输入输出边界

Resolver 只接收：

```text
ParsedOpenAPIDocument.root
引用字符串
引用出现 pointer
期望 target kind
OpenAPI version family
```

不得接收或调用：

- `OpenAPISource`；
-HTTPX client；
-文件 reader；
-数据库；
-模型。

## 实现约束

- 只允许 `#/components/.../{name}`；
-不允许根 `#`；
-不允许任意嵌套 pointer；
-Path Item `$ref` 拒绝；
-外部 URL/相对文件拒绝且零 I/O；
-目标 collection 决定类型，不按字段猜测；
-公共子目标重复使用不算循环；
-递归 Schema 返回 unsupported，不能降级；
-多跳每个 `$ref` 都记录 resolution；
-Context source pointer 以后指向最终具体对象。

## 先写的失败测试

-五类直接引用；
-两跳引用；
-`~0`、`~1` component 名称；
-目标不存在；
-目标非 object；
-Parameter → Response；
-同类型 32 跳；
-33 跳；
-直接/间接非 Schema 循环；
-直接/间接 Schema recursion；
-同一 Schema 多分支复用；
-HTTP URL；
-相对文件；
-Path Item；
-anchor；
-dynamicRef；
-3.0 sibling；
-3.1 Reference Object override；
-3.1 Schema `$ref` + description；
-零网络/零文件调用。

## 非目标

- Path Item 展开；
-外部文档；
-完整 JSON Schema resolver；
-SchemaContext 投影；
-operation 构建。

## 验收标准

- 受支持引用可确定性解析；
-不支持引用分类准确；
-循环与公共子图不混淆；
-每条引用可追溯；
-无外部 I/O；
-专项和全量质量门通过。

## 专项验证

```bash
uv run pytest tests/unit/openapi_context/test_reference_resolution.py -q
```

## 推荐提交

```text
feat: add local openapi reference resolution
```

## 评审重点

- Resolver 是否偷用第三方自动远程解析；
-循环检测是否使用全局 visited；
-3.0/3.1 sibling 是否混用；
-失败是否被降级为 ANY。

---

# 8. 任务卡 M3-06：OpenAPI 3.0/3.1 SchemaContext 投影

## 背景

引用解析完成后，需要把受支持的 3.0/3.1 Schema 统一投影为有限、不可变 `SchemaContext`。本任务不处理 operation，也不校验真实实例。

## 目标

实现 OpenAPI 3.0/3.1 Schema 子集到统一领域契约的确定性投影。

## 范围

创建：

```text
src/apiguard/openapi_context/schema_projector.py
tests/unit/openapi_context/test_schema_projector.py
```

## 必须实现

- `ANY/OBJECT/ARRAY/STRING/INTEGER/NUMBER/BOOLEAN/NULL`；
-properties；
-required；
-items；
-3.0 nullable；
-3.1 type + null；
-纯 null；
-enum；
-format；
-string length；
-array length；
-numeric bounds；
-3.0/3.1 exclusive 统一；
-readOnly/writeOnly；
-additionalProperties 三态；
-default/example 非权威；
-Schema `$ref`；
-source pointer。

## 实现约束

- 缺失 type 不推断 object/array；
-`ANY` 可保留 conditional constraints；
-明确 ARRAY 必须有 items；
-多类型 union 只允许一个基础类型 + null；
-纯 null 使用 `kind=NULL`；
-oneOf/allOf/复杂 anyOf 阻断；
-additionalProperties 为 Schema 阻断；
-recursion 阻断；
-readOnly/writeOnly 同时 true 阻断；
-enum 只允许 JSON 标量并与 kind/nullable 基本兼容；
-bool 不当 number；
-NaN/Infinity 拒绝；
-不实现实例校验。

## 先写的失败测试

-3.0 string nullable；
-3.1 string + null；
-pure null；
-string/integer/number/boolean；
-object properties/required；
-required 名称没有 property；
-array/items；
-array 缺 items；
-empty Schema；
-properties without type；
-items without type；
-additionalProperties missing/true/false/Schema；
-string min/max；
-array min/max；
-3.0 exclusive bool；
-3.1 exclusive numeric；
-invalid lower/upper；
-enum；
-object/array enum 拒绝；
-oneOf/allOf/complex anyOf；
-readOnly/writeOnly；
-default/example；
-ref source pointer；
-recursion。

## 非目标

- JSON Schema validator；
-format 验证；
-pattern；
-multipleOf；
-完整 2020-12；
-operation/request/response 构建；
-M4 比较器。

## 验收标准

- 3.0/3.1 形成同一 `SchemaContext` 类型；
-语义差异被正确统一或拒绝；
-不支持结构不被降级；
-所有结果不可变和稳定；
-专项和全量质量门通过。

## 专项验证

```bash
uv run pytest tests/unit/openapi_context/test_schema_projector.py -q
```

## 推荐提交

```text
feat: project supported openapi schemas
```

## 评审重点

- 是否为图省事把所有未知 Schema 转成 ANY；
-是否错误推断 object；
-3.0/3.1 exclusive 语义是否混淆；
-是否提前引入 jsonschema 实例校验。

---

# 9. 任务卡 M3-07：构建选中 Operation 上下文

## 背景

来源、解析、数据模型、引用和 Schema 投影已完成。现在需要把明确选中的 operation 及依赖闭包原子构造成 `OpenAPIContextSnapshot`。

## 目标

实现 OpenAPI 3.0/3.1 最小文档检查、operation 选择和完整上下文构建。

## 范围

创建：

```text
src/apiguard/openapi_context/builder.py
tests/unit/openapi_context/test_context_builder.py
```

## 必须实现

-版本识别；
-info；
-paths；
-operation 选择；
-operationId 一致性；
-Path Item + operation 参数覆盖；
-path/query/header 参数；
-默认标量序列化；
-JSON media type；
-request body；
-responses；
-security；
-effective server candidates；
-Schema projector；
-reference resolver；
-operation scope；
-reference records；
-diagnostics；
-快照来源身份；
-多 operation 原子构建；
-稳定排序。

## 输入

```text
OpenAPISourceReadResult
ParsedOpenAPIDocument
operation selections
caller-provided OpenAPIContextSnapshotId
```

不得接收用户业务规则、模型输出、target base URL、认证、ORM 或真实响应。

## 实现约束

- 只检查最低顶层结构和选中依赖闭包；
-未选 operation 的错误不阻断；
-选中任一 operation 失败则整个构建失败；
-不返回部分快照；
-不扫描所有 paths；
-operation 权威身份 path + method；
-支持 GET/HEAD/POST/PUT/PATCH/DELETE；
-Path 参数与占位符一一对应；
-operation 参数完整覆盖同身份 Path Item 参数；
-Header 名称大小写不敏感；
-只支持标量参数和默认 style；
-保留 Header 不进入普通参数；
-必需请求体必须至少一个支持 JSON media type；
-可选非 JSON request body 可忽略并诊断；
-非 JSON response 仍保留 status；
-response default 只接受小写；
-无显式 server 时不合成；
-security 只保存声明；
-相同输入产生相同业务内容；
-不调用完整 OpenAPI validator。

## 先写的失败测试

-3.0 正常文档；
-3.1 正常文档；
-missing/invalid/unsupported version；
-info invalid；
-paths invalid；
-operation not found；
-method unsupported；
-operationId conflict；
-path parameter missing/extra/not required；
-Path Item override；
-same-level duplicate parameter；
-header case duplicate；
-cookie/deepObject；
-requestBody absent/optional/required；
-multiple JSON types；
-required multipart；
-response exact/default/no body/non-JSON；
-invalid response key；
-media type normalize/duplicate；
-security document/operation/empty override；
-server priority；
-unselected bad operation；
-selected bad operation；
-multi-operation success；
-multi-operation atomic failure；
-snapshot does not contain raw document；
-source SHA/size propagated；
-stable ordering。

## 非目标

- 计划生成；
-规则理解；
-参数值校验；
-请求执行；
-响应实例校验；
-持久化；
-产品 API。

## 验收标准

- 固定 3.0/3.1 文档能够产生完整手工预期上下文；
-未选不支持 operation 不影响目标；
-所有失败均无部分快照；
-快照深层不可变；
-不含第三方对象；
-专项和全量质量门通过。

## 专项验证

```bash
uv run pytest tests/unit/openapi_context/test_context_builder.py -q
```

## 推荐提交

```text
feat: build selected openapi operation context
```

## 评审重点

- 是否退化为整份文档全量 validator；
-未选 operation 是否错误阻断；
-参数覆盖是否合并字段而非完整覆盖；
-是否把 server 当执行环境；
-是否生成部分快照。

---

# 10. 任务卡 M3-08：NormalizedRule 与规划基础值

## 背景

OpenAPI 上下文完成后，需要建立模型未来输出的候选规则语义和规划基础值。本任务不调用模型，也不构造完整计划。

## 目标

实现深层不可变 JSON、`NormalizedRule` 和 operation 候选映射。

## 范围

创建：

```text
src/apiguard/planning/__init__.py
src/apiguard/planning/primitives.py
src/apiguard/planning/rules.py
tests/unit/planning/test_primitives.py
tests/unit/planning/test_normalized_rule.py
```

修改：

```text
src/apiguard/shared/ids.py
tests/unit/shared/test_ids.py
```

新增：

```text
NormalizedRuleId
```

## 必须实现

- `FrozenJsonValue`；
-`OperationReference`；
-`NormalizedRule`；
-`NormalizedRuleContent`；
-preconditions；
-唯一 action；
-expected outcomes；
-observations；
-candidate operation mapping；
-ambiguities；
-missing information；
-version_no。

## 实现约束

- `version_no >= 1`；
-原始规则精确保存；
-不包含 model_call_id；
-不包含 confidence/score；
-operation 绑定精确 OpenAPI snapshot；
-operation 权威身份 path + method；
-Frozen JSON 普通 JSON 输入输出；
-内部深层不可变；
-拒绝 bytes/datetime/Decimal 泄漏/NaN/Infinity/循环；
-observation 字段组合严格；
-action 只能一个；
-不检查 operation 是否存在。

## 先写的失败测试

-Frozen scalar/list/object；
-输入 dict 后续修改不影响模型；
-model dump 后修改 dump 不影响模型；
-非法 JSON 值；
-NormalizedRule valid；
-version 0；
-empty original rule；
-multiple action 结构不可能；
-STATUS_CODE observation；
-HEADER observation；
-JSON_BODY observation；
-字段组合错误；
-candidate operation roles；
-no confidence；
-extra field；
-JSON round trip；
-no model/HTTPX/SQLAlchemy imports。

## 非目标

- 模型调用；
-Prompt；
-规则正确性判断；
-issue blocking；
-计划生成；
-持久化；
-model call record。

## 验收标准

- 有效规则 Fixture 严格构造；
-深层不可变；
-JSON 往返；
-共享 ID 仍保持名义类型边界；
-planning 无反向依赖；
-专项和全量质量门通过。

## 专项验证

```bash
uv run pytest \
  tests/unit/planning/test_primitives.py \
  tests/unit/planning/test_normalized_rule.py \
  tests/unit/shared/test_ids.py \
  -q
```

## 推荐提交

```text
feat: add normalized rule contracts
```

## 评审重点

- 是否把模型置信度放入契约；
-是否把规则当权威事实；
-是否加入真实模型依赖；
-是否错误新增持久化字段。

---

# 11. 任务卡 M3-09：ValidationPlanSnapshot 数据契约

## 背景

规则契约完成后，需要定义候选验证计划的完整结构。该结构应足以让 M4 校验和 M5 执行，但本任务不赋予执行资格。

## 目标

实现完整、不可变、最多三步的 `ValidationPlanSnapshot` 数据契约。

## 范围

创建：

```text
src/apiguard/planning/value_sources.py
src/apiguard/planning/conditions.py
src/apiguard/planning/plans.py
tests/unit/planning/test_value_sources.py
tests/unit/planning/test_conditions.py
tests/unit/planning/test_plan_models.py
```

## 必须实现

-计划身份/version/snapshot 绑定；
-objective；
-environment；
-task input；
-1–3 个顺序步骤；
-request parameter binding；
-JSON body template；
-LITERAL/TASK_INPUT/PRIOR_STEP_VARIABLE；
-variable extraction；
-ComparisonTarget；
-所有冻结 ComparisonCondition；
-ExpectedCondition；
-PlanPrecondition；
-final conditions；
-critical evidence；
-side effect；
-canonical content serialization/hash helper（若设计要求独立函数）。

## 实现约束

- 计划内容不包含 stage、validation issues、confirmation、execution、conclusion；
-不包含凭据；
-1–3 steps；
-index 从 1 连续；
-step ID 唯一；
-不提供 branch/loop/parallel；
-普通 parameter binding 可以使用三类 ValueSource；
-JSON body 中 literal scalar 使用 `JsonLiteralNode`；
-固定 object/array 使用专用节点；
-JSON body `JsonValueSourceNode` 只允许 TASK_INPUT 或 PRIOR_STEP_VARIABLE；
-变量 extraction 只支持 scalar；
-source_step_id 必须等于 enclosing step；
-敏感 Header 禁止；
-final_condition_ids 非空；
-M3 不判断引用是否存在；
-M3 不判断 prior step 是否真的在前；
-M3 不判断 retry 是否允许；
-M3 不执行任何 condition。

## 先写的失败测试

### ValueSource

- literal scalar/object/list；
-task input；
-prior step variable；
-unknown kind；
-字段冲突；
-empty names。

### JSON Template

- scalar literal；
-object；
-array；
-nested task input；
-nested prior variable；
-ValueSourceNode literal 拒绝；
-body/content-type 一致；
-template script/extra field 拒绝。

### Extraction

-status code；
-header；
-JSON pointer；
-字段组合；
-source step mismatch；
-sensitive Header；
-object/array type 不存在。

### Conditions

每个 ComparisonKind 至少一个合法测试，并覆盖：

-非法 target 联合；
-status range；
-empty STATUS_CODE_IN；
-JSON type；
-header equals；
-media type normalize flag；
-number operator；
-Schema target；
-expected task input/prior variable。

### Plan

-1、2、3 steps；
-4 steps；
-index 0/跳号/重复；
-重复 step ID；
-task input duplicate；
-condition ID duplicate；
-final conditions empty；
-environment URL；
-side effects；
-critical evidence；
-deep immutability；
-stable JSON round trip；
-content hash stable；
-stage/confirmation/conclusion 字段不存在。

## 非目标

- operation 存在性；
-OpenAPI 参数匹配；
-task input 存在性；
-variable 依赖校验；
-send budget；
-retry policy；
-计划确认资格；
-HTTP；
-比较执行。

## 验收标准

- 三类计划可严格构造；
-所有判别联合严格；
-深层不可变；
-非法结构在 Pydantic 阶段拒绝；
-不发生外部 I/O；
-专项和全量质量门通过。

## 专项验证

```bash
uv run pytest tests/unit/planning -q
```

## 推荐提交

```text
feat: add validation plan data contracts
```

## 评审重点

- 是否偷偷实现 M4 校验；
-是否允许第四步；
-JSON body 是否存在双重字面量表达；
-是否保存认证秘密；
-是否把 stage 放进计划内容。

---

# 12. 任务卡 M3-10：固定 Fixture、Golden 与阶段验收

## 背景

单个组件测试完成后，需要通过固定输入和人工审查的完整输出证明 M3 真正贯通。M3 不以“类存在”或“测试很多”为完成证据。

## 目标

建立两份规范主 Fixture、两份完整 golden、三类计划 Fixture、聚焦异常 Fixture 和十二个阶段验收场景。

## 范围

创建目录：

```text
tests/fixtures/openapi/m3/supported/
tests/fixtures/openapi/m3/invalid/
tests/fixtures/openapi/m3/unsupported/
tests/fixtures/openapi/m3/expected/
tests/fixtures/plans/m3/valid/
tests/fixtures/plans/m3/invalid/
```

创建验收测试：

```text
tests/unit/openapi_context/test_m3_openapi_acceptance.py
tests/unit/planning/test_m3_planning_acceptance.py
```

修改：

```text
pyproject.toml
uv.lock
```

增加开发依赖：

```toml
openapi-spec-validator>=0.9,<0.10
```

## 开发依赖边界

`openapi-spec-validator` 只用于验证两份正常主 Fixture 本身是完整规范合法文档。

禁止：

-生产代码导入；
-校验真实用户文档；
-决定 ApiGuard 错误 code；
-访问 URL；
-解析外部 `$ref`；
-返回第三方对象。

必须添加架构边界测试，扫描 `src/apiguard` 不存在 `openapi_spec_validator` import。

## 主 Fixture

### OpenAPI 3.0 YAML

```text
tests/fixtures/openapi/m3/supported/openapi_30_service.yaml
```

必须包含：

- GET `/v1/items/{item_id}`；
-POST `/v1/orders/{order_id}/cancel`；
-POST `/v1/checkout/orders`；
-POST `/v1/checkout/orders/{order_id}/pay`；
-GET `/v1/checkout/orders/{order_id}`；
-Path/Query/Header；
-参数覆盖；
-JSON request；
-200/201/400/404/409/default；
-vendor +json；
-components；
-security；
-nullable；
-exclusive bounds；
-未选择 required multipart operation。

### OpenAPI 3.1 JSON

```text
tests/fixtures/openapi/m3/supported/openapi_31_service.json
```

必须包含：

- GET `/v1/customers/{customer_id}`；
-POST `/v1/customers/{customer_id}/notes`；
-HEAD `/health`；
-null union；
-numeric exclusive bounds；
-Reference Object description override；
-顶层 webhook；
-未选择 complex oneOf operation。

### Golden

```text
tests/fixtures/openapi/m3/expected/openapi_30_context.json
tests/fixtures/openapi/m3/expected/openapi_31_context.json
```

必须是完整 `model_dump(mode="json")`，包含来源身份、SHA、版本、全部选中 operation、Schema、security、server、reference records 和 diagnostics。

不得在测试运行时自动重写 golden。

## Planning Fixture

有效：

```text
normalized_rule.json
contract_plan.json
business_rule_plan.json
state_flow_plan.json
```

非法至少：

```text
invalid_json_pointer.json
fourth_step.json
duplicate_step_id.json
non_contiguous_step_index.json
invalid_value_source.json
sensitive_header_extraction.json
body_without_content_type.json
unexpected_extra_field.json
```

## OpenAPI 异常 Fixture

非法至少：

```text
duplicate_key.yaml
root_array.json
missing_openapi.yaml
invalid_openapi_version.yaml
missing_paths.yaml
path_parameter_missing.yaml
invalid_response_key.yaml
unresolved_reference.yaml
reference_type_mismatch.yaml
```

不支持至少：

```text
swagger_20.yaml
openapi_32.yaml
required_multipart.yaml
cookie_parameter.yaml
deep_object_parameter.yaml
external_reference.yaml
recursive_schema.yaml
path_item_reference.yaml
complex_composition.yaml
schema_ref_sibling_31.yaml
```

## 十二个验收测试名称

建议精确采用：

```text
test_accepts_local_openapi_30_and_matches_golden
test_accepts_remote_openapi_31_and_matches_golden
test_retries_one_transient_openapi_fetch_failure
test_enforces_exact_openapi_size_limit
test_separates_source_parse_and_openapi_errors
test_records_supported_local_reference_resolution
test_rejects_external_reference_without_network_access
test_rejects_recursive_schema_without_partial_snapshot
test_normalized_rule_round_trips_strictly
test_single_step_plans_match_contract
test_three_step_plan_preserves_variable_sources
test_invalid_planning_fixtures_are_rejected
```

## 断言要求

每个主场景同时具备：

1. 完整 golden 相等；
2.关键字段独立断言；
3.负向不变量断言。

负向不变量包括：

-快照不含 raw document；
-无第三方类型；
-未选 operation 不进入快照；
-外部 `$ref` 网络计数为 0；
-失败不返回部分快照；
-计划无 stage、confirmation、conclusion；
-计划无凭据。

## 动态边界测试

不提交超大文件。测试中生成：

```python
exact_limit = b"x" * 2_097_152
over_limit = b"x" * 2_097_153
```

所有远程来源使用 MockTransport，不访问公网。

## 非目标

- 真实模型；
-真实待测 API；
-SQLite；
-EvaluationResult；
-四态；
-EvidenceBundle；
-产品 API。

## 验收标准

- 两份正常 Fixture 通过完整规范辅助校验；
-两份 golden 精确相等；
-十二个验收场景通过；
-invalid 与 unsupported 分类清晰；
-所有历史测试通过；
-生产代码不导入完整 validator；
-全量质量门通过。

## 专项及完整验证

```bash
uv sync --locked
uv run pytest tests/unit/openapi_context tests/unit/planning -q
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
git diff --check
git status --short
```

## 推荐提交

```text
test: complete milestone 3 acceptance
```

## 评审重点

- Golden 是否由实现自我生成后无审查接受；
-Fixture 是否过度庞大或包含多个失败原因；
-是否依赖公网；
-是否用 validator 替代 ApiGuard builder；
-是否错误声称系统已经生成或执行计划。

---

# 13. 任务卡 M3-11：正式封板 Milestone 3

## 背景

M3-10 通过后，还需要用户本地验收和正式接受。只有真实命令证据齐全后，才能修改 README 并写阶段验收文档。

## 前置条件

- M3-10 已提交；
-用户已在本地运行完整质量门；
-用户已接受 M3；
-无阻断问题；
-工作区干净。

## 目标

把 M3 的真实完成结果、任务提交、测试输出和已知限制保存进仓库。

## 范围

创建：

```text
docs/milestones/milestone-03-acceptance.md
```

修改：

```text
README.md
```

验收文档记录：

- M3-00 至 M3-10 每项 commit；
-最终生产和开发依赖；
-Fixture 清单；
-专项测试数量和结果；
-全量测试数量和结果；
-Ruff；
-format；
-Pyright；
-`git diff --check`；
-已知非阻断限制；
-M4 尚未开始。

## README 可以声明

- 受限本地/远程 OpenAPI 读取已完成；
-OpenAPI 3.0/3.1 最小上下文已完成；
-受限本地 `$ref` 已完成；
-OpenAPIContextSnapshot 已完成；
-NormalizedRule 和 ValidationPlanSnapshot 契约已完成；
-Fixture 和确定性测试已完成。

## README 不得声明

- 自动生成计划；
-计划校验；
-真实 API 执行；
-缺陷发现；
-EvidenceBundle；
-Agent 闭环。

## 非目标

- 不修改业务实现；
-不在封板任务修复代码问题；
-不创建 M4 模块；
-不增加新依赖。

发现代码问题时停止封板，回到对应任务修复并重新验收。

## 验收命令

```bash
uv sync --locked
uv run pytest tests/unit/openapi_context tests/unit/planning -q
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
git diff --check
git status --short
```

## 推荐提交

```text
docs: formally seal milestone 3
```

## 评审重点

- 文档中的数字是否来自真实命令；
-是否夸大当前能力；
-是否把非阻断 warning 错当完成失败或依赖升级理由；
-封板后工作区是否干净。

---

# 14. 阶段评审点

## 14.1 评审点 A：来源与解析

完成：

```text
M3-01
M3-02
M3-03
```

评审：

-来源和解析是否分层；
-预算是否真实；
-敏感信息是否脱敏；
-重复键是否拒绝；
-第三方异常是否隔离；
-是否发生公网访问。

未通过不得进入 M3-04。

## 14.2 评审点 B：OpenAPI 上下文

完成：

```text
M3-04
M3-05
M3-06
M3-07
```

评审：

-契约是否稳定且深层不可变；
-是否只处理选中依赖闭包；
-引用是否零外部 I/O；
-Schema 是否错误降级；
-3.0/3.1 是否统一；
-快照是否原子和确定；
-第三方对象是否泄漏。

未通过不得进入 planning。

## 14.3 评审点 C：规划契约

完成：

```text
M3-08
M3-09
```

评审：

-规则是否仍是候选语义；
-计划是否没有执行资格；
-ValueSource 是否只有三类；
-JsonPointer 是否唯一；
-是否保存凭据；
-是否提前实现 M4/M5；
-计划内容是否不含 stage/confirmation/conclusion。

## 14.4 评审点 D：M3 最终验收

完成：

```text
M3-10
```

评审：

-主 Fixture 是否规范合法；
-golden 是否人工审查；
-错误分类是否稳定；
-全部历史测试是否通过；
-是否发生范围扩张；
-外部评审者是否能独立运行验收。

用户接受后才执行 M3-11。

---

# 15. M3 最终完成定义

M3 只有同时满足以下条件才可封板：

## 来源与解析

- LOCAL_FILE；
-REMOTE_HTTP；
-10 秒 timeout；
-最多一次 retry；
-2 MiB 精确边界；
-UTF-8；
-JSON/YAML；
-重复键拒绝；
-错误分层。

## OpenAPI 上下文

- OpenAPI 3.0；
-OpenAPI 3.1；
-operation 明确选择；
-参数覆盖；
-JSON request/response；
-Schema 子集；
-security；
-server 非权威；
-本地 `$ref`；
-外部 `$ref` 零网络拒绝；
-递归 Schema 拒绝；
-完整 golden。

## Planning

- NormalizedRule；
-契约计划；
-业务规则计划；
-三步状态流；
-RFC 6901；
-三类 ValueSource；
-变量提取；
-ComparisonCondition 数据结构；
-深层不可变；
-非法输入拒绝。

## 范围证明

- 不调用真实模型；
-不校验计划业务合法性；
-不执行待测 API；
-不产生 EvaluationResult；
-不产生四态；
-不产生 EvidenceBundle；
-不新增产品 API；
-不新增数据库业务接口。

达到后必须停止，下一阶段进入 M4：

```text
候选计划确定性校验
+
确定性比较器
+
EvaluationResult
+
四态决策
```
