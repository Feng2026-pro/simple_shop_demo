---
name: api-scenario-generator
description: Generate business-readable chained API scenarios in JSON and Excel. Use when users want concise multi-interface test points (e.g. call A to get token, then call B/C).
---

# 场景生成（文档 -> 场景 JSON -> 场景 Excel）

本 skill 聚焦**测试设计与评审**，默认只维护两份产物：

- `docs/<name>_scenario.json`（权威输入，含顶层 `dependencies`）
- `docs/<name>_scenario.xlsx`（评审表）

重点是先沉淀**单接口用例**，再补充**多接口串联场景**，并统一在同一份 JSON/Excel 中评审。

## 默认覆盖策略（全量）

- 默认按接口文档中的**全部业务模块**生成，不仅限于某个模块。
- 生成顺序固定：先 `单接口`，后 `串联`。
- 覆盖深度默认包含：`CRUD + 常见负向 + 边界值`。
- 每个接口至少 1 条 `单接口` 正向用例。
- 写操作（POST/PUT/DELETE）默认补充：
  - 必填缺失
  - 非法状态/非法取值
  - 资源不存在
  - 业务约束冲突（如库存不足、不可删除状态）
- 数值字段默认补充边界：`0`、负数、最小合法值、超限（若文档可判断）。
- 查询接口默认补充：存在/不存在；若文档说明了权限或归属限制，则补充越权/归属负向。
- 产物要求：同一份 `*_scenario.json`（根键 `cases`）与同一份 `*_scenario.xlsx`（单 Sheet，含 `场景类型`）。

## 执行要求（触发 skill 时）

- 命中本 skill 后，**默认执行脚本并落地产物**，不是只给命令示例。
- 默认按 `docs/<name>_*` 规则推导输入输出，并回报实际产物路径。
- 若 `*_scenario.xlsx` 被占用写不进去，允许回退到 `*_scenario_generated.xlsx`。
- 执行后至少反馈：输入行数（场景数）与最终写出的 xlsx 路径。

## 固定产物

默认输出到项目 `docs/`：

- `docs/<name>_scenario.json`：场景主输入（根键 `cases`），见 [references/scenario-json-schema.md](references/scenario-json-schema.md)
- `docs/<name>_scenario.xlsx`：由 JSON 生成的场景评审表，见 [references/scenario-excel-spec.md](references/scenario-excel-spec.md)

## 场景模型（最少字段）

场景对象建议只保留以下字段（按评审优先）：

- `场景类型`（`单接口` / `串联`）
- `场景ID`
- `场景名称`
- `测试点`
- `优先级`
- `前置条件`
- `步骤`（核心：多接口串联过程）
- `预期结果`
- `备注`

`步骤` 推荐写成编号文本，例如：

1. 调用 `/auth/login` 获取 `token`
2. 调用 `/api/v1/orders/place`，请求头注入 `Authorization: Bearer {token}`
3. 调用 `/api/v1/orders/{orderId}` 校验订单状态与金额

### 顶层 dependencies（强约束）

- `scenario.json` 顶层必须允许并优先产出 `dependencies` 数组。
- 可复用登录动作必须沉淀到 `dependencies`（如 `dep_login_admin`），不要在每条 case 的 `步骤` 里重复写登录。
- case 通过以下字段引用依赖：
  - `前置依赖`：`dep_login_admin`
  - `注入方式`：`Authorization: Bearer DEP:dep_login_admin.token`
  - `依赖产出提取`：如 `token=$.data.token`
- 仅当场景本身是“登录接口测试/重登/切换账号”时，才保留登录动作在 `步骤`。

### 场景ID 编号规则（新增）

- `场景ID` 统一使用纯数字字符串序号：`"1"`, `"2"`, `"3"` ...（按输出顺序递增）。
- 不再使用 `SCN-001`、`SCN-U-001` 等编码格式。
- 若已有历史场景使用编码格式，更新或重生成时应重排为连续数字序号。

## 造数与生命周期规则（强约束）

