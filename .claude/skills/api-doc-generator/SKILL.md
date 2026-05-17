---
name: api-doc-generator
description: Scan backend code for Java, Go, Python, and Node.js projects to extract HTTP API endpoints and generate interface documentation in JSON or Markdown. Use when the user asks to scan a module, interface URL, or the whole project to auto-generate API docs.
---

# API Doc Generator

面向 Java、Go、Python、Node.js 多技术栈后端项目，从源码中扫描 HTTP 接口定义，并根据用户指定范围生成 JSON 或 Markdown 形式的接口文档。

## 使用时机

在当前项目中，当用户有类似需求时使用本 Skill：

- “生成接口文档 / API 文档 / 接口说明”
- “根据代码扫描所有接口”
- “按模块生成接口文档，比如 `backend/user-service`”
- “只针对某个 URL 或一组 URL 生成文档”
- “替代或补充 Swagger、OpenAPI 文档”

## 快速开始

1. **确定范围与输出格式**  
   用户会以自然语言指定：
   - 范围：
     - 整个项目：例如 “扫描整个项目的接口”
     - 某个模块目录：例如 “只扫描 `backend/user-service` 目录”
     - 某个接口 URL 或 URL 前缀：例如 “只生成 `/api/user` 相关接口”
   - 输出格式：
     - `json`：结构化 JSON，便于机器进一步处理
     - `md`：Markdown 文档，便于阅读与文档站集成
   - 若未指定格式，默认使用 `md`。

2. **推断后端技术栈与后端根目录**  
   使用工具（如 `Glob`、`Read`）检测项目特征文件与目录结构，推断：
   - 使用的语言/框架（Java / Go / Python / Node.js）
   - 主要后端目录（优先尝试：`backend/`、`server/`、`api/`，或根据框架标准结构推断）

3. **按语言规则扫描接口定义**  
   对每种识别到的语言/框架，使用对应规则在源码中查找路由/接口定义（见后文“语言/框架识别与扫描规则”）。

4. **构建统一接口模型**  
   将不同语言扫描到的接口信息统一映射到一个通用数据模型（见“接口数据模型定义”），便于后续统一输出。

5. **按用户指定格式输出并写入文件**  
   - 解析得到一个 `outputFormat`（`"json"` 或 `"md"`）以及一个输出文件路径（见下文“输出文件写入约定”）；  
   - 若为 `json`：根据统一模型生成结构化 JSON 字符串；  
   - 若为 `md`：根据统一模型生成层次化 Markdown 文本（按模块/服务分组、包含参数表等）；  
   - **必须**：将生成内容写入实际文件（而不是只返回到对话中），然后同时在回答中告知用户文件路径；  
   - 如有需要，仍可在回答中附带一份内容预览（例如前几行或某个服务的小节），但真正的完整结果以文件为准。

---

## 接口数据模型定义

统一数据模型用于描述单个 HTTP 接口（endpoint），以及按服务/模块聚合的结构。实现时不强制具体类型语言，仅约定字段含义。

### Endpoint 概念模型

```json
{
  "service": "user-service",
  "module": "user", 
  "controller": "UserController",
  "operationId": "getUserInfo",
  "path": "/api/users/{id}",
  "method": "GET",
  "summary": "获取用户详情",
  "description": "根据用户 ID 获取用户详情信息。",
  "tags": ["user", "read"],
  "deprecated": false,
  "pathParams": [
    {
      "name": "id",
      "type": "string",
      "required": true,
      "description": "用户 ID"
    }
  ],
  "queryParams": [
    {
      "name": "verbose",
      "type": "boolean",
      "required": false,
      "description": "是否返回扩展信息"
    }
  ],
  "headerParams": [
    {
      "name": "X-Request-Id",
      "type": "string",
      "required": false,
      "description": "请求链路追踪 ID"
    }
  ],
  "requestBody": {
    "contentType": "application/json",
    "schema": {
      "type": "object",
      "fields": [
        {
          "name": "name",
          "type": "string",
          "required": true,
          "description": "用户名"
        },
        {
          "name": "age",
          "type": "integer",
          "required": false,
          "description": "年龄"
        }
      ]
    },
    "description": "创建或更新用户的请求体"
  },
  "responses": [
    {
      "status": 200,
      "description": "请求成功",
      "contentType": "application/json",
      "schema": {
        "type": "object",
        "fields": [
          {
            "name": "id",
            "type": "string",
            "required": true,
            "description": "用户 ID"
          },
          {
            "name": "name",
            "type": "string",
            "required": true,
            "description": "用户名"
          }
        ]
      },
      "examples": {}
    }
  ]
}
```

