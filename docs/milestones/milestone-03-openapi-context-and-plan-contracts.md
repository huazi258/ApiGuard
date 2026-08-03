# ApiGuard V0｜里程碑 3 OpenAPI 上下文与计划数据契约

> 文档状态：Milestone 3 开发前冻结基线
> 适用仓库：`huazi258/ApiGuard`
> 开发基线：`main` / `5a4f7a5c324cac4b7988548d53fb77cc2a699da7`
> 上位基线：
> 1. `docs/baselines/00-v0-scope.md`
> 2. `docs/baselines/01-v0-architecture.md`
> 3. `docs/baselines/02-v0-technical-design-and-development.md`
>
> 本文档冻结 ApiGuard V0 Milestone 3 的问题、范围、数据边界、支持子集、错误分类、规划契约、Fixture 和验收方式。实现不得以第三方库能力、作品展示或后续里程碑需求为理由扩大本阶段范围。

---

# 0. 里程碑定位

## 0.1 M3 在完整产品流程中的位置

ApiGuard V0 的完整流程为：

```text
输入检查
→ 业务规则规范化
→ 生成结构化验证计划
→ 用户确认
→ 真实 HTTP 执行
→ 确定性比较
→ 四态结论
→ 证据报告
→ 重复验证
```

M3 只建立前半段所依赖的可信数据边界：

```text
OpenAPI 来源
→ 来源读取
→ 文档解码与解析
→ 选中 operation 的最小上下文
→ OpenAPIContextSnapshot

固定规则/计划 Fixture
→ NormalizedRule
→ ValidationPlanSnapshot
```

M3 到此停止，不进入：

```text
真实模型调用
计划生成
计划确定性校验
用户确认
待测 API HTTP 执行
变量求值
响应比较
EvaluationResult
四态结论
EvidenceBundle
报告与页面
启动恢复
```

## 0.2 M3 解决的问题

M3 解决四类不确定性：

1. **来源不确定性**：OpenAPI 从哪里读取，如何限制超时、大小、重试和敏感信息展示。
2. **文档不确定性**：原始字节、文本、JSON/YAML 数据树和领域快照如何分层。
3. **规范不确定性**：OpenAPI 3.0/3.1 中哪些 operation、参数、请求体、响应和 Schema 特性属于 V0。
4. **跨模块契约不确定性**：模型、计划校验、执行、比较和持久化未来使用什么稳定数据结构。

M3 的目标不是“完整支持 OpenAPI”，而是：

> 将受限、可追溯的 OpenAPI 输入确定性投影为不可变领域快照，并冻结规则与计划的结构化语言。

## 0.3 M3 输入

M3 的正式输入包括：

- 一个受支持的 OpenAPI 来源描述；
- 固定读取预算：10 秒、2 MiB、最多两次远程尝试；
- 明确的 operation 选择范围；
- 固定的规则与计划 Fixture；
- 调用方提供的领域标识。

M3 不接收：

- 真实模型输出；
- Prompt；
- 认证凭据；
- 待测接口真实响应；
- ORM Row 或 SQLAlchemy Session；
- 用户确认记录；
- EvidenceBundle；
- 四态结论。

## 0.4 M3 输出

M3 成功输出：

- `OpenAPISourceReadResult`；
- 内部 `DecodedOpenAPIDocument`；
- 内部 `ParsedOpenAPIDocument`；
- 不可变 `OpenAPIContextSnapshot`；
- 不可变 `NormalizedRule`；
- 不可变 `ValidationPlanSnapshot`；
- `JsonPointer`；
- 计划值来源、变量提取和比较条件数据契约；
- 稳定错误和诊断。

必须明确：

```text
Pydantic 构造成功
≠ 计划业务合法
≠ 用户已确认
≠ 可以执行
```

## 0.5 M3 完成定义

M3 只有在以下两条证明链均成立时完成：

```text
固定 OpenAPI Fixture
→ 预算内读取
→ 严格解析
→ 受限引用解析
→ 选中 operation 投影
→ 不可变 OpenAPIContextSnapshot
→ 与人工审查 golden 完全相等
```

```text
固定规则/计划 JSON
→ 严格 Pydantic 构造
→ 深层不可变
→ 稳定 JSON 往返
→ 非法输入确定性拒绝
```

---

# 1. 范围与非目标

## 1.1 M3 必做范围

M3 必须完成：

1. OpenAPI 来源描述与读取端口；
2. 本地文件来源；
3. 远程 HTTP/HTTPS 来源；
4. 10 秒远程读取预算；
5. 2 MiB 文档硬上限；
6. 最多一次临时网络重试；
7. UTF-8 和 UTF-8 BOM；
8. 严格 JSON 与安全 YAML；
9. 重复键和非 JSON 值拒绝；
10. OpenAPI 3.0.x 与 3.1.x 版本识别；
11. 明确选中 operation 的最小上下文；
12. 受限文档内 `$ref`；
13. 不可变 `OpenAPIContextSnapshot`；
14. 不可变 `NormalizedRule`；
15. 不可变 `ValidationPlanSnapshot`；
16. RFC 6901 `JsonPointer`；
17. 三类计划值来源；
18. 变量提取与比较条件数据结构；
19. 固定 Fixture、golden 和确定性单元测试。

## 1.2 明确非目标

M3 不实现：

- 模型供应商 SDK；
- Prompt；
- 真实规则规范化；
- 真实计划生成；
- 模型重试与格式修复流程；
- 计划确定性校验；
- 用户确认；
- 目标 HTTP 客户端；
- 真实请求构造和发送；
- 运行时变量提取；
- 响应比较器；
- OpenAPI Schema 实例校验；
- `EvaluationResult`；
- 四态决策；
- `EvidenceBundle`；
- `DerivedReport`；
- 产品 API；
- Jinja2 页面；
- 新数据库迁移；
- 新 Repository 或 Unit of Work 接口；
- 任务准备用例；
- 启动恢复；
- 完整 OpenAPI lint 平台；
- Swagger 2.0；
- OpenAPI 3.2；
- 完整 JSON Schema 2020-12；
- Webhook、Callback、SSE、WebSocket；
- multipart、表单、XML、文件上传下载验证；
- RAG、多 Agent、工作流引擎或动态重规划。

## 1.3 与后续里程碑的交界

| 能力 | M3 | 后续里程碑 |
|---|---|---|
| OpenAPI 来源和解析 | 定义并实现 | M6 准备用例调用 |
| OpenAPIContextSnapshot | 定义并构造 | M4–M10 消费与持久化 |
| NormalizedRule | 定义契约 | M6 由模型产生 |
| ValidationPlanSnapshot | 定义契约 | M4 校验，M6 生成 |
| JSON Pointer | 语法和值对象 | M4/M5 求值与比较 |
| ValueSource | 定义三类来源 | M4 校验，M5 求值 |
| ComparisonCondition | 定义结构 | M4 实现比较器 |
| HTTP 执行 | 不负责 | M5 |
| 产品闭环 | 不负责 | M6–M10 |

## 1.4 防越界检查

每次 M3 评审必须检查：