- 场景编排默认分三层：`造数/准备` -> `验证` -> `清理`。
- 禁止在中间验证阶段销毁后续仍需复用的实体（如用户、商品、订单）。
- 每个场景应在 `前置条件` 或 `备注` 写清最小依赖：来源实体、消费接口、回收时机。
- 破坏性操作（`DELETE`、终态流转如 `DONE/CANCELLED`）默认放末尾，或放在独立清理场景。
- 若必须跨场景复用实体，需显式写出“由哪个场景产出、由哪个场景消费”，避免隐式依赖。
- 造数命名要可重复执行：建议 `前缀_日期或批次_序号`，避免重复用户名导致 400。
- 禁止把真实账号密码写入场景文档；敏感值统一走环境变量方案。

推荐在场景文本中追加一行（可放 `备注`）：

- `数据依赖说明：依赖 场景1 产出的 productId；本场景不做删除，统一由 场景99 清理`

## 工作流

1. 读取接口文档（Markdown/OpenAPI）并抽取业务链路。
2. 产出或维护 `docs/<name>_scenario.json`（先写 `单接口`，再补 `串联`）。
   - `单接口`：覆盖文档中所有模块的 CRUD、负向与边界。
   - `串联`：覆盖主流程、逆流程、清理流程，明确数据产出与消费关系。
3. 先归一化 `scenario.json` 依赖结构（自动抽取重复登录到顶层 dependencies）：
   - `python .cursor/skills/api-scenario-generator/scripts/normalize_scenario_dependencies.py -i docs/<name>_scenario.json`
4. 生成场景 Excel：
   - `python .cursor/skills/api-scenario-generator/scripts/scenario_json_to_excel.py -i docs/<name>_scenario.json -o docs/<name>_scenario.xlsx`
5. 回报场景数与输出文件路径。

## 通用覆盖模板（跨项目）

对任意接口文档，按“资源模块”逐个套用以下最小覆盖模板（不绑定具体路径名）：

- 查询类（Read）
  - 列表查询：成功返回列表/分页结构
  - 详情查询：资源存在成功；资源不存在失败（如 404/业务码）
  - 若文档有权限/归属限制：补充越权或跨租户负向
- 创建类（Create）
  - 成功创建：关键返回字段可校验（主键、状态、时间戳等）
  - 参数负向：必填缺失、类型错误、枚举非法、重复创建冲突
  - 数值边界：`0`、负数、最小合法值、超限（按文档约束选择）
- 更新类（Update）
  - 成功更新：仅更新指定字段，其余字段保持不变
  - 参数负向：非法状态流转、非法字段值、资源不存在
  - 并发/版本控制（若有）：版本冲突或幂等更新校验
- 删除类（Delete）
  - 可删成功：删除后再查询应不存在
  - 不可删约束：被引用、状态不允许、库存/余额不满足等业务冲突
  - 重复删除：再次删除的幂等或错误码行为

生成顺序建议：

1. 先生成 `场景类型=单接口`，按上面模板补齐 CRUD + 负向 + 边界。
2. 再生成 `场景类型=串联`，覆盖主流程、逆流程、清理流程，并写清数据依赖关系。

## 快速命令

```bash
# 场景 JSON -> 场景 Excel
python .cursor/skills/api-scenario-generator/scripts/scenario_json_to_excel.py -i docs/user_scenario.json -o docs/user_scenario.xlsx
```

一键执行（推荐）：

```bash
python .cursor/skills/api-scenario-generator/scripts/run_scenario_pipeline.py -n user
```

说明：`-n user` 会按 `docs/user_scenario.json -> docs/user_scenario.xlsx` 执行。

## 验收清单

- 同一份接口文档可产出：场景 JSON + 场景评审 Excel
- 场景列模板稳定（列顺序与命名稳定）
- 单接口覆盖中可看到更新、查询、删除相关场景（不只主流程）
- 至少一条场景能清晰体现“先 A 后 B/再 C”的接口串联

## 注意事项

- 若 `*_scenario.xlsx` 被本机 Excel 占用导致无法覆盖，脚本会写入 `*_scenario_generated.xlsx`。
- 本 skill 不负责生成执行用例文件（如 `cases.json`、`mapping_issues.md`、`cases.xlsx`）。
- 不要写入真实账号密码，敏感数据使用环境变量方案。
