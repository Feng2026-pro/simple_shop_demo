# 串联清单（chain manifest）说明（已废弃）

不再需要 manifest；`scenario -> cases.json` 由 Agent 按 [SKILL.md](../SKILL.md) 规则结合接口文档直接生成，不再提供场景转 plan 的自动化脚本。

生成 `cases.json` 后，若需 Excel，使用：

```bash
python3 .cursor/skills/api-test-generator/scripts/plan_json_to_excel.py \
  -i docs/<name>_cases.json \
  -o docs/<name>_cases.xlsx
```

## 迁移说明

- 旧流程：`scenario + manifest -> plan`
- 当前流程：`scenario` + 接口文档 → **Agent 产出 `cases.json`** →（可选）`plan_json_to_excel.py` → `cases.xlsx`

## 自动生成规则（摘要）

- 每个场景（`场景ID`）生成一个 case。
- 从场景「步骤」文本提取 `METHOD + PATH`，按出现顺序生成 steps。
- 若场景包含顶层 `dependencies`，优先继承并用于鉴权注入。
- 默认优先将登录写入 `dependencies`，并按用户复用（同一用户一条登录依赖）。
- 普通场景中的重复登录步骤会在生成 plan 时被去重并提升到 `dependencies`。
- 若涉及多个用户，允许生成多条登录 `dependencies`，按用户注入鉴权头。
- 除登录外步骤优先注入 `Authorization: Bearer DEP:<dependency_name>.token`。
- 特殊场景（校验登录本身/重登/切换账号/登录参数不一致）允许在 case 的 `steps` 内显式登录。
- 路径参数、请求体使用固定字面量示例值，不使用随机占位符。
- 每步与顶层断言默认包含 `status: 200` 与基础 `checks`。

## 备注

本文件保留用于说明历史概念。新的用例生成不再读取 chain manifest 文件。
