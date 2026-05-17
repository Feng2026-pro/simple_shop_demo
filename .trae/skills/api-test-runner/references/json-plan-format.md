# JSON 测试用例格式说明

Runner 支持通过 `--json-cases` 读取测试用例，包含可选的全局依赖、可选的接口目录、以及业务用例。

## 顶层结构

```json
{
  "apiCatalog": "docs/api-catalog.sample.json",
  "dependencies": [],
  "cases": []
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `dependencies` | 否 | 数组；session 级依赖链，见下 |
| `cases` | 是 | 数组；业务用例 |
| `apiCatalog` | 否 | 字符串；相对**项目根**的接口目录 JSON 路径；也可由命令行 `--api-catalog` 覆盖 |

## dependencies（前置依赖链）

- `name`：依赖名，唯一
- `depends_on`：可选，数组，表示依赖执行顺序
- `request`：请求定义
  - `method`：GET/POST/PUT/DELETE（默认 POST）
  - `path`：接口路径（如 `/api/v1/login`），会拼接 `BASE_URL`
  - `headers`：可选对象，支持 `ENV:` / `DEP:`
  - `body`：可选对象，支持 `ENV:` / `DEP:`
- `extract`：响应提取，键为变量名，值为 JSONPath（如 `$.data.token`）

## 接口目录文件（apiCatalog）

单独 JSON，用于把 `method` / `path` / 默认 `headers` / `body` 抽离，供 case 内 `steps` 的 `api` 字段引用。

```json
{
  "apis": {
    "order.create": {
      "method": "POST",
      "path": "/api/v1/orders",
      "headers": {},
      "body": {}
    }
  }
}
```

- `apis`：对象，键为接口代号（与 step 里的 `api` 一致），值为与 `request` 相同的子结构（`method`、`path`、可选 `headers`、`body`、`path_params`）。

## cases（业务用例）

每条 case **必须且仅能**使用以下两种之一：

| 模式 | 字段 | 说明 |
|------|------|------|
| 单请求 | `request` + `assert` | 与旧版一致，一次 HTTP |
| 多步 | `steps` + `assert` | 不要求顶层 `request`；按顺序执行多步；顶层 `assert` 作用于**最后一步**的响应 |

公共字段：

- `id`：用例 ID（必填）
- `name`：描述（可选）
- `enabled`：是否执行（默认 `true`）
- `assert`：见下
- `db_assert`：可选，数据库断言数组（有 DB 配置时执行；无配置自动跳过）

### 单请求：`request`

- `method`、`path`、`path_params`、`headers`、`body`
- 占位解析：`ENV:`、`DEP:`、`STEP:`（单请求模式下无前置 step，通常不用 `STEP:`）

### 多步：`steps`

数组，按顺序执行。每一步：

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | 本 case 内唯一，供 `STEP:name.field` 引用 |
| `api` 或 `request` | 二选一 | `api`：在 `apiCatalog` 的 `apis` 中查找模板；`request`：完全内联，不查目录 |
| `path_params` / `headers` / `body` | 否 | 与目录模板做**浅层合并**（同名字段 step 覆盖目录） |
| `extract` | 否 | 本步响应 JSON 提取，写入本 step 的命名空间 |
| `assert` | 否 | 断言本步；未写 `checks` 时仍校验 HTTP `status`（默认 200） |

执行顺序：每步先解析引用并发请求，再校验本步 `assert`，再执行 `extract`，供后续 `STEP:` 使用。

## assert（HTTP + JSON）

```json
{
  "status": 200,
  "checks": ["$.code==200", "$.data.id"]
}
```

- `status`：预期 HTTP 状态码（默认 200）
- `checks`：字符串数组，语法与 CSV 的「预期响应校验」一致（支持 `&&` / `;` 多条件）

## db_assert（可选数据库断言）

`db_assert` 是 `case` 级数组，默认在 HTTP 断言完成后执行。用于校验接口调用后的落库结果。

```json
{
  "id": "SCN-ORDER-001",
  "name": "下单后查库校验",
  "steps": [
    {
      "name": "place_order",
      "request": {
        "method": "POST",
        "path": "/api/v1/orders/place",
        "body": {"items": [{"productId": 1001, "quantity": 1}]}
      },
      "extract": {"orderId": "$.data.orderId"}
    }
  ],
  "db_assert": [
    {
      "name": "order_created",
      "sql": "SELECT id,status,total_amount FROM orders WHERE id = STEP:place_order.orderId",
      "checks": ["rows_count==1", "row0.status==\"CREATED\"", "row0.total_amount>0"]
    }
  ],
  "assert": {"status": 200, "checks": ["$.code==200"]}
}
```

### 字段说明

- `name`：断言名（可选，便于日志定位）
- `sql`：SQL 语句（必填），支持引用协议（见下）
- `checks`：断言数组（可选），支持下列左值：
  - `rows_count`：查询返回行数
  - `row0.<column>`：第一行字段值（0-based）

### checks 语法

- 运算符：`==`, `!=`, `>`, `>=`, `<`, `<=`
- 示例：
  - `rows_count==1`
  - `row0.status=="PAID"`
  - `row0.amount>=100`

### 执行与降级规则

- 当 `DB_ASSERT_ENABLED=false` 时，跳过所有 `db_assert`。
- 当 DB 必填配置不完整（`DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASS`）时，跳过所有 `db_assert`。
- 跳过不影响 HTTP 结果；runner 会记录 skip 原因。
- 若 `db_assert` 被执行且任一 check 失败，该 case 记为失败。

## 引用协议

| 前缀 | 含义 |
|------|------|
| `ENV:KEY` | 环境变量 |
| `DEP:depName.field` | session 依赖 `dependencies` 中某步的 `extract` 键 |
| `STEP:stepName.field` | **当前 case** 内已执行步骤 `name` 的 `extract` 键 |

解析作用于：`path_params`、`headers`、`body`、`db_assert.sql` 中的字符串。

### 字符串内嵌 `DEP:` / `STEP:`

除「整串以 `DEP:` / `STEP:` 开头」外，支持在任意字符串中嵌入引用，便于拼 `Authorization` 等头，例如：

- `"Authorization": "Bearer DEP:auth.token"`（`auth` 为 `dependencies` 中某条的名字，`token` 为其 `extract` 键）
- `"Authorization": "Bearer STEP:login.token"`（`login` 为本 case 内前置 step 的 `name`）

嵌入语法与上表一致：`DEP:depName.field`、`STEP:stepName.field`（仅允许字母数字下划线）。

## 输出

- Allure：`allure-results` / `allure-report`
- JSON 汇总：`reports/json-run-result.json`

## 示例文件（项目根 `docs/`）

- `docs/api-catalog.sample.json`：接口目录
- `docs/cases_with_steps.sample.json`：单请求 + `steps` + `apiCatalog` 示例
- `docs/demo_project_chain_cases.json`：demo_project 本地服务，`dependencies` + `steps` 串联（登录后调业务接口）

运行前请设置 `BASE_URL`（如 jsonplaceholder：`https://jsonplaceholder.typicode.com`；demo 本地：`http://localhost:11011`）。

```bash
python scripts/run_tests.py --cases-json docs/plan_with_steps.sample.json --base-url https://jsonplaceholder.typicode.com
python scripts/run_tests.py --cases-json docs/api_cases.json --api-catalog docs/other-catalog.json
```
