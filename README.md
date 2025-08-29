# Portfolio System UI

一个基于 **FastAPI + React(antd)** 的投资组合可视化与管理界面。  
后端使用 SQLite 存储，支持：类别/标的映射、交易流水、每日快照、信号（止盈/配置偏离）与详细操作日志。  
前端提供 Dashboard、持仓编辑、交易录入等页面。

---

## 快速开始（最简 3 步）

> 需要已安装：**Python 3.10+**、**Node.js 18+（或 20+）**、**npm 9+**。

```bash
# 克隆本仓库后，执行一键脚本（macOS/Linux）
bash scripts/dev.sh
# 或 Windows PowerShell
scripts\dev.ps1
```

打开前端开发地址：`http://127.0.0.1:5173`

> 后端 API 文档：`http://127.0.0.1:8000/docs`

---

## 日常开发快速启动（忽略依赖安装）

如果依赖已经安装过，可以直接运行以下脚本快速启动：

```bash
# macOS / Linux
bash scripts/dev-fast.sh
# Windows PowerShell
scripts\dev-fast.ps1
```

该脚本仅启动前后端，不会重新安装依赖或生成配置文件。

---

## 🧭 目录结构

```
.
├── backend/                # FastAPI 后端
│   ├── api.py              # 路由 & 接口定义
│   ├── services/           # 业务逻辑拆分（position, transaction, signal 等）
│   ├── repository/         # DB 访问与持久化
│   ├── analytics/          # 计算与分析逻辑
│   ├── logs.py             # 日志统一入口
│   └── db.py               # SQLite 连接与基础 CRUD
├── frontend/               # React + Vite + TypeScript 前端
│   ├── src/
│   │   ├── pages/          # 页面：Dashboard, Position, Trade ...
│   │   ├── components/     # 公共组件
│   │   ├── services/       # 前端 API 调用
│   │   └── ...
│   └── vite.config.ts
├── requirements.txt        # 后端依赖清单
├── package.json            # 前端依赖清单
├── scripts/                # 跨平台开发脚本
│   ├── dev.sh
│   ├── dev.ps1
│   ├── dev-fast.sh
│   └── dev-fast.ps1
├── seeds/                  # 种子数据（CSV）
├── IMPLEMENTATION_PLAN.md  # 实施/演进计划
└── README.md
```

---

## 依赖说明

### 后端（Python）
- **FastAPI**
- **uvicorn**
- **pydantic v2**
- **pandas**
- **PyYAML**

安装：
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

### 前端（Node）
- **Vite + React + TypeScript**
- **Ant Design v5**
- **axios**
- **dayjs**
- **echarts**
- **react-router-dom**

安装：
```bash
cd frontend
npm i
```

环境变量：
```
VITE_API_BASE=http://127.0.0.1:8000
```

---

## 运行

### 方式 A：一键脚本（推荐）
```bash
bash scripts/dev.sh          # macOS / Linux
scripts\dev.ps1             # Windows
```

### 方式 B：快速脚本（跳过依赖安装）
```bash
bash scripts/dev-fast.sh     # macOS / Linux
scripts\dev-fast.ps1        # Windows
```

### 方式 C：手动
```bash
# 后端
source .venv/bin/activate
uvicorn backend.api:app --reload --port 8000

# 前端
cd frontend
npm run dev
```

---

## 初始化数据

```bash
# 导入种子数据
curl -X POST 'http://127.0.0.1:8000/api/seed/load'   -H 'Content-Type: application/json'   -d '{"categories_csv":"seeds/categories.csv","instruments_csv":"seeds/instruments.csv"}'
```

---

## 前端页面

- Dashboard：资产概览、类别分布、持仓表
- 持仓编辑：直接修改底仓
- 交易：流水表 + 新增交易弹窗（支持新代码自动登记）

---

## License
私有项目，勿外传。
