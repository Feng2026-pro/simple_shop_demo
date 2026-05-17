# Excel 新格式说明（2-sheet）

本文件仅用于说明 generator 导出的 Excel 结构（`.xlsx`）。  
`api-test-runner` 执行输入为 `cases.json`，不直接读取 Excel。

1. `dependencies`
2. `cases`

`steps` 与 `db_assert` 以内嵌 JSON 列方式放在 `cases` 中。

## dependencies sheet

| 列名 | 类型 | 说明 |
|------|------|------|
| name | 文本 | 依赖名称，唯一 |
| depends_on | 文本 | 逗号分隔的依赖名列表，可空 |
| method | 文本 | HTTP 方法 |
| path | 文本 | 接口路径，如 `/auth/login` |
| headers_json | JSON对象字符串 | 请求头 |
| body_json | JSON对象字符串 | 请求体 |
| assert_status | 数字 | 依赖预期状态码 |
| assert_checks | JSON数组字符串 | 依赖断言数组 |
| extract_json | JSON对象字符串 | 提取规则，如 `{"token":"$.data.token"}` |

## cases sheet

| 列名 | 类型 | 说明 |
|------|------|------|
| id | 文本 | case 唯一标识 |
| name | 文本 | case 名称 |
| enabled | 布尔/文本 | 是否执行；空值默认 true |
| case_assert_status | 数字 | case 末步预期状态码 |
| case_assert_checks | JSON数组字符串 | case 末步断言数组 |
| steps_json | JSON数组字符串 | 非空，元素为 step 对象（含 `name/request/assert/extract`） |
| db_assert_json | JSON数组字符串 | 可空；空按 `[]` 处理 |
| 运行结果 | 文本 | runner 写回 PASS/FAIL（自动新增） |
| 失败原因 | 文本 | runner 写回失败摘要（自动新增） |

## JSON 列约束

- `steps_json` 必须是合法 JSON 数组，且不能为空数组。
- `db_assert_json` 允许空单元格，按 `[]` 处理。
- `assert_checks`、`case_assert_checks` 建议写标准 JSON 数组，如 `["$.code==200"]`。
- 任一 JSON 列解析失败会 fail-fast，并定位到 `case_id + 列名`。

## 执行命令

```bash
python scripts/run_tests.py --cases-json docs/api_interface_cases.json --base-url http://localhost:11011
```
