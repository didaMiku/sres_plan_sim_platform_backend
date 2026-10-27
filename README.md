# 友好型源网荷储一体化规划配置仿真平台（可视化部分）

课程设计项目。前后端分离：

| 仓库 | 技术栈 | 说明 |
|---|---|---|
| 本仓库（backend） | Python 3.13 + FastAPI + SQLite + pandas | 业务接口、数据清洗入库、数据字典 |
| `sres_plan_sim_platform_frontend` | Vue 3 + TypeScript + Vite | 页面与交互 |

---

## 一、需求分析

### 1.1 任务来源

任务书题目：**友好型源网荷储一体化规划配置仿真平台（可视化部分）**。

背景：双碳目标与新型电力系统建设下，园区、数据中心、绿色燃料基地等场景需要做"源（风电、光伏）—网（外部电网）—荷（负荷）—储（储能）"的协同规划。传统做法依赖人工经验与静态估算，难以处理新能源波动性、负荷时序特性、储能调节能力和多目标约束。

任务书把系统描述为 5 个子平台：数据管理、仿真计算、优化决策、方案评价、报告输出。但题目括号里限定了**（可视化部分）**，三张参考效果图也只覆盖三类界面，因此本项目范围界定为：

| 子平台 | 本次是否实现 |
|---|---|
| 数据管理（上传、校验、映射、入库、历史） | ✅ 实现 |
| 可视化（项目仪表盘、运行曲线、指标展示） | ⏳ 界面已完成，图表待接 |
| 报告输出（模板、章节、预览、导出） | ⏳ 界面已完成，生成待做 |
| 仿真计算 / 优化决策（数学规划求解） | ❌ 待定 |

### 1.2 功能范围

1. **登录与会话**：管理员账密登录、Cookie 会话、当前登录状态查询、退出登录。
2. **项目管理**：项目列表、进入项目。
3. **数据导入**：
   - 左侧选数据类型 → 上传 csv/xlsx → 前端读表头 → 用户逐列选择对应数据库字段 → 提交；
   - 后端按映射改名、清洗、UPSERT 入库，原始文件留存，写入导入记录。
4. **导入历史**：按管理员查询最近导入记录（文件名、类型、行数、时间、状态）。

### 1.3 数据资产

数据目录 `源网荷储一体化仿真数据/`（10 个文件）：

| 文件 | 用途 | 是否已入库 |
|---|---|---|
| `01_项目基础数据.xlsx` | 项目名称、区域、规划年份、现状装机 | 手工录入 `project_list` |
| `02_设备技术参数.xlsx` | 风机/光伏/储能的运行参数 | 手工录入 `t_param`(device) |
| `03_小时级源荷气象电价数据.csv` | 5832 小时：风速、辐照、温度、负荷、电价 | ✅ 可导入 `t_source` |
| `04_典型日15分钟运行曲线.csv` | 96 点典型日：光伏可用出力、负荷 | ✅ 可导入 `t_typical_day`（需先补日期列） |
| `05_风光负荷同步出力数据.csv` | 5832 小时、14 列运行仿真结果 | ✅ 可导入 `t_simulation` |
| `06_容量优化与评价结果.xlsx` | 优化方案容量与指标 | 手工录入 `t_param`(result) |
| `07_华东分时电价数据.xlsx` | 谷/平/峰时段电价 + 上网电价 | 手工录入手 `t_tariff`（24 行） |
| `08_经济成本参数.xlsx` | CAPEX、折现率、碳价 | 手工录入 `t_param`(cost) |
| `09_容量配置及评价指标.xlsx` | 另一套容量指标 | 手工录入 `t_param`(indicator) |
| `10_数据说明.docx` | 数据范围与功率平衡公式 | 参考文档 |

数据核查中发现的问题（已记录，实现时按约定处理）：

- `03` 与 `05` **不是输入-输出关系**：风速 5829/5832 行不同、负荷全不同，两套数据独立生成；
- `03` 的电价只有 3 档（0.32 / 0.45 / 0.85），与 `07` 的 4 段电价（0.35 / 0.75 / 1.15）不一致；
- `06`（风 80 / 光 120）与 `09`（新能源 130）是两套口径，不能混用；
- `04` 只有 `00:00~23:45`，没有日期，入库前需补成 `2026-07-15` 起的时间戳。

---

## 二、总体设计

### 2.1 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Vue Router + Pinia | 任务书指定 Vue 3；TS 提供类型检查 |
| 后端 | Python 3.13 + FastAPI | 与 pandas 数据分析生态天然契合；自动生成 Swagger 文档 |
| 数据处理 | pandas + openpyxl + SheetJS（前端读表头） | csv/xlsx 解析、清洗、UPSERT |
| 数据库 | SQLite（单文件） | 零部署、随仓库走；数据量小（万行级） |
| 会话 | HttpOnly Cookie + `admin_session` 表 | 比 JWT 简单，且可主动注销 |