### 服务/模块聚合结构（示例）

```json
{
  "services": [
    {
      "name": "user-service",
      "description": "用户相关接口",
      "endpoints": [
        {
          "...": "Endpoint 字段同上"
        }
      ]
    }
  ]
}
```

实现时可根据项目实际情况裁剪字段，但建议保持字段名语义一致，便于多项目复用。

---

## 用户输入解析约定

### 支持的典型指令形式

- “扫描整个项目，生成接口文档（md）”
- “只扫描 `backend/user-service` 模块，输出 json”
- “只生成 `/api/user` 和 `/api/admin` 相关接口的文档，格式 md”
- “扫描所有 Java + Go 后端服务，生成统一 JSON 接口清单”

### 解析规则

1. **范围解析**  
   - 若用户提供 **目录路径**（如 `backend/user-service`），仅在该目录下扫描。  
   - 若用户仅提到 “整个项目 / 所有接口”，则：
     - 优先识别标准后端目录（如 `backend/`、`server/`、`api/`、`services/`）；
     - 若无法确定，则在项目根目录下按语言特征文件（如 `pom.xml`、`go.mod`、`package.json`、`requirements.txt` 等）推断后端子目录，再在这些目录中扫描。

2. **URL 过滤**  
   - 若用户指定一个或多个 URL / URL 前缀（如 `/api/user`、`/internal/*`），则在构建统一模型后，对 `path` 字段进行过滤，仅保留匹配的 endpoint。  
   - 匹配方式可以是：
     - 完整相等：`path === 指定路径`
     - 前缀匹配：`path` 以指定前缀开头
     - 简单通配（如以 `*` 结尾时表示前缀）

3. **输出格式**  
   - 若用户显式指定 `json` 或 `md`，则按其要求输出。  
   - 若用户未指定，则默认输出 `md`。

---

## 输出文件写入约定

为避免“只在对话中展示结果但没有真实文件”的情况，本 Skill 在实现时需要遵守以下约定：

1. **默认输出目录**  
   - 推荐在当前项目下使用固定目录，例如：
     - Markdown：`docs/api/`  
     - JSON：`docs/api-json/`  
   - 当这些目录不存在时，应先创建目录，再写入文件。

2. **文件命名规则**  
   - 若用户没有指定文件名，建议按以下规则自动生成：
     - 基础名：`api-docs`；
     - 若用户指定了模块目录（如 `backend/user-service`），可在文件名中带上模块标识，例如：
       - Markdown：`api-docs-user-service.md`
       - JSON：`api-docs-user-service.json`
     - 若存在多次生成或需要区分时间，可在文件名后追加时间戳，例如：`api-docs-20260311-101500.md`。
   - 若用户显式指定了文件名，则优先使用用户指定的名称（并自动补齐扩展名与目录，如仅给出 `user-api`，则写入为 `docs/api/user-api.md`）。

3. **写入与返回策略**  
   - 生成文档后，**必须真正写文件** 到磁盘；  
   - 在回答中至少包含：
     - 实际写入的文件路径（相对项目根，如 `docs/api/api-docs-user-service.md`）；  
     - 如有必要，附带一小段内容预览或结构摘要（例如服务数量、接口数量）；  
   - 可以同时将完整内容作为字符串返回，但文件写入是强制要求。

4. **覆盖 / 追加策略**  
   - 默认行为可以是 **覆盖写入**（每次生成重写同名文件）；  
   - 若希望保留历史版本，可在实现中采用时间戳命名或版本号命名；  
   - 无论采用哪种策略，都应在回答中明确提示当前生成对应的文件名与是否覆盖了旧文件。

---

## 语言/框架识别与扫描规则

下面是针对各技术栈的识别与接口扫描要点，仅作为 Skill 使用时的指导原则，不要求实现完全精确的语法解析，更侧重于通过模式匹配快速提取大部分接口信息。

### 1. Java（Spring MVC / Spring Boot）

#### 项目识别

- 通过以下信号推断使用 Spring：
  - 存在 `pom.xml` 或 `build.gradle`；
  - `pom.xml` / `build.gradle` 中包含如 `spring-boot-starter-web`、`spring-web`、`spring-mvc` 等依赖；
  - 源码目录包含 `src/main/java/` 结构。

#### 源文件范围

- 使用 `Glob`：`**/*.java`，在推断的后端根目录（如 `backend/xxx` 或 `src/main/java`）下扫描。

#### 接口识别模式

- **控制器类级注解**：
  - `@RestController`
  - `@Controller`
  - 可能组合 `@RequestMapping("/xxx")`