- 是否出现模型 SDK、Prompt 或真实模型调用；
- 是否出现待测业务 HTTP 请求；
- 是否判断计划“可以执行”；
- 是否创建 `EvaluationResult` 或四态结论；
- 是否修改 M2 数据库设计；
- 是否把第三方 OpenAPI 对象暴露给 planning；
- 是否为支持所有规范字段扩大快照；
- 是否依赖公网；
- 是否在 README 中夸大当前能力。

---

# 2. OpenAPI 来源与读取边界

## 2.1 支持的来源

```text
OpenAPISourceKind
- LOCAL_FILE
- REMOTE_HTTP
```

`REMOTE_HTTP` 允许：

```text
http
https
```

保留 `http` 是为了本地和测试环境。

测试中的 `FakeOpenAPISource` 或 `InMemoryOpenAPISource` 只是测试替身，不属于产品来源枚举，不保存到正式任务或快照。

## 2.2 不支持的来源

M3 不支持：

- 内联 OpenAPI 文本；
- stdin；
-上传文件对象；
-数据库 Blob；
-GitHub/Drive/对象存储专用来源；
-自动发现 `/openapi.json`；
-Swagger UI 页面抓取；
-FTP/SFTP/WebSocket；
-`file://`、`data:` 或自定义 scheme；
-需要登录、Cookie、OAuth 或动态签名的来源。

## 2.3 `OpenAPISourceDescriptor`

```text
OpenAPISourceDescriptor
- kind
- location
```

Descriptor 只做结构校验，不访问文件系统。

它拒绝：

- 空值；
-空白 location；
-路径或 URL 中的空字节；
-不支持的 URL scheme；
-缺少 host；
-URL 用户名或密码；
-URL fragment。

文件是否存在、是否为普通文件、权限和大小由本地适配器判断。

## 2.4 认证边界

远程 OpenAPI 来源不支持：

- `Authorization`；
-Cookie；
-API Key Header；
-Client Certificate；
-OAuth Token；
-自定义签名。

不得把 Token 或密码放进 URL。URL 中所有查询参数值在展示时统一脱敏。

## 2.5 冻结预算

```text
OPENAPI_FETCH_TIMEOUT_SECONDS = 10
MAX_OPENAPI_FETCH_ATTEMPTS = 2
MAX_OPENAPI_DOCUMENT_BYTES = 2 * 1024 * 1024
```

即：

- 单次远程尝试总预算 10 秒；
- 首次尝试 + 最多一次临时重试；
- 正好 2,097,152 bytes 允许；
- 2,097,153 bytes 拒绝。

## 2.6 `OpenAPISourceReadResult`

成功结果最小字段：

```text
OpenAPISourceReadResult
- source_kind
- source_display_value
- raw_document
- size_bytes
- content_sha256
- declared_content_type
- attempts
- diagnostics
```

不变量：

- `raw_document` 非空；
- `size_bytes == len(raw_document)`；
- `size_bytes <= 2 MiB`；
- SHA-256 依据原始字节；
-最后一次 attempt 为 `SUCCEEDED`；
-不得包含 HTTPX Response、文件句柄或解析对象。

## 2.7 来源展示值

本地来源：

- 保留调用方提供的可读路径；
-不自动绝对路径化；
-不泄露机器用户名和目录。

远程来源：

- 保留 scheme、host、port、path；
-所有 query value 统一显示为 `***`；
-不包含用户信息和 fragment。

## 2.8 `OpenAPISourceReadAttempt`

```text
OpenAPISourceReadAttempt
- attempt_no
- outcome
- elapsed_ms
- bytes_received
- error_code
```

```text
OpenAPISourceAttemptOutcome
- SUCCEEDED
- FAILED_RETRYABLE
- FAILED_FINAL
```

失败尝试的部分正文不得进入最终文档。

## 2.9 本地读取规则

本地来源必须：

1. 确认路径存在；
2. 确认是普通文件；
3. 预检查可用文件大小；
4. 受限读取；
5. 防止检查后文件增长突破上限。

本地来源不自动重试。

## 2.10 远程 HTTP 策略

- 只使用同步 `GET`；
-不先发 `HEAD`；
-不自动跟随重定向；
-只有 2xx 可以进入正文读取；
-204 或空正文直接报来源为空；
-Content-Type 只保存，不决定合法性；
-正文流式读取；
-大小上限针对解压后准备保存和解析的字节。

重定向：

```text
301/302/303/307/308
→ OPENAPI_REDIRECT_NOT_ALLOWED
```

## 2.11 自动重试

只对远程来源的以下临时问题重试一次：

-连接/读取超时；
-临时 DNS 或连接失败；
-连接重置或正文中断；
-502、503、504。

不重试：

-格式或位置错误；
-401/403；
-404/410；
-429；
-500；
-TLS 证书验证失败；
-重定向；
-空正文；
-文档超限；
-本地文件错误。

不实现指数退避、抖动、Range Resume 或 `Retry-After` 调度。

## 2.12 来源错误代码

```text
UNSUPPORTED_OPENAPI_SOURCE
INVALID_OPENAPI_SOURCE_LOCATION
OPENAPI_SOURCE_NOT_FOUND
OPENAPI_SOURCE_ACCESS_DENIED
OPENAPI_SOURCE_EMPTY
OPENAPI_FETCH_TIMEOUT
OPENAPI_SOURCE_UNAVAILABLE
OPENAPI_SOURCE_HTTP_ERROR
OPENAPI_REDIRECT_NOT_ALLOWED
OPENAPI_DOCUMENT_TOO_LARGE
OPENAPI_SOURCE_READ_FAILED
```

错误必须包含稳定 `code`、来源种类、安全展示值、是否可重试、attempts 和安全详情。第三方异常只能作为异常链，不能成为调用方判断依据。

## 2.13 来源层与解析层的边界

以下属于来源失败：

-文件不存在；
-HTTP 404；
-超时；
-连接失败；
-超 2 MiB；
-空文件；
-HTTP 403。

以下属于来源读取成功，之后由解析层处理：

-HTTP 200 HTML；
-普通文本；
-JSON/YAML 语法错误；
-缺少 `openapi`；
-Swagger 2.0；
-无法解析的 `$ref`。

---

# 3. 原始文档、解析结果与快照边界

## 3.1 四层对象

```text
OpenAPISourceReadResult
原始字节与来源事实
        ↓
DecodedOpenAPIDocument
严格 UTF-8 文本
        ↓
ParsedOpenAPIDocument
无重复键、JSON 兼容普通数据树
        ↓
OpenAPIContextSnapshot
ApiGuard 使用的不可变领域事实
```

## 3.2 原始字节

原始字节回答“实际输入是什么”。

- SHA-256 必须直接依据原始字节；
-不得在移除 BOM、换行规范化或 JSON 格式化后重算原始摘要；
-不得把 YAML 转换后的 JSON 冒充原始文档；
-不得写入普通日志；
-planning、execution、evaluation 不得直接读取原始字节。

## 3.3 文本解码

M3 只支持：

```text
UTF-8
UTF-8 with BOM
```