### 2.2 架构

```
浏览器（Vue 3 + TS）
    │  fetch /api/*
    ▼
Vite dev server（5173）—— proxy 转发 ——▶ FastAPI（8000）
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    ▼                       ▼                       ▼
               routers/                services/                 db.py
          （路由与参数校验）       （业务逻辑与清洗）        （连接与 SQL）
                                                                  │
                                                                  ▼
                                                        data/app.db（SQLite）
                                                        data/raw/（上传原件）
```

约定：**前端不写业务计算**，只负责渲染与交互；**字段定义只有一份**——放在数据库的 `field_dict`，前端通过接口获取。

### 2.3 数据库（11 张表）

| 表 | 作用 |
|---|---|
| `admin` | 管理员账号 |
| `admin_session` | 登录会话（token、过期时间） |
| `project_list` | 项目级信息（名称、区域、年份、装机、描述） |
| `data_type` | 数据类型字典（4 类可上传的时序数据） |
| `field_dict` | 字段字典（字段名、中文名、单位、是否必填） |
| `import_record` | 导入历史（管理员、文件、行数、状态、时间） |
| `t_source` | 源荷气象：`ts, wind_speed, ghi, temperature, load_mw, buy_price` |
| `t_typical_day` | 典型日曲线：`ts, pv_available_mw, load_mw` |
| `t_simulation` | 运行仿真：`ts` + 13 个物理量列 |
| `t_tariff` | 分时电价：`hour(0~23), price, sell_price, period_name` |
| `t_param` | 参数表：`category, name, value, unit`（device / cost / result / indicator） |

设计要点：

- 时序表**以规范化时间戳为主键**（`TEXT`，`YYYY-MM-DD HH:MM:SS`），重复导入用 UPSERT 覆盖，天然幂等；
- 主键列显式写 `NOT NULL`——SQLite 的 `TEXT PRIMARY KEY` 不会自动非空，否则会以 `NULL` 主键插重复行；
- 其余列尽量少加约束（不用外键、少用 `NOT NULL`），把可靠性交给后端校验。

### 2.4 接口

已实现 6 个：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | 账密登录，签发 token 并写入 HttpOnly Cookie |
| GET | `/api/auth/me` | 查当前登录管理员（前端路由守卫用） |
| POST | `/api/auth/logout` | 删会话 + 清 Cookie |
| GET | `/api/schema/types` | 4 类数据类型 + 各自字段（下拉框数据来源） |
| POST | `/api/imports` | 上传文件 + 列映射 → 清洗 → UPSERT 入库 |
| GET | `/api/imports` | 当前管理员的导入历史 |

未实现（见第五节）：`/api/projects`、仪表盘数据、报告生成、tariff 导入。

### 2.5 数据导入流程

```
前端：选类型 → 选文件（读前 8KB 拿表头）→ 逐列选映射 → 提交 multipart
        │
        ▼
后端：校验类型 → 查 field_dict（合法字段 / 必填字段）→ 校验映射
      → 读文件（xlsx 用 pandas；csv 先 utf-8 再 gbk）
      → 按映射改名 → 时间戳规范化 → 数值转换
      → 必填字段为空的行丢弃（计数 dropped）→ 去重排序
      → 原件写入 data/raw/
      → 一个事务：UPSERT 目标表 + 写 import_record
        │
        ▼
返回：{"row_count": 5832, "dropped": 0, "table": "t_source"}
```

### 2.6 关键设计决策

| 决策 | 结论 | 原因 |
|---|---|---|
| 文件何时上传 | 用户点"确认导入"时才上传 | 避免用户中途放弃留下一堆无用文件 |
| 解析放前端还是后端 | 表头在前端读，完整数据在后端处理 | 前端要即时显示列名；清洗必须用 pandas |
| 时序数据存哪 | 存 SQLite，不存 CSV | 避免"库里一份、文件一份"两份真相 |
| 表怎么拆 | 按数据文件拆（一个文件一张表） | 分析场景基本对应单个文件，避免多表 JOIN |
| 密码/token | 明文存储 | 课程设计简化，且 token 本身是随机串 |
| 字段字典 | 存数据库，不写死在前端 | 改字段只改库，前端不用重新构建 |

---

## 三、已完成

### 3.1 数据库

- 11 张表建好（手工建表 + `sql/schema.sql` 保留 DDL）；
- 种子数据：`data_type` 4 行、`field_dict` 27 行、`t_param` 25 行、`t_tariff` 24 行、`project_list` 1 行。

