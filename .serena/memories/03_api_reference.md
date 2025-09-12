# API接口参考

## 路由模块化架构
所有API按业务域组织在 `backend/routes/` 下，主入口 `api.py` 负责路由注册和CORS配置。

## 核心API接口

### Dashboard数据 (`dashboard.py`)
- `GET /api/dashboard?date=YYYYMMDD` - 投资组合概览
- `GET /api/dashboard/aggregate?start=&end=&period=` - KPI时序数据  
- `GET /api/category?date=YYYYMMDD` - 类别分布视图
- `GET /api/position?date=YYYYMMDD` - 持仓详情
- `GET /api/signal?date=YYYYMMDD` - 当日信号
- `GET /api/signal/all` - 历史信号查询
- `GET /api/series/position?start=&end=&ts_codes=` - 持仓时序数据

### 交易管理 (`transactions.py`)
- `GET /api/txn/list?page=&size=` - 分页交易列表
- `GET /api/txn/range?start=&end=&ts_codes=` - 范围查询
- `POST /api/txn/create` - 单笔交易创建（BUY/SELL/DIV/FEE/ADJ）
- `POST /api/txn/bulk` - 批量交易导入

### 价格同步 (`pricing.py`)
- `POST /api/sync-prices` - 单日价格同步
- `POST /api/sync-prices-enhanced` - **增强版**：自动检测缺失数据
- `GET /api/missing-prices?lookback_days=7` - 查询缺失价格
- `GET /api/price/last?ts_code=&date=` - 最新价格
- `GET /api/price/ohlc?ts_code=&start=&end=` - OHLC数据（K线图用）

### 信号系统 (`signals.py`)
- `GET /api/signals/current-status?date=` - 当前信号状态
- `GET /api/positions/status?date=&ts_code=` - 持仓状态
- `POST /api/signal/create` - 手动信号创建
- `POST /api/signal/rebuild-historical` - 重建历史信号
- `POST /api/signal/rebuild-structure` - 重建结构信号
- `GET /api/zig/signal/test` - ZIG信号测试
- `POST /api/zig/signal/validate` - ZIG信号验证

### 持仓管理 (`positions.py`)
- `GET /api/position/raw` - 原始持仓数据
- `POST /api/position/opening` - 设置期初持仓
- `POST /api/position/update` - 持仓更新
- `POST /api/position/delete` - 删除持仓

### 参考数据 (`reference_data.py`)
- `GET /api/category/list` - 类别列表
- `POST /api/category/create` - 创建类别
- `GET /api/instrument/list?q=&active_only=` - 标的搜索
- `GET /api/instrument/get?ts_code=` - 标的详情
- `POST /api/instrument/create` - 标的创建/更新
- `POST /api/seed/load` - 加载种子数据

### 系统配置 (`settings.py`)
- `GET /api/settings/get` - 获取配置（敏感数据脱敏）
- `POST /api/settings/update` - 更新配置

### 数据分析 (`analytics.py`)
- `GET /api/position/irr?ts_code=&date=` - 单标的IRR计算
- `GET /api/position/irr/batch?date=` - 批量IRR计算

### 数据维护 (`maintenance.py`)
- `POST /api/backup` - 业务数据备份
- `POST /api/restore` - 数据恢复
- `POST /api/calc` - 触发重算

### 监控和日志 (`logs.py`)
- 操作日志查询和追踪接口

## API设计规范

### 日期格式
- 统一使用 `YYYYMMDD` 格式
- 前端查询参数保持一致

### 响应结构
```json
{
  "success": true,
  "data": {...},
  "message": "操作成功"
}
```

### 错误处理
- 标准HTTP状态码
- 结构化错误信息
- 操作日志记录

### 重算触发
- 所有写操作自动触发相关日期的重算
- 支持 `recalc` 参数控制重算行为
- 智能依赖分析，只重算必要的日期

## 前端集成
- React Query hooks提供类型安全的API调用
- 统一的错误处理和加载状态管理
- 自动缓存和数据同步