不支持 UTF-16、UTF-32、GBK、Big5、ISO-8859 或自动猜测。

HTTP 声明非 UTF-8 charset 时拒绝，不自动转换。

内部对象：

```text
DecodedOpenAPIDocument
- text
- encoding
- had_utf8_bom
```

解码错误：

```text
OPENAPI_DOCUMENT_ENCODING_UNSUPPORTED
OPENAPI_DOCUMENT_TEXT_INVALID
```

## 3.4 JSON/YAML 解析策略

固定顺序：

```text
先严格 JSON
JSON 失败后安全 YAML
```

JSON 要求：

- 拒绝重复键；
-拒绝 NaN/Infinity；
-根必须为对象。

YAML 要求：

- 只使用 SafeLoader；
-拒绝重复键；
-拒绝非字符串 key；
-拒绝日期、bytes、自定义对象和循环 alias 等非 JSON 值；
-最终转换为普通 JSON 兼容树。

## 3.5 `ParsedOpenAPIDocument`

内部结构：

```text
ParsedOpenAPIDocument
- document_format
- root
- declared_openapi_version
- diagnostics
```

`root` 必须是字符串 key 的 JSON 兼容 mapping。

该对象：

- 只在 `openapi_context` 内使用；
-不持久化；
-不提供给 planning；
-不进入产品 API；
-Context Builder 是唯一正常消费者。

## 3.6 文档解析错误

```text
OPENAPI_DOCUMENT_ENCODING_UNSUPPORTED
OPENAPI_DOCUMENT_TEXT_INVALID
OPENAPI_DOCUMENT_SYNTAX_INVALID
OPENAPI_DOCUMENT_DUPLICATE_KEY
OPENAPI_DOCUMENT_ROOT_NOT_OBJECT
OPENAPI_DOCUMENT_VALUE_UNSUPPORTED
```

解析成功只证明“获得无歧义数据树”，不证明是合法 OpenAPI。

## 3.7 `OpenAPIContextSnapshot`

业务含义：

> 针对一个明确 operation 范围，从某一份固定 OpenAPI 原始文档中提取、规范化并冻结的最小接口事实。

顶层类别：

```text
OpenAPIContextSnapshot
- openapi_snapshot_id
- source
- raw_document_identity
- document_format
- openapi_version
- document_metadata
- operation_scope
- operations
- reference_resolutions
- diagnostics
```

快照不包含：

- `raw_document`；
-完整文本；
-解析 root；
-第三方 OpenAPI 对象；
-HTTPX 类型；
-SQLAlchemy 类型。

## 3.8 快照权威性

- 原始文档回答“输入是什么”；
-解析树回答“语法树是什么”；
-快照回答“ApiGuard 实际使用了什么接口事实”。

后续模块只能使用快照，不得绕过快照重新解释原始文档。

快照投影发现缺陷时：

-修复 Context Builder；
-创建新快照；
-不得修改历史快照；
-历史计划和尝试仍绑定旧快照。

## 3.9 构建范围和原子性

Context Builder 只严格检查：

```text
文档最低顶层结构
+
选中 operation
+
选中 operation 的依赖闭包
```

未选 operation 的不支持结构不阻止当前快照。

如果选中多个 operation：

-全部成功才返回；
-任一失败则整个调用失败；
-不返回部分快照；
-不静默删除失败 operation。

## 3.10 不可变性和确定性

所有公开 Pydantic 模型必须：

```text
frozen = true
extra = forbid
```

集合使用 tuple 或等价深层不可变表示。

相同原始字节、相同 operation 选择、相同构建器版本和相同调用方 ID，必须产生相同业务字段。

不得依赖：

-当前时间；
-随机 ID；
-dict 偶然顺序；
-Python 对象地址；
-文件绝对路径；
-第三方异常文本。

---

# 4. OpenAPI 3.0/3.1 最小支持范围

## 4.1 版本

支持：

```text
OpenAPI 3.0.x
OpenAPI 3.1.x
```

不支持：

```text
Swagger 2.0
OpenAPI 3.2
```

领域表示：

```text
OpenAPIVersion
- family
- exact_version

OpenAPIVersionFamily
- OPENAPI_3_0
- OPENAPI_3_1
```

版本字符串必须为三个数字段，例如 `3.0.3`、`3.1.0`。

版本错误：

```text
OPENAPI_VERSION_MISSING
OPENAPI_VERSION_INVALID
OPENAPI_VERSION_UNSUPPORTED
```

## 4.2 文档最低顶层结构

必须存在：

```text
openapi
info
paths
```

`info` 至少包含非空字符串：

```text
title
version
```

快照可保留：

```text
OpenAPIDocumentMetadata
- title
- api_version
```

错误：

```text
OPENAPI_INFO_INVALID
OPENAPI_PATHS_INVALID
```

## 4.3 支持的 HTTP 方法

复用共享 `HttpMethod`：

```text
GET
HEAD
POST
PUT
PATCH
DELETE
```

不支持 OPTIONS、TRACE、CONNECT。

operation 权威身份为：

```text
path + method
```

`operationId` 只是附加信息，不是唯一定位方式。

## 4.4 `servers`

`servers` 只作为非权威候选元数据。

- 优先级：operation → path → document；
-只保留实际生效层级；
-不自动选择环境；
-不覆盖用户 target base URL；
-不展开成实际请求地址；
-没有显式 server 时 `server_candidates = ()`，不合成 `/`。

## 4.5 `security`

保留：

- 文档级 requirements；
-operation 级覆盖；
-空 security 覆盖；
-scheme 名称和最小类型。

可识别：

```text
apiKey
http
oauth2
openIdConnect
mutualTLS
```

M3 不获取凭据、执行登录或选择认证 alternative。

## 4.6 参数范围

支持位置：

```text
PATH
QUERY
HEADER
```

不支持 Cookie 参数。

参数只支持基础标量：

```text
STRING
INTEGER
NUMBER
BOOLEAN
```

不支持 object、array、nullable 参数、参数 `content`、deepObject、matrix、label、pipeDelimited、spaceDelimited。

只支持默认序列化：

| 位置 | style | explode |
|---|---|---:|
| PATH | simple | false |
| QUERY | form | true |
| HEADER | simple | false |

Query `allowReserved=true` 不支持。

## 4.7 请求体范围

只支持 JSON：

```text
application/json
application/*+json
具体 application/*+json vendor 类型
```

不支持 multipart、form-urlencoded、XML、text、binary 和文件。

必需请求体如果没有受支持 JSON media type，operation 构建失败。

可选请求体如果只有不支持 media type，可以忽略并记录诊断。

## 4.8 响应范围

响应键支持：

```text
100–599 的三位精确状态码
default（只接受精确小写）
```

不接受 `2XX`、`4XX`、`DEFAULT`、`Default`。

响应可以：

- 无正文；
-只有非 JSON 内容；
-声明多个状态；
-声明 default。

非 JSON 响应仍保留状态码契约，但不能产生 JSON Schema 条件。

## 4.9 Schema 最小范围

基础类型：

