# 前端架构参考

## 页面路由映射
| 路由 | 文件 | 功能 | 菜单标题 |
|-----|------|------|---------|
| `/` | `pages/Dashboard.tsx` | 投资组合总览 | Dashboard |
| `/review` | `pages/Review.tsx` | 复盘分析 | 复盘分析 |
| `/signals` | `pages/Signals.tsx` | 交易信号管理 | 交易信号 |
| `/positions` | `pages/PositionEditor.tsx` | 持仓编辑 | 持仓编辑 |
| `/txn` | `pages/Txn.tsx` | 交易流水 | 交易记录 |
| `/settings` | `pages/Settings.tsx` | 系统配置 | 系统设置 |
| `/instrument/:ts_code` | `pages/InstrumentDetail.tsx` | 标的详情 | (详情页) |

## 核心组件体系

### 数据展示组件
- `KpiCards.tsx` - 关键绩效指标卡片
- `CategoryTable.tsx` - 类别分布表格
- `PositionTable.tsx` - 持仓数据表格
- `InstrumentDisplay.tsx` - 标的信息展示（多模式）
- `SignalTags.tsx` - 交易信号标签

### 图表组件系列 (`components/charts/`)

#### K线图核心模块
- `CandleChart.tsx` - K线图主入口
- `CandleChartView.tsx` - 视图容器（支持全屏）
- `CandleToolbar.tsx` - 控制工具栏
- `useCandleData.ts` - 数据获取Hook

#### K线图配置模块化架构 (`components/charts/options/`)
```
options/
├── types.ts                    # 共享类型定义
├── layoutBuilder.ts            # 图表布局计算  
├── priceSeriesBuilder.ts       # 主图数据（K线、均线、成本线）
├── tradeMarkersBuilder.ts      # 交易标记（买卖点）
├── signalSeriesBuilder.ts      # 信号处理（含结构信号倒计时）
├── technicalIndicatorsBuilder.ts # 技术指标（MACD、KDJ、BIAS）
├── tooltipBuilder.ts           # 工具提示格式化
└── legendBuilder.ts            # 图例构建
```

#### 其他图表组件
- `TotalAssetsLine.tsx` - 总资产趋势线
- `PositionPie.tsx` - 持仓分布饼图
- `PositionSeriesPanel.tsx` - 持仓对比面板
- `HistoricalLineChart.tsx` - 通用历史线图

#### 技术指标支持
- **移动平均线**: SMA, EMA
- **趋势指标**: MACD (DIF, DEA, 柱状图)
- **摆动指标**: KDJ (K, D, J线)
- **偏离指标**: BIAS (多周期乖离率)
- **成交量**: 柱状图 + 量价关系

### 交互组件
- `CreateSignalModal.tsx` - 信号创建弹窗
- 各种表单和编辑组件

## K线图重构架构

### 重构原因
解决原 `candleOption.ts` 文件过于复杂（800+行）的问题

### 模块职责划分
- **layoutBuilder**: 动态面板布局（全屏/标准模式）
- **priceSeriesBuilder**: K线和价格相关数据
- **tradeMarkersBuilder**: 买卖点标记渲染
- **signalSeriesBuilder**: 统一信号处理 + 结构信号倒计时
- **technicalIndicatorsBuilder**: 所有技术指标面板
- **tooltipBuilder**: 多分类工具提示HTML
- **legendBuilder**: 条件性图例显示

### 关键特性保留
- **ZIG信号系统**: 完整信号渲染和配置
- **结构信号倒计时**: 9天倒计时显示
- **动态止盈止损**: 根据盈亏状态显示对应线条
- **交易标记**: 买卖点可视化
- **响应式设计**: 支持全屏模式切换

## 数据流和状态管理

### API集成
- **React Query**: 数据获取和缓存
- **TypeScript客户端**: 类型安全的API调用
- **统一错误处理**: 全局错误边界和提示

### 状态管理模式
- 组件级状态：使用useState/useReducer
- 服务端状态：React Query管理
- 全局状态：Context API（配置等）

### 数据获取Hooks
- `useCandleData.ts` - K线数据
- `usePositionSeries.ts` - 持仓序列数据
- 各种业务数据hooks在 `api/hooks.ts`

## 设计规范

### UI框架
- **Ant Design**: 主要组件库
- **ECharts**: 专业图表库
- **响应式设计**: 适配不同屏幕尺寸

### 代码规范  
- **TypeScript严格模式**: 完整类型定义
- **组件复用**: 高度模块化设计
- **性能优化**: memo, useMemo, useCallback合理使用
- **错误边界**: 防止组件崩溃影响整体

### 文件组织原则
- 按功能域分组（pages, components, api）
- 相关文件就近原则
- 共享组件独立目录
- 类型定义集中管理