- **方法级注解**：
  - `@RequestMapping(...)`
  - `@GetMapping(...)`
  - `@PostMapping(...)`
  - `@PutMapping(...)`
  - `@DeleteMapping(...)`
  - `@PatchMapping(...)`
- **路径组合规则**：
  - 类级 `@RequestMapping("/user")` + 方法级 `@GetMapping("/info")` => `/user/info`
  - 若方法级注解使用 `value` 或 `path` 属性，需要解析其字符串值：
    - `@GetMapping("/info")`
    - `@GetMapping(path = "/info")`
    - `@RequestMapping(value = "/info", method = RequestMethod.GET)`
- **HTTP 方法推断**：
  - 由方法级注解名直接推断（`GetMapping` -> `GET`，`PostMapping` -> `POST` 等）；
  - 或由 `@RequestMapping(method = RequestMethod.GET)` 中的 `RequestMethod` 推断。

#### 参数与请求体/响应模型（简化）

- **路径参数**：
  - 参数注解 `@PathVariable`，结合方法签名中的参数名与类型。
- **查询参数**：
  - 参数注解 `@RequestParam`。
- **请求体**：
  - 参数注解 `@RequestBody`；
  - 尽量关联到 DTO 类型名，必要时可在同文件中继续搜索该类型的字段信息。
- **响应模型**：
  - 方法返回类型（如 `UserDto`, `ResponseEntity<UserDto>`）；
  - 可在 DTO 定义中搜索字段，构建响应字段结构（若成本过高可先只记录类型名）。

#### 描述信息

- 优先使用：
  - 方法上的 JavaDoc 注释；
  - Swagger / OpenAPI 注解：
    - `@ApiOperation(value = "...", notes = "...")`
    - `@Operation(summary = "...", description = "...")`
- 若缺失，则可用类名 + 方法名作为退化描述。

---

### 2. Go（net/http、Gin 等）

#### 项目识别

- 存在 `go.mod`；
- 源码中含有 `package main` 或标准 Go 目录结构（如 `cmd/`, `internal/`, `pkg/` 等）。

#### 源文件范围

- 使用 `Glob`：`**/*.go`，过滤测试文件（如 `*_test.go`）。

#### 接口识别模式

- **Gin**：
  - 常见形式：
    - `router.GET("/path", handler)`
    - `router.POST("/path", handler)`
    - `group.PUT("/path", handler)`
    - `r.DELETE("/path", handler)`
  - 分组路由：
    - `userGroup := router.Group("/user")`
    - `userGroup.GET("/info", handler)` => `/user/info`
- **net/http**：
  - `http.HandleFunc("/path", handler)`
  - `mux.HandleFunc("/path", handler)`

#### 参数与请求体/响应模型（简化）

- Go 中类型信息多通过 handler 内部解析（如 `c.BindJSON(&req)` 或 `json.NewDecoder(r.Body).Decode(&req)`），可选择性：
  - 搜索 handler 内部的 `BindJSON`、`Decode` 调用，尝试获取绑定的 struct 类型；
  - 若成本过高，可仅记录 handler 函数名与请求体类型名（如果明显）。

#### 描述信息

- 优先使用 handler 函数上方的注释，作为 `summary` 或 `description`。

---

### 3. Python（Django / Flask / FastAPI）

#### 项目识别

- 通过以下信号：
  - 存在 `manage.py`、`settings.py`（Django）；
  - 依赖文件（如 `requirements.txt`、`pyproject.toml`、`Pipfile`）中包含：
    - `django`
    - `flask`
    - `fastapi`
  - 源码目录里存在 `app.py`、`main.py`、`asgi.py`、`wsgi.py` 等典型入口。

#### 源文件范围

- 使用 `Glob`：`**/*.py`，排除迁移等可选目录（如 `migrations/`）视需要调整。

#### 接口识别模式

- **Flask**：
  - 装饰器形式：
    - `@app.route("/path", methods=["GET", "POST"])`
    - `@blueprint.route("/path", methods=["GET"])`
  - 从 `methods` 参数中读取 HTTP method 列表，未指定默认 `GET`。

- **FastAPI**：
  - 装饰器形式：
    - `@app.get("/path")`
    - `@app.post("/path")`
    - `@router.put("/path")`
    - `@router.delete("/path")`
  - HTTP 方法直接由装饰器名推断。
  - 参数类型注解（如 `id: int`, `q: str | None = Query(None)`）可用于构建 path/query 参数描述。

