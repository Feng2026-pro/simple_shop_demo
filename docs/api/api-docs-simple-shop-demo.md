# 接口文档（自动生成）

生成时间：2026-05-17T00:00:00Z  
项目：apiauto-demo2.0 / simple_shop_demo  
技术栈：Python Flask 3.0.3  
扫描范围：`simple_shop_demo/`

> **说明**：本服务为 Flask 服务端渲染（SSR）演示应用，多数接口返回 HTML 页面或通过表单提交后重定向，而非 JSON REST API。下文按 HTTP 路由统一描述，便于自动化测试与流程编排参考。

**默认 Base URL**：`http://127.0.0.1:5000`

---

## simple-shop-demo 简易商城

简易电商演示：商品维护、下单、库存扣减与订单查询。数据存储为 SQLite（`shop.db`）。

### GET /

**接口说明**  
获取商品列表页面，从数据库查询全部商品并渲染首页。

**所属控制器**  
`app.index`

**路径参数**  
（暂无）

**查询参数**  
（暂无）

**请求体**  
（无）

**响应**

- `200 OK`  
  Content-Type: `text/html`  
  渲染模板 `index.html`，上下文变量 `products` 为商品行列表（SQLite 查询结果元组）。

---

### GET /add_product

**接口说明**  
展示新增商品表单页面。

**所属控制器**  
`app.add_product`

**路径参数**  
（暂无）

**查询参数**  
（暂无）

**请求体**  
（无）

**响应**

- `200 OK`  
  Content-Type: `text/html`  
  渲染模板 `add_product.html`。

---

### POST /add_product

**接口说明**  
提交表单创建新商品，成功后重定向至首页。

**所属控制器**  
`app.add_product`

**路径参数**  
（暂无）

**查询参数**  
（暂无）

**请求体（Form）**

Content-Type: `application/x-www-form-urlencoded`

| 字段   | 类型    | 必填 | 说明     |
| ------ | ------- | ---- | -------- |
| name   | string  | 是   | 商品名称 |
| price  | number  | 是   | 商品价格 |
| stock  | integer | 是   | 库存数量 |

**响应**

- `302 Found`  
  重定向至 `/`。

---

### GET /order/{product_id}

**接口说明**  
根据商品 ID 展示下单页面（商品详情与下单表单）。

**所属控制器**  
`app.order`

**路径参数**

| 名称        | 类型    | 必填 | 说明    |
| ----------- | ------- | ---- | ------- |
| product_id  | integer | 是   | 商品 ID |

**查询参数**  
（暂无）

**请求体**  
（无）

**响应**

- `200 OK`  
  Content-Type: `text/html`  
  渲染模板 `order.html`，上下文变量 `product` 为单条商品记录。若商品不存在，`product` 可能为 `None`（源码未单独处理 404）。

---

### POST /order/{product_id}

**接口说明**  
用户下单：校验库存、扣减库存、写入订单表，成功后跳转订单列表；库存不足时返回纯文本错误。

**所属控制器**  
`app.order`

**路径参数**

| 名称        | 类型    | 必填 | 说明    |
| ----------- | ------- | ---- | ------- |
| product_id  | integer | 是   | 商品 ID |

**查询参数**  
（暂无）

**请求体（Form）**

Content-Type: `application/x-www-form-urlencoded`

| 字段     | 类型    | 必填 | 说明     |
| -------- | ------- | ---- | -------- |
| quantity | integer | 是   | 购买数量 |

**响应**

- `302 Found`  
  下单成功，重定向至 `/orders`。
- `200 OK`（业务失败）  
  Content-Type: `text/plain`  
  正文：`库存不足！`（当 `quantity > current_stock` 时）。

**副作用**  
更新 `products.stock`；向 `orders` 表插入记录（`product_name`, `quantity`, `total_price`, `create_time`）。

---

### GET /orders

**接口说明**  
查询全部订单（按 ID 降序）并展示订单列表页面。

**所属控制器**  
`app.orders`

**路径参数**  
（暂无）

**查询参数**  
（暂无）

**请求体**  
（无）

**响应**

- `200 OK`  
  Content-Type: `text/html`  
  渲染模板 `orders.html`，上下文变量 `orders` 为订单行列表。

---

## 数据模型（SQLite）

### products

| 字段  | 类型    | 说明     |
| ----- | ------- | -------- |
| id    | INTEGER | 主键自增 |
| name  | TEXT    | 商品名称 |
| price | REAL    | 单价     |
| stock | INTEGER | 库存     |

### orders

| 字段        | 类型    | 说明           |
| ----------- | ------- | -------------- |
| id          | INTEGER | 主键自增       |
| product_name| TEXT    | 商品名称快照   |
| quantity    | INTEGER | 购买数量       |
| total_price | REAL    | 订单总价       |
| create_time | TEXT    | 创建时间字符串 |

---

## 业务流程

1. 创建商品（`POST /add_product`）
2. 维护库存（新增时写入 `stock`）
3. 展示商品列表（`GET /`）
4. 用户下单（`POST /order/{product_id}`）
5. 库存扣减（下单成功时更新 `products.stock`）
6. 生成订单（写入 `orders` 表）
7. 查看订单（`GET /orders`）

---

## 扫描配置

| 项           | 值                          |
| ------------ | --------------------------- |
| scanRoot     | `simple_shop_demo/`         |
| language     | Python                      |
| framework    | Flask                       |
| sourceFiles  | `app.py`                    |
| endpointCount| 6（含同路径不同 HTTP 方法） |
