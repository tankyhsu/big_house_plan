# Portfolio System UI

一个基于 FastAPI + React(antd) 的投资组合可视化与管理界面。
后端使用 SQLite 存储，支持：类别/标的映射、交易流水、每日快照、技术指标、历史信号（止盈/止损）与操作日志；
前端包含 Dashboard、复盘、持仓管理、交易录入、信号分析、设置等页面，支持K线图信号标注。

---

## 快速开始

前置要求：Python 3.10+、Node.js 18+/20+、npm 9+

```bash
# macOS / Linux（或 Windows 下的 Git Bash / WSL）
bash scripts/dev.sh
```

- 前端开发地址：http://127.0.0.1:5173
- 后端 API 文档：http://127.0.0.1:8000/docs

快速启动（跳过依赖安装）：

```bash
bash scripts/dev-fast.sh
```

---

## 手动运行

```bash
# 后端
python -m venv .venv
source .venv/bin/activate    # Windows(Git Bash): source .venv/Scripts/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
uvicorn backend.api:app --reload --port 8000

# 前端
cd frontend
npm i
echo "VITE_API_BASE=http://127.0.0.1:8000" > .env   # 首次
npm run dev
```

---

## 目录结构

```
.
├── backend/                  # FastAPI 后端
│   ├── api.py                # 路由 & 接口定义
│   ├── services/             # 业务逻辑（calc/pricing/analytics/position/txn 等）
│   ├── repository/           # DB 读写封装
│   ├── providers/            # 第三方数据源（TuShare 包装）
│   ├── domain/               # 领域模型/交易引擎
│   ├── scripts/              # 后端维护脚本
│   ├── tests/                # pytest 测试
│   ├── logs.py               # 操作日志（operation_log 表）
│   └── db.py                 # SQLite 连接与路径解析
├── frontend/                 # React + Vite + TypeScript 前端
│   ├── src/
│   │   ├── pages/            # Dashboard / 复盘 / 持仓管理 / 交易 / 设置
│   │   ├── components/       # 图表与通用组件（ECharts K 线、指标等）
│   │   ├── api/              # 前端 API 客户端与类型
│   │   └── utils/            # 工具函数
│   └── vite.config.ts
├── scripts/                  # 启动脚本（bash）
│   ├── dev.sh
│   └── dev-fast.sh
├── seeds/                    # CSV 种子数据（categories/instruments）
├── schema.sql                # 数据库结构
├── requirements.txt          # 后端依赖
├── config.yaml               # 本地配置（dev.sh 首次会生成）
├── portfolio.py              # 可选：CLI 工具（初始化/同步/计算/报表）
└── README.md
```

---

## 配置说明（config.yaml）

`bash scripts/dev.sh` 首次运行会在项目根生成默认 `config.yaml`。

- db_path: SQLite 文件路径（默认 `./backend/data/portfolio.db`）
- unit_amount, stop_gain_pct, overweight_band, ma_short, ma_long, ma_risk
- tushare_token: TuShare 令牌（留空则跳过价格同步）
- cash_ts_code: 现金镜像用代码（默认 `CASH.CNY`）
- tushare_fund_rate_per_min: TuShare 基金接口限速（每分钟最大调用数）

高级：也可通过环境变量 `PORT_DB_PATH` 覆盖数据库路径；当 `APP_ENV=test` 或处于 pytest 运行时会优先读取 `test_db_path`。

---

## 常用 API（后端）

- 健康检查：`GET /health`
- Dashboard 概览：`GET /api/dashboard?date=YYYYMMDD`
- 聚合 KPI：`GET /api/dashboard/aggregate?start=YYYYMMDD&end=YYYYMMDD&period=day|week|month`
- K 线数据与详情：`GET /api/instrument/detail?ts_code=...`
- 历史信号查询：`GET /api/signal/all?type=...&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- 交易流水：`GET /api/txn/list`、`GET /api/txn/range?start=...&end=...`
- 导入种子：`POST /api/seed/load { categories_csv, instruments_csv }`
- 同步价格（TuShare）：`POST /api/sync-prices { date?:YYYYMMDD, recalc?:bool }`
- 重算快照与信号：`POST /api/calc { date:YYYYMMDD }`
- 操作日志查询：`GET /api/logs/search`

完整接口可在 http://127.0.0.1:8000/docs 查看。

---

## 初始化与数据准备

方式 A：通过 API 导入种子（推荐）

```bash
curl -X POST 'http://127.0.0.1:8000/api/seed/load' \
  -H 'Content-Type: application/json' \
  -d '{"categories_csv":"seeds/categories.csv","instruments_csv":"seeds/instruments.csv"}'
```

方式 B：使用 CLI（可选）

```bash
python portfolio.py init              # 初始化 schema 并导入 seeds
python portfolio.py sync-prices      # 需要在 config.yaml 配置 tushare_token
python portfolio.py calc -d 20250101 # 重算指定交易日
```

---

## 前端功能

- **Dashboard**：资产概览、类别分布、持仓表、资产曲线，实时显示最新信号
- **复盘分析**：多标的对比、标准化/指数化曲线，支持时间范围选择
- **信号分析**：历史交易信号汇总，支持时间范围和信号类型筛选，默认显示近一个月
- **持仓详情**：单标的K线图，集成信号标注（止盈/止损），交易记录查询
- **持仓管理**：期初持仓设置、手动调整、清理零持仓，IRR计算
- **交易记录**：流水查询与录入，支持批量导入
- **设置**：系统配置（阈值、TuShare Token、现金镜像等）

### 信号系统特性
- **历史信号记录**：信号与首次出现日期严格匹配，非每日快照
- **智能去重**：避免重复计算生成相同信号
- **K线图集成**：信号在K线图上智能定位，止盈显示在高点上方，止损显示在低点下方
- **时间筛选**：默认显示近期有操作价值的信号，支持自定义时间范围

---

## 测试与质量

- 后端测试：在项目根运行 `pytest`（目录：`backend/tests/`）
- 前端 ESLint：`cd frontend && npm run lint`
- 最近验证（Python 3.13.7，pytest 8.3.2）：`pytest` 全部 90 项测试通过
  - FastAPI `@app.on_event` 在 0.111+ 版本起已弃用，可后续迁移至 lifespan hooks
  - Pydantic 2.x 中 `.dict()` 将被移除，建议按需替换为 `model_dump()`
  - Pandas 对 `fillna` 的类型降级行为将调整，可通过 `infer_objects` 或 `future.no_silent_downcasting` 选项提前适配

---

## 注意事项

- 令牌等敏感信息仅保存在本地 `config.yaml`，不要提交到仓库。
- 前端后端通过 `frontend/.env` 的 `VITE_API_BASE` 指定后端地址。
- 数据库路径可在 `config.yaml` 中通过 `db_path` 配置，避免提交本地 DB 文件。

---

## License

私有项目，勿外传。