```text
ANY
OBJECT
ARRAY
STRING
INTEGER
NUMBER
BOOLEAN
NULL
```

支持关键词：

- `type`；
-`properties`；
-`required`；
-`items`；
-`enum`；
-`format`；
-`description`；
-`default`；
-`minimum`、`maximum`；
-`exclusiveMinimum`、`exclusiveMaximum`；
-`minLength`、`maxLength`；
-`minItems`、`maxItems`；
-OpenAPI 3.0 `nullable`；
-readOnly/writeOnly；
-additionalProperties 的缺失/true/false。

不支持：

-复杂 oneOf/anyOf/allOf；
-通用多态；
-discriminator；
-not；
-if/then/else；
-dependentSchemas；
-unevaluatedProperties；
-动态引用；
-additionalProperties 为 Schema；
-完整 JSON Schema 方言平台。

唯一允许的 union 是：

```text
一个支持基础类型 + null
```

## 4.10 `SchemaKind.ANY`

`ANY` 表示根值没有明确基础类型约束，不表示验证已经通过。

当 Schema 没有 `type`，但有 `properties` 或 `items` 时：

- 不强制推断 OBJECT/ARRAY；
-`kind = ANY`；
-允许保留 conditional object/array constraints。

例如只有 `properties` 时，其含义是：根值未被要求必须是 object，但当值为 object 时保留观察到的属性约束。

## 4.11 required 与 nullable

必须严格区分：

- `required`：字段是否必须存在；
-`nullable`：字段存在时是否允许 null。

OpenAPI 3.0：

```yaml
type: string
nullable: true
```

OpenAPI 3.1：

```yaml
type: [string, "null"]
```

统一表示为：

```text
kind = STRING
nullable = true
```

---

# 5. Operation 最小上下文数据契约

## 5.1 对象层次

```text
OpenAPIContextSnapshot
└── operations: tuple[OperationContext, ...]
    ├── key
    ├── parameters
    ├── request_body
    ├── responses
    ├── effective_security
    ├── server_candidates
    └── diagnostics
```

## 5.2 `OperationKey`

```text
OperationKey
- path
- method
```

路径：

- 必须以 `/` 开头；
-保留原始大小写和尾部 `/`；
-不包含 scheme、host、query。

## 5.3 `OperationContext`

```text
OperationContext
- key
- source_pointer
- operation_id
- summary
- description
- parameters
- request_body
- responses
- effective_security
- server_candidates
- diagnostics
```

不包含环境、测试数据、计划步骤、认证凭据、实际 URL、结论或执行状态。

## 5.4 参数契约

```text
ParameterContext
- name
- location
- required
- description
- deprecated
- serialization
- schema
- suggested_value
- source_pointer
- declared_scope
```

```text
ParameterDeclaredScope
- PATH_ITEM
- OPERATION
```

参数身份：

- Path/Query 名称大小写敏感；
-Header 名称大小写不敏感。

Path 参数不变量：

- 每个 `{name}` 必须有且只有一个 Path 参数；
-Path 参数必须 `required=true`；
-参数名称与占位符大小写一致；
-不能有额外 Path 参数。

Path Item 与 operation 参数合并：

1. 读取 Path Item 参数；
2.读取 operation 参数；
3.以 `(location, normalized_name)` 为身份；
4.operation 完整覆盖同身份 Path Item 参数；
5.同层重复身份拒绝。

保留 Header 名称：

```text
Accept
Content-Type
Authorization
```

不得作为普通 Header 参数进入最终参数集合。

## 5.5 非权威建议值

单一 `example` 或 `default` 可映射为：

```text
SuggestedValueContext
- kind
- value
- source_pointer
- authoritative = false
```

它不是实际测试数据，不直接成为计划字面量，也不能绕过用户确认。

## 5.6 Media Type

```text
MediaTypeContext
- declared_value
- normalized_value
- match_kind
```

```text
JsonMediaTypeMatchKind
- EXACT_JSON
- STRUCTURED_JSON_SUFFIX
- STRUCTURED_JSON_SUFFIX_WILDCARD
```

规范化：

- type/subtype 小写；
-去除参数；
-保留原始声明；
-规范化后重复必须拒绝。

## 5.7 JSON 内容

```text
JsonContentContext
- media_type
- schema
- suggested_value
- source_pointer
```

`schema` 允许为空，表示文档声明 JSON media type，但没有可用于结构验证的 Schema。不得根据 example 猜测 Schema。

## 5.8 请求体

```text
RequestBodyContext
- required
- description
- json_content
- ignored_content_types
- source_pointer
```

无 requestBody：`None`。

必需请求体没有支持的 JSON media type：阻断。

多个 JSON media type 全部保留，M3 不自动选择。

## 5.9 响应选择器

```text
ResponseSelector
- ExactStatusCode
- DefaultResponse
```

`DefaultResponse` 不使用特殊整数代替。

排序：精确状态码升序，default 最后。

## 5.10 响应上下文

```text
ResponseContext
- selector
- description
- json_content
- ignored_content_types
- source_pointer
```

operation 必须至少有一个 response。

无正文响应合法。

只有 PDF/XML 等非 JSON 内容的 response 仍保留状态码，并记录 ignored content type。

## 5.11 `SchemaContext`

```text
SchemaContext
- kind
- nullable
- description
- format
- enum_values
- default_value
- example_value
- read_only
- write_only
- string_constraints
- numeric_constraints
- array_constraints
- object_constraints
- source_pointer
```

对象约束：

```text
ObjectConstraints
- properties
- required_properties
- additional_properties
```

```text
AdditionalPropertiesPolicy
- UNSPECIFIED
- ALLOWED
- FORBIDDEN
```

数组约束：

```text
ArrayConstraints
- items
- min_items
- max_items
```

明确 ARRAY 时必须有 items。

数值约束统一为：

```text
NumericBound
- value
- inclusive
```

OpenAPI 3.0/3.1 的 exclusive 语义在投影层统一。

readOnly 和 writeOnly 不得同时为 true。

## 5.12 Security

```text
EffectiveSecurityContext
- authentication_required
- alternatives
```

同一 alternative 内为 AND，alternative 之间为 OR。

M3 只保存声明，不选择方案、不保存凭据。

## 5.13 Server Candidate

```text
ServerCandidateContext
- url_template
- description
- variables
- authoritative_for_execution = false
```

实际环境始终来自用户输入。

## 5.14 Source Pointer

主要上下文对象保留 RFC 6901 pointer：

- operation；
-parameter；
-requestBody；
-response；
-media type；
-Schema。

用途：诊断、证据追溯、测试和后续 Schema 条件绑定。

## 5.15 稳定排序

- Operation：path → 固定 method 顺序；
-Parameter：PATH → QUERY → HEADER → normalized name；
-Content-Type：normalized media type；
-Response：状态码升序 → default；
-Property：名称；
-required：去重后名称排序；
-diagnostic：source pointer → severity → code。

---

# 6. `$ref`、非法文档与不支持结构

## 6.1 总体策略

只支持：

> 当前文档内、基于 RFC 6901 JSON Pointer fragment、指向明确具名 component 的引用。