- **Django**（基础支持）：
  - 在 `urls.py` 或其它 URL 配置中查找：
    - `urlpatterns = [ path("path/", view_func, name="..."), ... ]`
    - `re_path(r"^path/$", view_func, ...)`
  - 进一步可关联到 view 函数或 class-based view，但首版可只记录 path、view 名称与 HTTP method（若难以精确，则默认 `GET`，并在描述中标注“method 未精确识别”）。

#### 描述信息

- 优先来源：
  - 视图函数 / 处理函数的 docstring；
  - 装饰器参数（若有描述类扩展）；
  - 与路由同文件中的注释。

---

### 4. Node.js（Express / Koa / NestJS 等）

#### 项目识别

- 存在 `package.json`；
- `package.json` 中依赖包含：
  - `express`
  - `koa`, `@koa/router`
  - `@nestjs/common`, `@nestjs/core`

#### 源文件范围

- 使用 `Glob`：
  - JavaScript：`**/*.js`
  - TypeScript：`**/*.ts`
  - 可排除前端目录（如 `frontend/`、`src/client/`），重点扫描后端目录（如 `src/`, `server/`, `backend/` 中与 Node 服务相关部分）。

#### 接口识别模式

- **Express**：
  - 典型形式：
    - `app.get("/path", handler)`
    - `app.post("/path", handler)`
    - `router.put("/path", handler)`
    - `router.delete("/path", handler)`
  - 支持链式调用或变量别名（如 `const r = express.Router(); r.get("/path", ...)`）。

- **Koa + Router**：
  - `router.get("/path", handler)`
  - `router.post("/path", handler)`

- **NestJS**：
  - 控制器类：
    - `@Controller('/users')` class `UserController` {...}
  - 方法装饰器：
    - `@Get('/list')`
    - `@Post('/')`
    - `@Put(':id')`
  - 路径组合与 Spring 类似：类级路径前缀 + 方法级路径。

#### 参数与请求体/响应模型（简化）

- Node 通常在 handler 中解析 `req.params`、`req.query`、`req.body` 等：
  - 若直接解析字段（如 `const { id } = req.params`），可在同一函数中简单收集字段名；
  - 若使用 DTO 或 schema 校验库（如 `Joi`、`zod`、`class-validator` 等），可进一步读取 schema 定义，构建字段描述（首版可选）。

#### 描述信息

- 优先来源：
  - handler 上方注释；
  - NestJS 中类或方法上的装饰器（如 `@ApiOperation({ summary: '...' })`）；
  - 若无，则使用 controller + handler 函数名作为退化描述。

---

## 扫描与构建模型的流程建议

实现本 Skill 时，可按以下顺序执行（可根据项目实际情况调整）：

1. **定位后端根目录**（如存在多个服务，可多次执行或多服务并行扫描）。  
2. **检测语言/框架**：  
   - 根据特征文件与依赖判断哪些语言/框架实际存在；  
   - 仅对存在的语言执行扫描，避免无用遍历。
3. **按语言扫描接口定义**：  
   - 使用 `Glob` 定位候选源码文件集；  
   - 使用 `Grep` 或等价工具，按上述模式搜索注解、装饰器、路由调用等；  
   - 在需要更高语义理解时，可在单文件范围内用 `SemanticSearch` 或 AST 方案，但需注意性能。
4. **提取字段并填充统一 Endpoint 模型**：  
   - 每发现一个接口定义，就构建一个 Endpoint 实例；  
   - 尽量填充路径、方法、控制器、operationId、参数、请求体、响应等字段；  
   - 无法确定的信息可留空或用描述性占位（例如 `type: "unknown"`）。
5. **按服务/模块分组**：  
   - 根据目录结构、命名约定（如 `user-service`, `order-service`）推断 `service` 字段；  
   - 可按 package/module/controller 进行次级分组，便于 Markdown 展示。
6. **应用用户指定的 URL / 模块过滤**：  
   - 根据用户提供的目录/URL 条件过滤 Endpoint 列表。  
7. **生成最终输出**：  
   - 使用下文“输出格式模板”将统一模型渲染为 JSON 或 Markdown。

---

## 输出格式模板

### JSON 输出模板

当用户指定 `json` 格式时，推荐输出结构如下（可根据项目实际略作调整）：

```json
{
  "generatedAt": "2026-03-11T10:00:00Z",
  "project": "example-project",
  "services": [
    {
      "name": "user-service",
      "description": "用户相关接口",
      "endpoints": [
        {
          "service": "user-service",
          "module": "user",
          "controller": "UserController",
          "operationId": "getUserInfo",
          "path": "/api/users/{id}",
          "method": "GET",
          "summary": "获取用户详情",
          "description": "根据用户 ID 获取用户详情信息。",
          "tags": ["user", "read"],
          "deprecated": false,
          "pathParams": [],
          "queryParams": [],
          "headerParams": [],
          "requestBody": null,
          "responses": []
        }
      ]
    }
  ]
}
```

