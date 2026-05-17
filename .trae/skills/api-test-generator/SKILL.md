---
name: api-test-generator
description: Generate executable chained API test cases Excel for api-test-runner. Use when users ask to generate cases.xlsx from scenario docs for direct Excel execution.
---

# API 测试用例生成（JSON + Excel 双产出）

基于 `scenario.json` 和接口文档，生成 `api-test-runner` 执行输入 `cases.json`，并同时导出 `cases.xlsx`（2-sheet）。  
本 skill 默认流程为：先生成 `cases.json`，再导出 `cases.xlsx`。

## 输入与输出

- 输入 1：`docs/<name>_scenario.json`（或用户给定场景 JSON）
- 输入 2：接口文档（如 `demo_project/API接口定义.md`）
- 输出 1：`docs/<name>_cases.json`
- 输出 2：`docs/<name>_cases.xlsx`

## 工作流

1. 读取 `scenario.json` 顶层 `dependencies` + `cases` 与每条 `步骤` 文本。
2. 读取接口文档中的 method/path、请求字段、路径参数、响应关键字段。
3. **由 Agent 按本 skill「生成规则」「输出自检清单」将 scenario 转为 `cases.json`**（继承顶层 `dependencies`、解析步骤为 `steps`、补全 `body`/路径参数/断言；登录去重与 `DEP` 注入规则见下文）。**不再使用** `scenario_to_json_plan.py`（已移除）。
4. 先判断 DB 开关与配置：  
   - 若 `DB_ASSERT_ENABLED=false` 或 DB 配置不完整：跳过 DB 断言，仅输出纯 HTTP `cases.json`。  
   - 若 DB 配置完整：**必须先执行查表结构脚本**，再做 SQL 组装和 `db_assert`。
5. 执行 `plan_json_to_excel.py` 导出为 `cases.xlsx`，按「输出自检清单」检查后输出最终文件（`cases.json` + `cases.xlsx`）。

### 5.1 cases.json -> cases.xlsx 导出

- 脚本路径：`.cursor/skills/api-test-generator/scripts/plan_json_to_excel.py`
- `cases.json` 就绪后导出 Excel（`python` 不可用处换 `python3`）：

```bash
python3 .cursor/skills/api-test-generator/scripts/plan_json_to_excel.py \
  -i docs/<name>_cases.json \
  -o docs/<name>_cases.xlsx
```

### 4.1 通用查表结构脚本（必须先执行）

- 脚本路径：`.cursor/skills/api-test-generator/scripts/export_db_schema.py`
- 作用：查询 `information_schema` 并输出 `docs/<name>_db_schema.json`
- 读取配置优先级：命令行参数 > 系统环境变量 > `config/.env`
- 通用调用方式：

```bash
python .cursor/skills/api-test-generator/scripts/export_db_schema.py \
  --output docs/<name>_db_schema.json
```

- 指定参数调用方式（覆盖 `.env`）：

```bash
python .cursor/skills/api-test-generator/scripts/export_db_schema.py \
  --host 127.0.0.1 --port 3306 --name demo_project \
  --user root --password your_db_password \
  --output docs/demo_project_db_schema.json
```

## cases.json 目标结构

```json
{
  "dependencies": [
    {
      "name": "dep_login_admin",
      "request": {
        "method": "POST",
        "path": "/auth/login",
        "headers": {},
        "path_params": {},
        "body": {
          "username": "admin",
          "password": "123456"
        }
      },
      "assert": {
        "status": 200,
        "checks": ["$.code==200 && $.data.token && $.data.userId"]
      },
      "extract": {
        "token": "$.data.token",
        "userId": "$.data.userId"
      }
    },
    {
      "name": "dep_login_buyer",
      "request": {
        "method": "POST",
        "path": "/auth/login",
        "headers": {},
        "path_params": {},
        "body": {
          "username": "buyer001",
          "password": "123456"
        }
      },
      "assert": {
        "status": 200,
        "checks": ["$.code==200 && $.data.token && $.data.userId"]
      },
      "extract": {
        "token": "$.data.token",
        "userId": "$.data.userId"
      }
    }
  ],
  "cases": [
    {
      "id": "1",
      "name": "场景名称",
      "enabled": true,
      "steps": [
        {
          "name": "step_01_get",
          "request": {
            "method": "GET",
            "path": "/api/v1/user",
            "headers": {
              "Authorization": "Bearer DEP:dep_login_admin.token"
            },
            "path_params": {}
          },
          "assert": {
            "status": 200,
            "checks": ["$.code==200 && $.data.userId==DEP:dep_login_admin.userId"]
          }
        }
      ],
      "assert": {
        "status": 200,
        "checks": ["$.code==200"]
      },
      "db_assert": [
        {
          "name": "check_order_row",
          "sql": "SELECT id,status FROM orders WHERE id = STEP:step_02_post.orderId",
          "checks": ["rows_count==1", "row0.status==\"CREATED\""]
        }
      ]
    }
  ]
}
```