支持形式：

```text
#/components/schemas/Order
#/components/parameters/OrderId
#/components/requestBodies/CreateOrder
#/components/responses/NotFound
#/components/securitySchemes/ApiKeyAuth
```

不支持：

- 外部 URL；
-相对文件；
-`file://`；
-anchor；
-`$id` rebase；
-`$dynamicRef`；
-任意嵌套 pointer；
-Path Item `$ref`；
-递归 Schema。

## 6.2 支持目标

```text
ReferenceTargetKind
- SCHEMA
- PARAMETER
- REQUEST_BODY
- RESPONSE
- SECURITY_SCHEME
```

引用位置决定期望目标类型。目标存在但类型不匹配必须失败，不允许根据字段形状猜测。

## 6.3 引用链

- 支持同类型多跳；
-最大深度 32；
-33 跳失败；
-不得跨 component 类型；
-活动解析栈用于循环检测；
-公共子 Schema 重复使用不算循环。

## 6.4 循环

非 Schema 引用循环：

```text
OPENAPI_REFERENCE_CYCLE
INVALID_DOCUMENT
```

递归 Schema：

```text
OPENAPI_SCHEMA_RECURSION_UNSUPPORTED
UNSUPPORTED_FEATURE
```

不得截断、删除递归字段或降级为 `ANY`。

## 6.5 OpenAPI 3.0 sibling

OpenAPI 3.0 Reference Object 中只有 `$ref` 参与语义。

其他 sibling：

- 忽略；
-产生诊断；
-不与目标对象合并。

诊断：

```text
OPENAPI_30_REFERENCE_SIBLING_IGNORED
```

## 6.6 OpenAPI 3.1 Reference Object sibling

支持：

```text
$ref
summary
description
```

离实际使用位置最近的 metadata override 优先。

其他 sibling 只记录 warning，不合并目标字段。

## 6.7 OpenAPI 3.1 Schema `$ref`

Schema `$ref` 与 Reference Object 不同。

V0 只支持纯 Schema `$ref`。如果同级存在其他 Schema keyword：

```text
OPENAPI_SCHEMA_REF_SIBLING_UNSUPPORTED
```

`x-*` 可以忽略并诊断，但不能改变语义。

## 6.8 引用追溯

快照保存：

```text
ReferenceResolutionRecord
- reference_pointer
- original_reference
- canonical_target_pointer
- target_kind
- chain_depth
- openapi_version_family
- metadata_override_applied
```

Context 的 `source_pointer` 指向最终提供结构的具体对象；引用出现位置由 resolution record 保存。

## 6.9 分类

### `INVALID_DOCUMENT`

表示文档无法按自己的声明确定性解释，例如：

- `$ref` 不是字符串；
-URI/Pointer 语法非法；
-目标不存在；
-目标非对象；
-目标类型错误；
-非 Schema 循环；
-必要字段缺失。

### `UNSUPPORTED_FEATURE`

表示结构可能属于规范，但超出 V0，例如：

-外部引用；
-Path Item 引用；
-anchor/dynamicRef；
-超过 32 跳；
-递归 Schema；
-3.1 Schema `$ref` sibling；
-不支持 component 类型。

### `SELECTION_ERROR`

表示调用方选择的 path/method 不存在或 operationId 冲突。

## 6.10 禁止降级

引用或 Schema 失败时禁止：

-把 `$ref` 当普通字符串；
-删除字段；
-换成空对象；
-换成 `ANY`；
-使用 example 代替；
-忽略大小写寻找同名目标；
-跨 collection 搜索；
-调用模型猜测；
-访问远程文档；
-返回部分快照。

---

# 7. 规划数据契约

## 7.1 总体原则

M3 定义候选计划语言，不判断候选计划是否合法。

```text
NormalizedRule
→ 候选规则语义

ValidationPlanSnapshot
→ 完整但尚未获得执行资格的计划内容
```

计划阶段、校验问题和确认记录不进入不可变计划内容。

所有规划公开模型：

```text
Pydantic v2
frozen = true
extra = forbid
strict validation
```

不得包含运行时凭据、ORM、HTTPX 或模型 SDK 类型。

## 7.2 `FrozenJsonValue`

接受普通 JSON：

- null；
-boolean；
-integer；
-finite number；
-string；
-array；
-string-key object。

内部深层冻结，外部仍以普通 JSON 序列化。

拒绝 bytes、datetime、Decimal 泄漏、NaN、Infinity、循环对象和非字符串 key。

## 7.3 `NormalizedRule`

```text
NormalizedRule
- normalized_rule_id
- task_id
- version_no
- openapi_snapshot_id
- original_rule_text
- content
```

`version_no >= 1`。

M3 不包含 `model_call_id`，因为本阶段没有真实模型。M6 持久化时由应用层组合规则与模型调用记录。

## 7.4 `NormalizedRuleContent`

```text
NormalizedRuleContent
- preconditions
- action
- expected_outcomes
- key_observations
- candidate_operations
- ambiguities
- missing_information
```

规则：

- 必须且只能有一个主要 action；
-至少一个候选可观察预期；
-不保存 confidence/probability/score；
-ambiguity 和 missing information 不包含由模型决定的 blocking/can_execute。

Observation 类型：

```text
STATUS_CODE
RESPONSE_HEADER
JSON_BODY
```

Candidate operation role：

```text
PRIMARY_ACTION
PRECONDITION_OBSERVATION
POSTCONDITION_OBSERVATION
```

## 7.5 `OperationReference`

```text
OperationReference
- openapi_snapshot_id
- path
- method
- operation_id
```

权威身份为 path + method。M3 只做结构校验，不检查 operation 是否存在；M4 检查引用一致性。

## 7.6 `ValidationPlanSnapshot`

```text
ValidationPlanSnapshot
- plan_id
- task_id
- version_no
- normalized_rule_id
- openapi_snapshot_id
- content
```

计划阶段不在内容中。

## 7.7 `ValidationPlanContent`

```text
ValidationPlanContent
- objective
- environment
- task_inputs
- steps
- preconditions
- final_condition_ids
- critical_evidence_requirements
- side_effects
```

不包含：

- stage；
-validation issues；
-confirmation；
-execution result；
-conclusion；
-Token/Cookie/API Key。

## 7.8 目标和环境

```text
VerificationObjective
- task_type
- statement
- success_evidence_boundary
- allowed_operations
```

任务类型复用 `VerificationTaskType`。

```text
TargetEnvironmentSnapshot
- base_url
- non_production_confirmed
```

base URL 只允许 HTTP/HTTPS，必须有 host，不得包含用户信息、query 或 fragment。

M3 不判断 URL 真实是否生产环境。

## 7.9 Task Input

```text
TaskInputBinding
- name
- value
```

只保存非凭据测试数据。名称在计划内唯一并稳定排序。

## 7.10 Request Step

```text
RequestStep
- step_id
- step_index
- operation
- request
- variable_extractions
- expected_conditions
- allow_technical_retry
```

结构限制：

```text
1 <= steps <= 3
```

step index 从 1 连续递增，step ID 唯一。

