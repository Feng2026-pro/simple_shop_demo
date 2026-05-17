---
name: api-test-report
description: Generate and open Allure reports from existing allure-results. If Allure CLI is not installed, guides the user to install it. Use when the user wants to view Allure report, open allure results, serve allure, or generate report from allure-results.
---

# Allure 报告查看

根据已生成的 **allure-results** 数据生成并打开 Allure 报告。若用户未安装 Allure CLI，则引导安装。

## 工作流

1. **检查 Allure 是否已安装**：在项目根目录执行 `allure --version`（或使用本 skill 的 `scripts/serve_report.py` 检测）。若命令不存在，进入「未安装时的引导」。
2. **执行报告（默认直接启动）**：若已安装 Allure CLI，默认在项目根目录直接执行：
   - `allure serve allure-results`（会临时起服务并打开浏览器）
3. 若用户明确只需生成不打开，再执行：
   - `allure generate allure-results -o allure-report --clean`

## 未安装时的引导

若检测到未安装 Allure CLI，**不要直接修改环境**，仅给出安装指引：

- **macOS（推荐）**：`brew install allure`
- **其他方式**：见 [references/install.md](references/install.md)，或官方文档 https://docs.qameta.io/allure/

并说明：安装完成后在项目根目录执行 `allure serve allure-results` 即可查看报告。

## 入口脚本（可选）

本 skill 提供脚本用于检测 Allure 并执行报告：

```bash
# 在项目根目录执行；若未安装会打印安装指引并退出
python .cursor/skills/api-test-report/scripts/serve_report.py [--no-open]
```

- 无 `--no-open`：若已安装 Allure，默认直接 `allure serve allure-results`（会打开浏览器）。
- 有 `--no-open`：仅执行 `allure generate`，输出到 `allure-report/`。

结果目录默认为项目根目录下的 `allure-results`；若不存在，脚本提示先运行测试生成数据。

## 与 api-test-runner 的关系

- **api-test-runner**：执行 CSV 用例（pytest），并写入 `allure-results`，可选在结束后调用 Allure 生成/打开报告。
- **本 skill**：不执行测试，仅根据**已有**的 `allure-results` 生成/打开报告；并在未安装 Allure 时负责引导用户安装。

## 资源

- **安装指引**：[references/install.md](references/install.md)
- **脚本**：[scripts/serve_report.py](scripts/serve_report.py)
