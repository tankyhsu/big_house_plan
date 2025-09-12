# 系统架构总览

## 技术栈
- **Backend**: Python + FastAPI + SQLite + pandas
- **Frontend**: React + TypeScript + ECharts + Ant Design
- **Testing**: pytest
- **Development**: uvicorn + Vite

## 核心业务流程
1. **交易录入** → 持仓计算 → 投资组合快照
2. **价格同步** → 自动重算所有受影响日期的指标
3. **信号生成** → 基于持仓阈值和技术分析

## 后端架构 (`backend/`)

### 严格分层结构
```
backend/
├── api.py                 # FastAPI入口，路由注册
├── routes/               # API层：HTTP处理
├── services/            # Service层：业务逻辑
├── repository/          # Repository层：数据访问
├── domain/              # 领域层：核心业务实体
├── providers/           # 外部服务集成
└── db.py               # 数据库连接管理
```

### 关键Service模块
- `calc_svc.py` - 投资组合计算和重平衡
- `pricing_svc.py` - 价格同步（TuShare集成）
- `signal_svc.py` - 交易信号生成（含ZIG信号）
- `dashboard_svc.py` - Dashboard数据聚合
- `txn_svc.py` - 交易处理
- `position_svc.py` - 持仓管理

### 数据库设计
- **SQLite** 存储，结构定义在 `schema.sql`
- 关键表：`instruments`, `categories`, `positions`, `transactions`, `portfolio_daily`, `price_eod`, `signal`
- 种子数据：`seeds/categories.csv`, `seeds/instruments.csv`

## 前端架构 (`frontend/src/`)

### 页面结构
- `pages/` - 主要功能页面
  - Dashboard - 总资产概览和持仓分析
  - Review - 复盘分析和历史走势
  - Signals - 交易信号管理
  - Txn - 交易流水录入和查看
  - Settings - 系统配置

### 组件体系
- `components/charts/` - 专业金融图表（K线图、技术指标等）
- 通用组件：KpiCards, PositionTable, SignalTags等
- API集成：React Query + TypeScript客户端

### K线图模块化架构
- 拆分为8个专业模块：布局、价格序列、交易标记、信号处理、技术指标、工具提示、图例构建
- 支持多种技术指标：MACD、KDJ、BIAS、移动平均线
- ZIG信号特殊处理：结构信号9天倒计时功能

## 核心业务模块

### 交易引擎 (`domain/txn_engine.py`)
- 支持复杂企业行为：股票分割、股息、费用处理
- 精确成本计算：加权平均 + 已实现损益
- 现金镜像交易：非现金工具的现金流追踪

### 价格同步系统
- **增强功能**：自动检测并补齐过去N天缺失的价格数据
- TuShare API集成：支持股票、ETF、基金、港股
- 智能重算：价格更新后自动重算受影响日期

### 信号系统
- **结构信号**：基于持仓阈值的买卖提醒
- **ZIG信号**：通达信ZIG(3,10)算法实现，84.6%准确率
- **手动信号**：支持多种范围创建（单个标的/类别/全部）

## 开发和部署

### 快速启动
```bash
# 完整环境
bash scripts/dev.sh

# 快速启动（已安装依赖）
bash scripts/dev-fast.sh
```

### 测试
```bash
# 后端测试
pytest

# 前端检查
cd frontend && npm run lint
```

### 配置管理
- `config.yaml` - 主配置文件（数据库路径、TuShare令牌等）
- `frontend/.env` - 前端环境变量
- 环境变量 `PORT_DB_PATH` 可覆盖数据库位置