数据结构不包含 branch、loop、parallel、next step 或 fallback。

M3 不判断重试是否符合 GET/HEAD 或三次实际发送预算，M4/M5 决定。

## 7.11 Request Template

```text
RequestTemplate
- path_parameters
- query_parameters
- headers
- content_type
- json_body
```

普通绑定：

```text
RequestValueBinding
- name
- value_source
```

有 JSON body 时 content type 必须存在；无 body 时必须为 `None`。

## 7.12 JSON Body 模板

判别联合：

```text
JsonLiteralNode
JsonValueSourceNode
JsonObjectNode
JsonArrayNode
```

正式避免两种字面量表达：

- `JsonLiteralNode` 只保存 JSON 标量；
-固定 object/array 使用 Object/Array node；
-`JsonValueSourceNode` 只允许 TASK_INPUT 或 PRIOR_STEP_VARIABLE；
-JSON body 中不允许 `JsonValueSourceNode(LITERAL)`。

不支持 Jinja2、模板字符串、JSONPath、脚本、循环或动态展开。

## 7.13 ValueSource

```text
ValueSourceKind
- LITERAL
- TASK_INPUT
- PRIOR_STEP_VARIABLE
```

```text
LiteralValueSource
- kind = LITERAL
- value
```

```text
TaskInputValueSource
- kind = TASK_INPUT
- input_name
```

```text
PriorStepVariableValueSource
- kind = PRIOR_STEP_VARIABLE
- producer_step_id
- variable_name
```

M3 不检查 task input 是否存在或 producer 是否在前序步骤；M4 检查。

不支持环境变量、数据库查询、当前时间、随机数、模型生成值、脚本或历史尝试数据。

## 7.14 变量提取

```text
VariableExtraction
- variable_name
- source_step_id
- source_kind
- header_name
- json_pointer
- value_type
- allow_null
```

来源：

```text
STATUS_CODE
RESPONSE_HEADER
JSON_POINTER
```

变量类型：

```text
STRING
INTEGER
NUMBER
BOOLEAN
```

不支持 object/array 变量。

禁止提取敏感 Header：

```text
Authorization
Proxy-Authorization
Cookie
Set-Cookie
X-API-Key
```

M3 只定义规则，不执行响应解析或保存变量值。

## 7.15 `JsonPointer`

使用 RFC 6901 字符串：

合法：

```text
""
/data/id
/items/0/name
/a~1b
/m~0n
/
```

规则：

- 根是空字符串；
-非根以 `/` 开头；
-`~` 后只能为 `0` 或 `1`；
-不允许 `#` fragment；
-不允许 JSONPath、通配符、过滤器和脚本；
-构造时不要求路径真实存在。

公共 JSON 中序列化为字符串。

## 7.16 比较目标

```text
ComparisonTarget
- StatusCodeTarget
- ResponseHeaderTarget
- JsonBodyTarget
- OpenAPIResponseSchemaTarget
```

Schema target 绑定精确 operation、response selector、media type 和 schema pointer。

M3 不检查这些绑定是否互相一致，M4 检查。

## 7.17 ComparisonCondition

冻结结构：

```text
STATUS_CODE_EQUALS
STATUS_CODE_IN
JSON_PATH_EXISTS
JSON_PATH_NOT_EXISTS
JSON_VALUE_EQUALS
JSON_VALUE_NOT_EQUALS
JSON_VALUE_TYPE
OPENAPI_SCHEMA_VALID
RESPONSE_HEADER_EXISTS
RESPONSE_HEADER_EQUALS
NUMBER_COMPARE
```

数值运算符：

```text
GREATER_THAN
GREATER_THAN_OR_EQUAL
LESS_THAN
LESS_THAN_OR_EQUAL
```

M3 只构造条件，不执行比较。

## 7.18 ExpectedCondition

```text
ExpectedCondition
- condition_id
- description
- source_rule_clause_ids
- role
- required_for_conclusion
- comparison
```

角色：

```text
PRECONDITION_PROOF
STEP_EXPECTATION
FINAL_ASSERTION
```

`required_for_conclusion` 是候选计划声明，不能替代 M4 四态决策表。

## 7.19 前置条件、最终条件和证据要求

```text
PlanPrecondition
- precondition_id
- description
- source_rule_clause_ids
- proof_condition_ids
```

```text
final_condition_ids
```

必须非空，但 M3 不检查引用是否存在。

```text
CriticalEvidenceRequirement
- requirement_id
- description
- required_step_ids
- required_condition_ids
```

M3 不自动映射为 `INCONCLUSIVE`，M4 决定。

## 7.20 副作用

```text
SideEffectNotice
- side_effect_id
- step_id
- kind
- description
```

```text
SideEffectKind
- CREATE_RESOURCE
- MODIFY_RESOURCE
- DELETE_RESOURCE
- EXTERNAL_EFFECT
- UNKNOWN
```

M3 不判断副作用是否真实、可回滚或允许重试。

## 7.21 内容摘要边界

`ValidationPlanContent` 的 canonical JSON 是计划内容摘要输入。

不包含：

- plan ID；
-task ID；
-version；
-stage；
-validation issues；
-confirmation；
-database timestamps。

同理，规则内容摘要以 `NormalizedRuleContent` 为核心，并遵守 M2 已冻结持久化结构。

---

# 8. M3 本地结构校验与 M4 权威校验边界

## 8.1 M3 必须拒绝

- 未知字段；
-空 ID；
-非法枚举；
-非法 JsonPointer；
-无效 URL 基础结构；
-超过三个步骤；
-step index 不连续；
-重复 step ID；
-判别联合字段冲突；
-body/content-type 不一致；
-变量提取字段冲突；
-敏感 Header 提取；
-NaN/Infinity；
-深层可变结构。

## 8.2 M4 才判断

- operation 是否存在于快照；
-步骤是否只用 allowed operation；
-参数是否符合 OpenAPI；
-请求 body 是否符合 Schema；
-content type 是否被声明；
-task input 是否存在且类型兼容；
-prior variable 是否存在且来自前序步骤；
-condition target 是否有效；
-Schema pointer 是否属于对应响应；
-最多三次实际发送；
-技术重试是否允许；
-是否只有一个验证目标；
-前置条件和最终条件是否完整；
-副作用和关键证据是否充分；
-计划能否进入用户确认。

## 8.3 M5 才执行

- ValueSource 求值；
- URL/参数/body 构造；
-认证注入；
-真实 HTTP；
-JsonPointer 求值；
-变量提取；
-Step/Send 记录；
-技术重试。

---

# 9. 固定 Fixture 与验收

## 9.1 目录

```text
tests/
├── fixtures/
│   ├── openapi/m3/
│   │   ├── supported/
│   │   ├── invalid/
│   │   ├── unsupported/
│   │   └── expected/
│   └── plans/m3/
│       ├── valid/
│       └── invalid/
└── unit/
    ├── openapi_context/
    └── planning/
```

## 9.2 主 OpenAPI 3.0 Fixture

文件：

```text
tests/fixtures/openapi/m3/supported/openapi_30_service.yaml
```

必须包含：