## 生成规则（强约束）

### 0) case id 编号规则（新增）

- `cases[*].id` 使用纯数字字符串序号：`"1"`, `"2"`, `"3"` ...（按输出顺序递增）。
- 不再使用任何编码前缀（如 `SCN-001`、`CASE-001`）。
- 若输入 `scenario.json` 的 `场景ID` 已是数字，可直接沿用；否则在生成 `cases.json` 时重排为连续数字序号。

### 1) 步骤与接口映射

- 从 `步骤` 文本抽取调用顺序（`GET/POST/PUT/DELETE/PATCH + /path`）。
- 每个 API 调用生成一个 step，step 名固定为 `step_<序号>_<method小写>`。
- `request.method` 与 `request.path` 必填。

### 2) 请求参数与路径参数

- 写接口（`POST/PUT/PATCH`）必须有业务 `body`（文档声明无请求体除外）。
- `body` 字段优先级：
  1. 场景步骤中明确值（如 `status=CANCELLED`、`quantity=20`）
  2. 接口文档请求字段定义与示例
  3. 固定字面量示例（如 `user001`、`user001@demo.com`、`1`）
- 路径参数（如 `{userId}`、`{productId}`、`{orderId}`）必须赋具体值。

### 3) 鉴权与提取（强约束）

- 默认优先将可复用登录写入 `dependencies`，非登录步骤按用户注入：
  - `Authorization: Bearer DEP:<dependency名>.token`
- 若 `scenario.json` 已有顶层 `dependencies`，必须优先复用，不得重复生成等价登录 step。
- 若 case 的 `步骤` 中出现等价登录动作，生成 `cases.json` 时应去重并提升到顶层 `dependencies`（特殊登录场景除外）。
- 登录类接口（如 `/auth/login`）的提取字段固定为：
  - `extract.token = $.data.token`
  - `extract.userId = $.data.userId`
- 登录 dependency 命名建议：`dep_login_<username>`（同一用户只保留一条）。
- 特殊场景允许将登录写在 `steps`（不要强行抽到 `dependencies`）：
  - 场景本身验证登录成功/失败/异常；
  - 场景存在重登、切换账号、刷新 token；
  - 场景登录参数与全局复用登录不一致。

### 3.1) 登录复用判定规则

- 先按用户名/账号标识做归一化；同一用户复用同一个登录 dependency。
- 若 `scenario.json` 涉及多个用户，允许并建议生成多个登录 dependencies。
- 若为特殊登录流程（见上），登录步骤直接保留在对应 case 的 `steps`。
- 允许同一 `cases.json` 同时存在：
  - 全局 `dependencies` 登录（主路径）
  - 个别 case 内显式登录 step（特殊路径）
- 普通业务场景禁止“每条 case 首步都登录”；可复用登录必须只在 `dependencies` 执行一次。

### 3.2) 造数与关联编排规则

- `dependencies` 优先放全局可复用准备动作（登录、基础造数）。
- 默认每个 case 自洽，不依赖前一 case 的可变状态（除非场景明确要求）。
- 若必须跨 case 复用数据，必须显式声明来源并保证执行顺序可追踪。
- 禁止模式：
  - 前序 case 删除/失效资源，后序 case 继续引用该资源；
  - 在 `checks` 右值中直接使用 runner 不支持的动态写法（如 `STEP:...` 字面比较）。
- `extract` 与引用规则：
  - `extract` 路径必须与 runner 解析能力一致；
  - `path_params/body/headers` 引用提取值前，必须确保有来源；
  - 对关键引用建议提供兜底方案（显式已知值或补造数 step），避免 `None` 路径参数。

### 4) 断言生成

- `assert.status` 默认 `200`（按场景可改 4xx/5xx）。
- `assert.checks` 使用 runner 表达式：
  - 支持：`==`, `!=`, `>`, `>=`, `<`, `<=`
  - 多条件 AND：`&&`（兼容 `;`）
- 推荐模板：
  - 登录成功：`$.code==200 && $.data.token && $.data.userId`
  - 列表查询：`$.code==200 && $.data.list && $.data.total>=0`
  - 详情查询：`$.code==200 && $.data.id`
  - 创建成功：`$.code==200 && $.data.id`
  - 删除成功：`$.code==200`

### 4.2) DB 断言生成（查结构 -> 组 SQL）

- 仅在以下条件满足时生成 `db_assert`：
  - `DB_ASSERT_ENABLED` 不为 `false`；
  - 环境变量完整：`DB_HOST`、`DB_PORT`、`DB_NAME`、`DB_USER`、`DB_PASS`。