### 3.2 后端

- 登录模块：3 个接口 + `admin`/`admin_session` 表 + Cookie 会话 + `current_admin` 鉴权依赖；
- 数据字典：`GET /api/schema/types`；
- 数据导入：`POST /api/imports`（支持 source / typical_day / simulation）、`GET /api/imports`；
- 清洗规则：时间戳多格式解析、数值转换、空值/必填行丢弃、同刻去重（保留最后）、按时间排序、UPSERT；
- 原始文件留存，命名 `{时间戳}_{随机8位}__{原文件名}`（含中文文件名解码与非法字符清洗）。

### 3.3 前端

- 5 个页面 + 路由：`/login`、`/projects`、`/projects/:id/dashboard`、`/projects/:id/imports`、`/projects/:id/reports`；
- 登录页：调接口、错误提示、登录后跳转；
- 路由守卫：未登录访问内部页面跳登录页，登录后回跳；
- 数据导入页：
  - 左侧类型列表（来自接口）、右侧上传区；
  - 支持 csv/xlsx（SheetJS 读表头）；
  - 列映射表格（源列名、样例值、目标字段下拉），必填校验；
  - 提交 multipart，成功/失败提示；
  - 底部"最近导入"列表（来自 `GET /api/imports`）；
- 仪表盘：3 个 KPI、5 个图区、6 张指标卡（**数据为示例值，图表为占位**）；
- 报告页：4 个模板、13 个章节勾选、A4 预览区（**占位**）；
- `vite.config.ts` 配置 `/api` 代理到 8000，避免跨域 Cookie 问题。

### 3.4 实测结论

- 三个数据文件全部导入成功：`03` → 5832 行、`04` → 96 行、`05` → 5832 行；
- `tariff` 请求按约定返回 400「该类型暂未支持」；
- SQLite 以 5832 行 × 14 列实测：批量写 0.015 s、读回 0.017 s、按月聚合 0.003 s。

---

## 四、待完成

| # | 事项 | 说明 |
|---|---|---|
| 1 | `GET /api/projects` | `project_list` 已建表，接口未做；前端项目卡片仍写死 |
| 2 | 仪表盘数据接口 | `/api/dashboard/*`：KPI、曲线序列；前端图表当前是占位框 |
| 3 | ECharts 图表 | 按参考效果图实现 5 个图（风电/光伏/电力平衡/储能/友好性雷达） |
| 4 | 报告生成 | 模板 + 章节 → 生成 docx（python-docx），前端预览与下载 |
| 5 | `tariff` 导入 | 需特殊逻辑：「时段 → 24 小时」展开，不能走通用映射流程 |
| 6 | 数据预览 | 已导入数据的表格预览与分页 |
| 7 | 指标计算 | 消纳率、绿电占比、LCOE、峰值削减率等（口径见需求分析文档） |
| 8 | 参数类数据展示 | `t_param` 目前只是入库，前端没有展示页面 |

---

## 五、运行方式

### 5.1 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

- 接口文档：http://127.0.0.1:8000/docs
- 默认账号：`admin / 1234`
- 数据库文件：`data/app.db`（首次运行需执行 `sql/schema.sql` 建表，当前为手工建表）

### 5.2 前端

```bash
cd frontend
npm install
npm run dev
```

http://localhost:5173 ，`/api` 请求由 Vite 代理到 8000。

---

## 六、目录结构

```
backend/
├── app/
│   ├── main.py            入口：建应用、挂中间件、注册路由
│   ├── db.py              数据访问层：连接、SQL、字典查询
│   ├── models.py          Pydantic 请求/响应模型
│   ├── security.py        Cookie 鉴权依赖
│   ├── routers/
│   │   ├── auth.py        登录 / 当前用户 / 退出
│   │   ├── schema.py      数据类型与字段字典
│   │   └── imports.py     上传导入 / 导入历史
│   └── services/
│       ├── auth_service.py    登录业务
│       └── imports_service.py 文件解析、清洗、UPSERT
├── sql/schema.sql         建表脚本
├── data/
│   ├── app.db             SQLite 数据库
│   └── raw/               上传原件
├── requirements.txt
└── README.md
```

---

## 七、约定

- 时间戳统一 `YYYY-MM-DD HH:MM:SS`（TEXT 存储，字符串序即时间序）；
- 单位不写进列名，统一放 `field_dict.unit`，由前端拼接展示；
- 错误统一用 HTTP 状态码表达：400 参数/业务错误，401 未登录，422 校验失败，500 服务异常；
- 数据导入只做「覆盖」（UPSERT），不做版本管理；原始文件是唯一的回溯手段。