- `openapi: 3.0.3`；
-info；
-document server；
-GET `/v1/items/{item_id}`；
-POST `/v1/orders/{order_id}/cancel`；
-POST `/v1/checkout/orders`；
-POST `/v1/checkout/orders/{order_id}/pay`；
-GET `/v1/checkout/orders/{order_id}`；
-path/query/header 参数；
-Path Item 参数被 operation 覆盖；
-JSON 请求体；
-200/201/400/404/409/default；
-vendor `+json`；
-components；
-security scheme；
-3.0 nullable 和 exclusive bound；
-未选择的必需 multipart operation。

## 9.3 主 OpenAPI 3.1 Fixture

文件：

```text
tests/fixtures/openapi/m3/supported/openapi_31_service.json
```

必须包含：

- `openapi: 3.1.0`；
-info；
-jsonSchemaDialect；
-GET `/v1/customers/{customer_id}`；
-POST `/v1/customers/{customer_id}/notes`；
-HEAD `/health`；
-null union；
-3.1 numeric exclusive bound；
-纯 Schema `$ref`；
-Reference Object description override；
-顶层 webhook；
-未选择的 complex oneOf operation。

## 9.4 Golden 快照

```text
tests/fixtures/openapi/m3/expected/openapi_30_context.json
tests/fixtures/openapi/m3/expected/openapi_31_context.json
```

必须保存完整：

- snapshot ID；
-source；
-size 和 SHA-256；
-format；
-version；
-metadata；
-operation scope；
-parameters；
-request body；
-responses；
-SchemaContext；
-security；
-server candidates；
-reference records；
-diagnostics。

验收必须比较完整 `model_dump(mode="json")`，不得仅断言对象非空或 operation 数量。

Golden 不得由当前实现运行时自动生成后直接接受。变更必须人工审查 Diff。

## 9.5 Planning Fixture

有效文件：

```text
normalized_rule.json
contract_plan.json
business_rule_plan.json
state_flow_plan.json
```

覆盖：

-规则前置条件、主要动作和预期；
-单步契约计划；
-单步业务规则计划；
-三步状态流；
-三类 ValueSource；
-变量提取；
-最终条件；
-关键证据；
-副作用。

非法规划文件至少覆盖：

-非法 JsonPointer；
-第四步；
-重复 step ID；
-index 不连续；
-未知 ValueSource；
-敏感 Header；
-body 无 content type；
-extra field。

## 9.6 非法 OpenAPI Fixture

至少覆盖：

- duplicate key；
-root array；
-missing openapi；
-invalid version；
-missing paths；
-missing path parameter；
-invalid response key；
-unresolved reference；
-reference type mismatch。

每个 Fixture 应尽量只有一个主要失败原因，并断言精确错误 code、category 和 source pointer。

## 9.7 不支持 OpenAPI Fixture

至少覆盖：

- Swagger 2.0；
-OpenAPI 3.2；
-required multipart；
-Cookie parameter；
-deepObject；
-external reference；
-recursive Schema；
-Path Item reference；
-complex composition；
-3.1 Schema `$ref` sibling。

必须证明 `INVALID_DOCUMENT` 与 `UNSUPPORTED_FEATURE` 不混淆。

## 9.8 动态边界输入

不提交 2 MiB 大文件，测试中确定性生成：

```text
2,097,152 bytes
2,097,153 bytes
```

远程来源全部使用 HTTPX MockTransport 或等价 transport，不访问公网。

外部 `$ref` 测试必须断言：

```text
network_send_count == 0
```

## 9.9 十二个验收场景

1. 本地 OpenAPI 3.0 与 golden 完全相等；
2.远程 OpenAPI 3.1 与 golden 完全相等；
3.一次临时来源故障后成功；
4. 2 MiB 精确边界；
5.来源、语法、OpenAPI 语义错误分层；
6.本地引用和追溯；
7.外部引用零网络拒绝；
8.递归 Schema 拒绝且无部分快照；
9. NormalizedRule 严格往返；
10.两类单接口计划；
11.三步变量计划；
12.非法规划 Fixture 全部拒绝。

## 9.10 测试断言层次

主验收必须同时有：

1. 完整 golden 相等；
2.关键领域字段独立断言；
3.负向不变量断言。

负向不变量包括：

-快照不含 raw document；
-不含第三方类型；
-计划不含 stage、confirmation、conclusion；
-不含凭据；
-未选 operation 不进入快照；
-外部引用不发网络；
-失败不返回部分快照。

## 9.11 正式验证命令

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

---

# 10. 技术选型

## 10.1 生产路径

M3 采用：

```text
同步 HTTPX
→ 原始 bytes
→ 标准库 JSON / 严格 PyYAML SafeLoader
→ 普通 JSON 兼容树
→ ApiGuard 受限文档内 resolver
→ ApiGuard Schema Projector
→ ApiGuard Context Builder
→ Pydantic v2 快照
```

生产依赖建议：

```toml
pydantic>=2.10,<3
httpx>=0.28,<1
PyYAML>=6.0.3,<7
```

HTTPX 从 dev dependency 移入 production dependency。

Pydantic 作为直接使用的结构化边界，应成为直接生产依赖。

## 10.2 测试辅助

```toml
openapi-spec-validator>=0.9,<0.10
```

只用于验证两份正常主 Fixture 本身是完整合法的 OpenAPI 3.0/3.1 文档。

禁止：

-进入生产代码；
-校验用户真实文档；
-决定 ApiGuard 错误分类；
-访问 URL；
-成为领域模型。

## 10.3 明确不采用

M3 不引入：

- `openapi-core`：其请求/响应校验和框架集成属于后续阶段；
-`openapi-pydantic`：完整第三方对象图不是 ApiGuard 领域模型；
-`jsonschema`：实例校验属于 M4；
-第三方 resolver 自动访问外部 `$ref`。

## 10.4 第三方库边界

任何第三方库：

-只能存在于内部适配器；
-不得进入公开 Pydantic 契约；
-不得决定稳定错误 code；
-不得修改原始读取结果；
-不得让未选 operation 的错误阻止目标 operation；
-不得自动访问外部引用。

---

# 11. 代码组织建议

```text
src/apiguard/
├── shared/
│   ├── enums.py
│   ├── ids.py
│   ├── errors.py
│   └── json_pointer.py
│
├── openapi_context/
│   ├── __init__.py
│   ├── source.py
│   ├── document_parser.py
│   ├── models.py
│   ├── references.py
│   ├── schema_projector.py
│   └── builder.py
│
├── planning/
│   ├── __init__.py
│   ├── primitives.py
│   ├── rules.py
│   ├── value_sources.py
│   ├── conditions.py
│   └── plans.py
│
└── infrastructure/
    └── openapi/
        ├── __init__.py
        ├── local_source.py
        └── http_source.py
```

不得创建无明确职责的：

```text
utils.py
services.py
managers.py
common_models.py
openapi_helpers.py
```

不得提前创建 M4/M5 空模块。

---

# 12. 统一错误分类索引

## 12.1 来源错误