实现时可按需增加字段，例如：

- `version`：当前文档版本或项目版本；
- `languageSummary`：简要说明哪些语言/框架参与了扫描；
- `scanConfig`：记录扫描时使用的根目录、过滤条件等信息。

### Markdown 输出模板

当用户指定 `md` 或未指定格式时，推荐生成结构类似：

```markdown
# 接口文档（自动生成）

生成时间：2026-03-11T10:00:00Z  
项目：example-project

## user-service 用户服务

### GET /api/users/{id}

**接口说明**  
获取用户详情。

**所属控制器**  
`UserController.getUserInfo`

**路径参数**

| 名称 | 类型   | 必填 | 说明     |
| ---- | ------ | ---- | -------- |
| id   | string | 是   | 用户 ID  |

**查询参数**

| 名称   | 类型    | 必填 | 说明             |
| ------ | ------- | ---- | ---------------- |
| verbose | boolean | 否   | 是否返回扩展信息 |

**请求头参数**

| 名称        | 类型   | 必填 | 说明         |
| ----------- | ------ | ---- | ------------ |
| X-Request-Id | string | 否   | 请求追踪 ID  |

**请求体（Request Body）**

Content-Type: `application/json`

| 字段 | 类型    | 必填 | 说明   |
| ---- | ------- | ---- | ------ |
| name | string  | 是   | 用户名 |
| age  | integer | 否   | 年龄   |

**响应（Responses）**

- `200 OK`  
  Content-Type: `application/json`

  | 字段 | 类型   | 必填 | 说明    |
  | ---- | ------ | ---- | ------- |
  | id   | string | 是   | 用户 ID |
  | name | string | 是   | 用户名  |

---
```

实现时可：

- 按 `service` 分节；  
- 每个 Endpoint 一个子小节，标题统一为 `METHOD path`；  
- 缺失的字段用“（暂无信息）”或直接省略对应表格部分。

---

## 使用 Cursor 工具的建议

实现或使用本 Skill 时，可以配合 Cursor 提供的工具，以在不同语言下高效扫描：

- **Glob**：  
  - 用于快速定位代码文件：
    - Java：`**/*.java`
    - Go：`**/*.go`（排除 `*_test.go`）
    - Python：`**/*.py`
    - Node.js：`**/*.js`, `**/*.ts`
- **Grep**（或同等 ripgrep 工具）：  
  - 用于匹配典型注解/装饰器/路由模式，例如：
    - Java：`@RestController`, `@GetMapping`, `@PostMapping` 等；
    - Go：`\\.GET\\(\"/`, `http.HandleFunc\\(\"/` 等；
    - Python：`@app\\.route\\(\"/`, `@router\\.get\\(\"/`, `urlpatterns` 等；
    - Node.js：`app\\.get\\(\"/`, `router\\.post\\(\"/`, `@Controller\\(`, `@Get\\(\"/` 等。
- **SemanticSearch**：  
  - 在大型文件或复杂 handler 内，帮助理解与接口关联的 DTO、schema 定义等；
  - 在无法通过简单字符串搜索确定请求体/响应结构时，可以对相关类型/结构体进行语义查找。

性能建议：

- 尽量先用 **特征文件 + 目录结构** 限定搜索范围，再在指定目录下做 `Glob` + `Grep`；  
- 避免在整个仓库做无筛选的全文搜索，尤其是当前端/文档/依赖目录较大时。

---

## 扩展与自定义

- **新增语言/框架支持**：  
  - 在后续需要支持新的后端技术（如 PHP Laravel、Ruby on Rails、Rust Axum/Actix 等）时，可以：
    - 添加对应的“项目识别”规则（特征文件、依赖名、目录结构）；
    - 定义新的“接口识别模式”（路由、装饰器、宏等）；
    - 将提取到的信息映射到统一 Endpoint 模型字段。

- **项目特定约定**：  
  - 若项目有自定义的注解/装饰器/路由封装（例如自定义 `@ApiGet`、`defineRoute("/path", "GET")` 等）：
    - 可在本 Skill 的实现中加入额外的匹配规则；
    - 或在项目本身维护一个简单的“映射说明”（如单独文档），由使用者手动补充接口说明。

- **与现有文档体系集成**：  
  - 生成的 JSON 可作为后续生成 OpenAPI/Swagger 文件的中间层；  
  - 生成的 Markdown 可以直接放入文档站（如 Docusaurus、VuePress、MkDocs）中，或进一步加工。

