---
name: api-test-runner
description: Read user-specified JSON cases files, execute API tests via pytest, and generate Allure reports. This skill only runs tests and reports pass/fail with modification suggestions; it does not edit case content.
---

# JSON 计划驱动接口测试执行

读取用户指定的 **cases.json** 测试用例文件，执行 pytest 并生成 Allure 报告。支持前置依赖（如登录获取 token）和 case 内多步串联依赖（A->B->C）。

## 原则

- **仅关注执行**：本 skill 只负责读取 JSON 计划 → 执行测试 → 生成结果，不改写用例设计。
- **不修改用例内容**：不替用户修改 plan 中的请求体、断言、依赖；失败时只反馈结果与修改建议，由用户自行调整。
- **失败后仅建议**：执行失败时，禁止自动修复或重写计划文件。
- **禁止自动改参**：禁止自动改断言、请求体、路径参数、依赖引用、账号密码；仅输出可执行修复建议供用户决定。

## 输入方式

用户提供 JSON 用例路径（`cases.json`）。顶层包含 `dependencies` 与 `cases`。

## 工作流

### Step 1：读取用例（JSON）

- 读取 `cases.json` 顶层 `dependencies` / `cases`。
- 每个 case 必须满足 runner 结构约束（`request` 与 `steps` 互斥，二者至少其一存在；若有 `steps` 则 step 名唯一）。
- 仅执行 `enabled` 为真（空值默认真）的 case。

### Step 2：执行测试

- 通过 `pytest_generate_tests` 将每条 case 参数化到 `test_api_row`
- session 开始先执行 `dependencies`（支持 `depends_on` 拓扑排序）
- 执行时支持 `ENV:KEY`、`DEP:dep.field` 与 case 内 `STEP:step.field`
- `run_tests.py` 在项目根目录 chdir 后调用 pytest 执行本 skill 下的 `scripts/test_api.py`（同目录 `conftest.py` 提供 fixture 与结果写回）

### Step 3：输出结果并生成 Allure 报告

- 输出 pytest 与 Allure 执行结果（不回写计划文件）
- Allure 报告生成方式见下
- **使用本 skill 时**：执行完成后只做结果汇总与修改建议，不主动编辑用例文件（路径参数、请求体等）

```bash
allure generate allure-results -o allure-report --clean
allure serve allure-results  # 或直接打开查看
```

## 执行后输出

执行结束后应输出：

- **通过/失败汇总**：共 N 条，通过 M 条，失败 K 条；并列失败用例的用例ID与简要原因（如预期状态码 vs 实际状态码、响应摘要）。
- **修改建议**（若有失败）：根据失败原因给出具体建议，供用户自行修改用例或检查环境（例如「TC_010 预期 200 实际 404，接口按 UUID 查询用户，请将路径参数 id 改为环境中存在的用户 UUID」）。**不要**替用户编辑用例文件。

失败报告建议按以下结构输出：

- `失败用例ID`：定位具体 case/row。
- `预期 vs 实际`：状态码、关键断言、响应摘要。
- `根因判断`：账号错误、数据不存在、状态污染、断言语法不兼容、依赖缺失等。
- `修复建议`：只给建议，不落地修改。

建议分级：

- `高优先级（阻断）`：登录失败、依赖缺失、核心资源不存在。
- `中优先级（数据不稳定）`：跨用例污染、重复造数冲突、环境脏数据影响。
- `低优先级（断言优化）`：断言过严、字段比较方式不兼容、可读性改进。

## 入口脚本

```bash
python scripts/run_tests.py --cases-json <用例文件路径> [--base-url <url>] [--serve]
```

示例：

```bash
python scripts/run_tests.py -c docs/api_interface_cases.json --base-url http://localhost:11011 --serve
```

推荐与 `api-test-generator` 联用：先生成 `*_cases.json`（执行输入），同时导出 `*_cases.xlsx` 供人工查看/编辑。

## 配置

- **敏感信息**：账号密码请通过环境变量注入（变量名按你的依赖定义），避免写入计划文件明文
- **BASE_URL**：环境变量或 `--base-url` 参数
- **引用协议**：`ENV:KEY`、`DEP:depName.field`、`STEP:stepName.field`（整串或嵌入字符串，如 `Bearer DEP:auth.token`）

## 资源

- **Excel 派生格式参考**：[references/excel-format.md](references/excel-format.md)（仅用于 generator 导出结构说明）
- **实现位置**：本 skill 的 `scripts/` 下含 [conftest.py](scripts/conftest.py)（JSON 计划读取与依赖执行）与 [test_api.py](scripts/test_api.py)（用例逻辑），自包含，不依赖项目根 `tests/`
- **测试入口**：[scripts/run_tests.py](scripts/run_tests.py)