```text
UNSUPPORTED_OPENAPI_SOURCE
INVALID_OPENAPI_SOURCE_LOCATION
OPENAPI_SOURCE_NOT_FOUND
OPENAPI_SOURCE_ACCESS_DENIED
OPENAPI_SOURCE_EMPTY
OPENAPI_FETCH_TIMEOUT
OPENAPI_SOURCE_UNAVAILABLE
OPENAPI_SOURCE_HTTP_ERROR
OPENAPI_REDIRECT_NOT_ALLOWED
OPENAPI_DOCUMENT_TOO_LARGE
OPENAPI_SOURCE_READ_FAILED
```

## 12.2 文档解析错误

```text
OPENAPI_DOCUMENT_ENCODING_UNSUPPORTED
OPENAPI_DOCUMENT_TEXT_INVALID
OPENAPI_DOCUMENT_SYNTAX_INVALID
OPENAPI_DOCUMENT_DUPLICATE_KEY
OPENAPI_DOCUMENT_ROOT_NOT_OBJECT
OPENAPI_DOCUMENT_VALUE_UNSUPPORTED
```

## 12.3 OpenAPI 文档与 operation 错误

```text
OPENAPI_VERSION_MISSING
OPENAPI_VERSION_INVALID
OPENAPI_VERSION_UNSUPPORTED
OPENAPI_INFO_INVALID
OPENAPI_PATHS_INVALID
OPENAPI_OPERATION_NOT_FOUND
OPENAPI_OPERATION_METHOD_UNSUPPORTED
OPENAPI_OPERATION_SELECTION_CONFLICT
OPENAPI_OPERATION_STRUCTURE_INVALID
OPENAPI_REQUIRED_FEATURE_UNSUPPORTED
OPENAPI_SCHEMA_DIALECT_UNSUPPORTED
OPENAPI_MEDIA_TYPE_UNSUPPORTED
OPENAPI_PARAMETER_SERIALIZATION_UNSUPPORTED
```

## 12.4 参数、响应和 Schema 错误

```text
OPENAPI_PARAMETER_DUPLICATE
OPENAPI_PARAMETER_NAME_INVALID
OPENAPI_PATH_PARAMETER_MISSING
OPENAPI_PATH_PARAMETER_EXTRA
OPENAPI_PATH_PARAMETER_REQUIRED
OPENAPI_PARAMETER_SCHEMA_UNSUPPORTED
OPENAPI_REQUIRED_REQUEST_BODY_MEDIA_TYPE_UNSUPPORTED
OPENAPI_MEDIA_TYPE_INVALID
OPENAPI_MEDIA_TYPE_DUPLICATE
OPENAPI_RESPONSES_MISSING
OPENAPI_RESPONSE_KEY_INVALID
OPENAPI_RESPONSE_DUPLICATE
OPENAPI_SCHEMA_STRUCTURE_INVALID
OPENAPI_SCHEMA_TYPE_UNSUPPORTED
OPENAPI_SCHEMA_UNION_UNSUPPORTED
OPENAPI_SCHEMA_COMPOSITION_UNSUPPORTED
OPENAPI_ADDITIONAL_PROPERTIES_SCHEMA_UNSUPPORTED
OPENAPI_ARRAY_ITEMS_MISSING
OPENAPI_SCHEMA_CONSTRAINT_INVALID
OPENAPI_SECURITY_REQUIREMENT_INVALID
```

## 12.5 引用错误

```text
OPENAPI_REFERENCE_VALUE_INVALID
OPENAPI_REFERENCE_URI_INVALID
OPENAPI_REFERENCE_POINTER_INVALID
OPENAPI_REFERENCE_TARGET_NOT_FOUND
OPENAPI_REFERENCE_TARGET_NOT_OBJECT
OPENAPI_REFERENCE_TARGET_TYPE_MISMATCH
OPENAPI_REFERENCE_CYCLE
OPENAPI_EXTERNAL_REFERENCE_UNSUPPORTED
OPENAPI_REFERENCE_TARGET_UNSUPPORTED
OPENAPI_PATH_ITEM_REFERENCE_UNSUPPORTED
OPENAPI_REFERENCE_DEPTH_EXCEEDED
OPENAPI_SCHEMA_RECURSION_UNSUPPORTED
OPENAPI_SCHEMA_REF_SIBLING_UNSUPPORTED
OPENAPI_SCHEMA_REFERENCE_FEATURE_UNSUPPORTED
```

## 12.6 引用诊断

```text
OPENAPI_30_REFERENCE_SIBLING_IGNORED
OPENAPI_REFERENCE_UNKNOWN_SIBLING_IGNORED
OPENAPI_REFERENCE_METADATA_NOT_APPLICABLE
OPENAPI_REFERENCE_EXTENSION_IGNORED
```

错误优先级必须通过聚焦 Fixture 和稳定测试明确，不能依赖第三方库异常文本。

---

# 13. 最终架构不变量

M3 实现必须维护：

1. 来源失败不等于解析失败；
2.解析成功不等于 OpenAPI 有效；
3. OpenAPI 有效不等于被选 operation 受支持；
4.原始文档摘要只依据原始字节；
5.后续模块只使用 `OpenAPIContextSnapshot`；
6.快照不包含原始文档或第三方对象；
7.只严格构建选中 operation 的依赖闭包；
8.任一选中 operation 失败则整个构建失败；
9.不允许外部 `$ref` I/O；
10.不允许递归 Schema 降级；
11. OpenAPI 3.0/3.1 使用统一领域接口；
12. examples/default 永远不是权威测试数据；
13. server candidates 永远不是实际执行环境；
14. security 声明永远不是运行时凭据；
15.规划契约不包含执行资格；
16.计划阶段、确认、执行和结论不进入不可变计划内容；
17. ValueSource 只有 LITERAL、TASK_INPUT、PRIOR_STEP_VARIABLE；
18. JsonPointer 只有 RFC 6901；
19.所有公开数据模型深层不可变；
20. M3 不新增持久化接口；
21. M3 不调用真实模型；
22. M3 不执行真实待测 API；
23. M3 不生成四态结论；
24.达到可信上下文和严格计划契约后必须停止。

---

# 14. M3 封板后可以声明的能力

README 可以声明：

- 已支持受限本地/远程 OpenAPI 来源读取；
-已支持 OpenAPI 3.0/3.1 的最小 operation 上下文；
-已支持受限文档内 `$ref`；
-已建立不可变 `OpenAPIContextSnapshot`；
-已建立 `NormalizedRule` 和 `ValidationPlanSnapshot` 数据契约；
-已建立固定 Fixture、golden 和确定性单元测试。

不得声明：

- 已能自动生成计划；
-已能判断计划合法；
-已能执行真实 API；
-已能发现缺陷；
-已形成 EvidenceBundle；
-已完成 Agent 闭环。

---

# 15. 后续阶段入口

M3 封板后，M4 才开始：

```text
候选计划确定性校验
+
确定性比较器
+
EvaluationResult
+
四态决策表
```

M4 不得重新定义 M3 已冻结的数据契约；确需破坏性修改时必须重新进行阶段设计评审。
