# Simple Shop Demo

一个基于 Python Flask 的简易商城演示项目，用于接口测试用例生成和自动化测试实战。

## 项目概述

本项目是一个轻量级的电商后端演示系统，包含商品管理、订单处理、库存管理等核心功能。主要用于学习和实践接口自动化测试。

## 技术栈

- **语言**: Python 3.x
- **框架**: Flask 3.0.3
- **数据库**: SQLite
- **测试工具**: pytest, Allure

## 项目结构

```
simple_shop_demo/
├── simple_shop_demo/           # 主应用代码
│   ├── app.py                 # Flask 应用入口
│   └── clear_db.py            # 数据库清理脚本
├── docs/
│   └── api/
│       └── api-docs-simple-shop-demo.md  # API 接口文档
├── .trae/skills/              # 测试技能工具集
│   ├── api-doc-generator/     # API 文档生成器
│   ├── api-test-generator/    # 测试用例生成器
│   ├── api-test-runner/       # 测试执行器
│   ├── api-test-report/       # 测试报告生成器
│   ├── api-scenario-generator/# 场景测试生成器
│   ├── api-test-config/       # 测试配置管理
│   └── jmx-test-generator/    # JMeter 测试脚本生成器
├── test_plan.jmx              # JMeter 测试计划
├── allure-results/            # Allure 测试结果
├── allure-report/             # Allure 测试报告
└── README.md                  # 项目说明文档
```

## 快速开始

### 安装依赖

```bash
cd simple_shop_demo
pip install flask pytest pytest-allure-adaptor requests
```

### 启动服务

```bash
cd simple_shop_demo
python app.py
```

服务默认运行在 `http://127.0.0.1:5000`

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | / | 获取商品列表 |
| GET | /add_product | 展示新增商品表单 |
| POST | /add_product | 创建新商品 |
| GET | /order/{product_id} | 展示下单页面 |
| POST | /order/{product_id} | 提交订单 |
| GET | /orders | 查询订单列表 |

详细接口文档请参考: [docs/api/api-docs-simple-shop-demo.md](docs/api/api-docs-simple-shop-demo.md)

## 测试工具

### API 文档生成
```bash
# 扫描代码生成 API 文档
lark-cli api-doc-generator scan simple_shop_demo/
```

### 测试用例生成
```bash
# 从 API 文档生成测试用例
lark-cli api-test-generator doc-to-excel docs/api/api-docs-simple-shop-demo.md
```

### 执行测试
```bash
# 运行 API 测试
lark-cli api-test-runner run cases.xlsx
```

### 生成测试报告
```bash
# 生成 Allure 报告
lark-cli api-test-report serve
```

### JMeter 测试脚本生成
```bash
# 从 API 文档生成 JMX 脚本
lark-cli jmx-test-generator generate docs/api/api-docs-simple-shop-demo.md
```

## 数据模型

### products 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键自增 |
| name | TEXT | 商品名称 |
| price | REAL | 商品价格 |
| stock | INTEGER | 库存数量 |

### orders 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键自增 |
| product_name | TEXT | 商品名称 |
| quantity | INTEGER | 购买数量 |
| total_price | REAL | 订单总价 |
| create_time | TEXT | 创建时间 |

## 业务流程

1. **创建商品** → POST /add_product
2. **查看商品列表** → GET /
3. **下单购买** → POST /order/{product_id}
4. **查看订单** → GET /orders

## License

MIT License