- 满足上述条件时，必须先执行 `.cursor/skills/api-test-generator/scripts/export_db_schema.py`，
  成功生成 `docs/<name>_db_schema.json` 后，才允许编写 `db_assert.sql`。
- 若 DB 配置缺失或关闭：
  - 不生成 `db_assert`；
  - 保持纯 HTTP `cases.json` 输出；
  - 在结果说明中标注“已跳过 DB 断言生成”。
- 启用 DB 时，建议先查询 `information_schema` 并缓存为 `docs/<name>_db_schema.json`：
  - 表清单：`TABLE_NAME`
  - 字段：`COLUMN_NAME`、`DATA_TYPE`、`IS_NULLABLE`
  - 关键键：`COLUMN_KEY`（优先 `PRI` / `UNI`）
- SQL 组装优先级：
  1. 场景/步骤中明确的业务主键（如 `orderId`）
  2. 表主键（`PRI`）
  3. 唯一键（`UNI`）
- `db_assert.checks` 最小建议：
  - `rows_count==1`
  - `row0.<column>==<expected>`
- SQL 中的 `STEP:` / `DEP:` / `ENV:` 占位符**禁止手工加单引号**：
  - runner 会按值类型自动生成 SQL 字面量（字符串单引号并转义、数字原样、bool 转 TRUE/FALSE、None 转 NULL）。
  - 正例：`SELECT id FROM orders WHERE id = STEP:step_03_post.orderId`
  - 反例：`SELECT id FROM orders WHERE id = 'STEP:step_03_post.orderId'`（运行时会被替换为 `''字符串''` 双重引号，导致语义错误）

### 5) 禁止项

- 禁止占位体：`{"example":1}`、`__RANDOM__`、`__RANDOM_INT__`、`__DEP:*`。
- 禁止输出非 JSON 文本（解释、注释、代码围栏）。

## 输出自检清单（必须通过）

1. 顶层包含且仅包含必要键：`dependencies`（list）、`cases`（list）。
2. 每个 case 至少包含：`id`、`name`、`enabled`、`steps`、`assert`。
3. 每个 step 至少包含：`name`、`request`、`assert`。
4. 每个 `request` 至少包含：`method`、`path`。
5. 写接口 `body` 不为空对象（文档明确“请求体：无”除外）。
6. 全文件不得出现 `example` 占位键或随机占位符。
7. `checks` 语法符合 runner 约定，且至少包含一个业务码/状态判断。
8. 同一用户可复用登录时，不应在多个 case 中重复构造等价登录步骤。
8.1 若输入场景已提供顶层 `dependencies`，输出 plan 必须继承并按 `DEP` 引用，不得降级为 case 内重复登录。
9. 多用户场景下，`dependencies` 应包含对应多条登录依赖并按用户注入鉴权头。
10. 特殊登录流程允许放在 `steps`，但需在该 step 内保留完整断言与提取。
11. 不得出现“前序场景销毁资源、后序场景仍引用同资源”的跨 case 污染。
12. 每个被引用键（`DEP/STEP`）都必须存在可追溯来源，禁止悬空引用。
13. case 顶层 `assert.status` 与末步语义保持一致，避免末步失败但 case 仍写 200。
14. 若生成了 `db_assert`，每条必须包含 `sql` 且 `checks` 仅使用 `rows_count` / `row0.<column>` 语法。

## Excel 输出格式（2-sheet）

- `dependencies` sheet 列：
  - `name`, `depends_on`, `method`, `path`, `headers_json`, `body_json`, `assert_status`, `assert_checks`, `extract_json`
- `cases` sheet 列：
  - `id`, `name`, `enabled`, `case_assert_status`, `case_assert_checks`, `steps_json`, `db_assert_json`
- 约束：
  - `steps_json` 为非空 JSON 数组，元素结构等价 `cases.json` 的 `steps[*]`
  - `db_assert_json` 为 JSON 数组，可为空（空单元格视为 `[]`）
  - `assert_checks` / `case_assert_checks` 使用 JSON 数组字符串

若任一项失败：先修正失败项，再重新执行自检；全部通过后才输出 `cases.json` 与由其导出的 `cases.xlsx`（两者语义一致）。

## demo_project 验收基线

- 输入：
  - `docs/demo_project_scenario.json`
  - `demo_project/API接口定义.md`
- 输出：
  - `docs/demo_project_cases.json`
  - `docs/demo_project_cases.xlsx`
- 关键接口字段验收：
  - `POST /auth/login` -> `username/password`
  - `POST /api/v1/users` -> `username/password/email`
  - `POST /api/v1/products` -> `name/price/status`
  - `POST /api/v1/inventory/inbound` -> `productId/quantity`
  - `POST /api/v1/orders/place` -> `items[].productId/items[].quantity`
  - `PUT /api/v1/orders/{orderId}/status` -> `status`

## 资源

- 串联清单格式参考：`references/chain-manifest-schema.md`
