# 前端页面标题到文件映射

## 页面路由与文件对应关系

| 路由路径 | 页面标题/功能 | 文件路径 | 导航菜单标题 |
|---------|--------------|----------|-------------|
| `/` | Dashboard / 仪表板 | `frontend/src/pages/Dashboard.tsx` | Dashboard |
| `/review` | 复盘分析 | `frontend/src/pages/Review.tsx` | 复盘分析 |
| `/signals` | 历史交易信号 | `frontend/src/pages/Signals.tsx` | 交易信号 |
| `/positions` | 持仓编辑 | `frontend/src/pages/PositionEditor.tsx` | 持仓编辑 |
| `/instrument/:ts_code` | 标的详情 | `frontend/src/pages/InstrumentDetail.tsx` | (详情页，无菜单) |
| `/txn` | 交易流水 | `frontend/src/pages/Txn.tsx` | 交易记录 |
| `/settings` | 系统配置 | `frontend/src/pages/Settings.tsx` | 系统设置 |

## 页面详细描述

### Dashboard (仪表板)
- **文件**: `frontend/src/pages/Dashboard.tsx`
- **功能**: 总资产概览、类别分布、持仓数据、近期信号统计
- **页面标题**: 无明确标题 (主要为数据展示)

### 复盘分析
- **文件**: `frontend/src/pages/Review.tsx`
- **功能**: 总资产变化与标的表现复盘，历史市值走势分析
- **页面标题**: "复盘分析" (Typography.Title level={3})

### 交易信号
- **文件**: `frontend/src/pages/Signals.tsx`
- **功能**: 历史交易信号管理、信号重建、结构信号生成
- **页面标题**: "历史交易信号" (Typography.Title level={3})

### 持仓编辑
- **文件**: `frontend/src/pages/PositionEditor.tsx`
- **功能**: 持仓管理、新增持仓、持仓数据编辑
- **页面标题**: "持仓编辑" (Typography.Title level={3})

### 标的详情
- **文件**: `frontend/src/pages/InstrumentDetail.tsx`
- **功能**: 单个标的详细信息、K线图、交易记录、持仓信息编辑
- **页面标题**: "标的详情" (Typography.Title level={3})
- **特殊**: 动态路由，需要 ts_code 参数

### 交易流水
- **文件**: `frontend/src/pages/Txn.tsx`
- **功能**: 交易记录管理、新增交易、交易历史查看
- **页面标题**: "交易流水" (Typography.Title level={3})

### 系统设置
- **文件**: `frontend/src/pages/Settings.tsx`
- **功能**: 系统配置、止盈止损设置、数据管理
- **页面标题**: 无明确页面标题，但有 "系统配置" 和 "数据管理" 卡片标题

## 导航结构
导航菜单在 `frontend/src/App.tsx` 中定义：
- Dashboard → `/`
- 复盘分析 → `/review`
- 交易信号 → `/signals` (带警告图标)
- 持仓编辑 → `/positions`
- 交易记录 → `/txn`
- 系统设置 → `/settings` (带设置图标)

## 注意事项
- 所有页面使用 Ant Design 的 Typography.Title level={3} 作为主标题
- 标的详情页面通过点击持仓列表中的标的进入，路径为 `/instrument/:ts_code`
- 部分页面有多个功能区域，每个区域可能有自己的 Card title