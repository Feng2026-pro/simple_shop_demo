---
name: api-test-config
description: 辅助用户维护 config/.env 配置。根据用户描述整理前置依赖所需变量，并默认补齐 DB 断言环境变量模板。适用于 CSV 接口测试前置依赖变量梳理、登录接口非 /auth/login、以及 JSON plan 的 db_assert 场景。
---

# 前置依赖与环境配置助手

辅助用户维护 `config/.env`，聚焦前置依赖所需变量与 DB 断言开关。  
**本 skill 不生成 `config/.env.example`。**

## 何时使用

- 用户要配置/新增前置依赖（登录、获取 tenant token 等）
- 登录或其它前置接口路径不是默认的 `/auth/login`
- 用户希望启用/关闭 JSON plan 中的 `db_assert`，并补齐 DB 连接环境变量

## 工作流

1. **获取信息**：从用户处获取前置接口信息（可来自接口文档或用户描述）：
   - 接口路径（如 `/api/v2/signin`、`/sso/login`）
   - 请求方法（GET/POST 等）
   - 请求体字段（如 username、password；敏感信息用环境变量）
   - 响应中需要提取的字段及 JSONPath（如 token 在 `data.accessToken` → `$.data.accessToken`）
2. **前置依赖变量梳理**：根据登录/前置接口信息，整理所需环境变量键名（如 `LOGIN_USER`、`LOGIN_PASS`、`ADMIN_USER`、`ADMIN_PASS`）。
3. **配置 .env**：
   - 路径：项目根目录下的 `config/.env`。
   - 必须包含 `BASE_URL`（示例值如 `http://localhost:11011`，可带简短注释）。
   - 根据本次梳理出的前置依赖变量（如 `LOGIN_USER`、`LOGIN_PASS`、`ADMIN_USER` 等），在 `.env` 中列出对应键与值（避免写入真实生产密码）。
   - 若文件不存在则创建；若已存在则合并：只新增当前场景用到、且 `.env` 里尚未存在的变量，并保留原有注释与顺序；避免覆盖用户已有敏感配置。
  - 默认补齐 DB 断言变量模板（即使用户本轮未显式提及 DB），默认关闭，后续可按需开启 `db_assert`：
    - `DB_ASSERT_ENABLED=false`
     - `DB_HOST`、`DB_PORT`、`DB_NAME`、`DB_USER`、`DB_PASS`
     - `DB_CHARSET=utf8mb4`
4. **提醒用户**：
   - 已在 `config/.env` 中配置了本次依赖所需变量，请按实际环境调整并注意不要提交敏感信息。
   - 若 JSON plan 含 `db_assert`：仅当 `DB_ASSERT_ENABLED` 非 `false` 且 `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASS` 完整时才会执行 DB 断言，否则自动跳过。

## 输出约定

- 仅输出并维护环境变量相关内容（`.env`）。
- DB 变量统一放在 `config/.env`。

## 资源

