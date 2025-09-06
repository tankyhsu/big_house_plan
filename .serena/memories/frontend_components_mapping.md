# 前端公共组件映射

## 组件目录结构

```
frontend/src/components/
├── charts/                          # 图表组件目录
│   ├── hooks/                       # 图表相关 Hooks
│   │   └── useCandleData.ts        # K线数据获取 Hook
│   ├── CandleChart.tsx             # K线图组件（主要入口）
│   ├── CandleChartView.tsx         # K线图视图组件
│   ├── CandleToolbar.tsx           # K线图工具栏
│   ├── candleOption.ts             # K线图配置构建函数
│   ├── indicators.ts               # 技术指标计算函数
│   ├── TotalAssetsLine.tsx         # 总资产趋势线图
│   ├── PositionPie.tsx             # 持仓饼图
│   ├── PositionSeriesPanel.tsx     # 持仓序列面板
│   ├── PositionSeriesLine.tsx      # 持仓序列线图
│   ├── HistoricalLineChart.tsx     # 历史数据线图
│   └── usePositionSeries.ts        # 持仓序列数据 Hook
├── CategoryTable.tsx               # 类别数据表格
├── CreateSignalModal.tsx          # 创建信号弹窗
├── InstrumentDisplay.tsx          # 标的信息展示组件
├── KpiCards.tsx                   # KPI 卡片组件
├── PositionTable.tsx              # 持仓数据表格
└── SignalTags.tsx                 # 信号标签组件
```

## 组件详细说明

### 数据展示组件

#### KpiCards.tsx
- **功能**: 显示关键绩效指标（KPI）卡片
- **Props**: `marketValue`, `cost`, `pnl`, `ret`, `signals`, `priceFallback`, `dateText`
- **使用页面**: Dashboard
- **描述**: 展示市值、成本、收益、收益率等核心财务指标

#### CategoryTable.tsx
- **功能**: 类别数据表格展示
- **Props**: `data`, `loading`, `header`, `height`
- **使用页面**: Dashboard
- **描述**: 按类别分组显示投资组合数据

#### PositionTable.tsx
- **功能**: 持仓数据表格展示
- **Props**: `data`, `loading`, `signals`
- **使用页面**: Dashboard
- **描述**: 显示所有持仓信息，包括代码、名称、份额、均价等

#### InstrumentDisplay.tsx
- **功能**: 标的信息统一展示组件
- **Props**: `data`, `mode`, `showLink`, `signals`, `maxSignals`, `style` 等
- **使用页面**: PositionEditor, Signals, Txn
- **描述**: 提供多种模式的标的信息展示（代码、名称、组合等）
- **特色**: 包含工具函数 `createInstrumentOptions` 和 `getInstrumentDisplayText`

#### SignalTags.tsx
- **功能**: 信号标签展示组件
- **Props**: `signals`, `maxDisplay`
- **使用页面**: InstrumentDetail, InstrumentDisplay 中使用
- **描述**: 以标签形式展示交易信号，支持限制显示数量

### 图表组件系列

#### CandleChart.tsx
- **功能**: K线图主组件
- **Props**: `tsCode`, `months`, `height`, `title`, `secType`, `stretch`, `signals`
- **使用页面**: InstrumentDetail
- **描述**: 显示股票/基金的K线图，包含技术指标、交易点位、信号标记

#### CandleChartView.tsx
- **功能**: K线图视图容器
- **Props**: `option`, `height`, `title`, `fullscreen`, `onOpen`, `onClose`
- **描述**: 提供K线图的视图容器，支持全屏模式

#### CandleToolbar.tsx
- **功能**: K线图工具栏
- **Props**: `range`, `onRangeChange`, `maInput`, `onMaInputChange`, `onApplyMaInput`, `onOpenFullscreen`
- **描述**: K线图的控制工具栏，支持时间范围选择、均线设置等

#### TotalAssetsLine.tsx
- **功能**: 总资产趋势线图
- **使用页面**: Review
- **描述**: 显示投资组合总资产随时间的变化趋势

#### PositionPie.tsx
- **功能**: 持仓分布饼图
- **Props**: `date`
- **使用页面**: Dashboard
- **描述**: 以饼图形式展示不同类别的持仓分布

#### PositionSeriesPanel.tsx
- **功能**: 持仓序列面板
- **Props**: `title`, `defaultNormalize`
- **使用页面**: Review
- **描述**: 提供多标的持仓对比分析面板

#### HistoricalLineChart.tsx
- **功能**: 历史数据线图
- **Props**: `series`, `normalize`, `height`, `eventsByCode`, `lastPriceMap`, `signalsByCode`
- **描述**: 通用的历史数据线图组件，支持标准化、交易事件标记、信号显示

### 交互组件

#### CreateSignalModal.tsx
- **功能**: 创建信号弹窗
- **Props**: `open`, `onClose`, `onSuccess`
- **使用页面**: Signals
- **描述**: 手动创建交易信号的弹窗表单

### 工具函数和配置

#### candleOption.ts
- **功能**: K线图配置构建
- **导出**: `buildCandleOption` 函数
- **描述**: 构建ECharts K线图的完整配置，包含技术指标、信号标记、交易点位等

#### indicators.ts
- **功能**: 技术指标计算
- **导出**: `sma`, `ema`, `computeMacd`, `computeKdj`, `computeBias`, `mapVolumes`
- **描述**: 提供各种技术分析指标的计算函数

### Hooks

#### useCandleData.ts
- **功能**: K线数据获取Hook
- **参数**: `tsCode`, `months`
- **描述**: 封装K线数据获取逻辑

#### usePositionSeries.ts
- **功能**: 持仓序列数据Hook
- **参数**: `codes`, `range`
- **描述**: 获取多个标的的持仓序列数据

## 组件使用关系

| 页面 | 使用的组件 |
|-----|-----------|
| Dashboard | KpiCards, CategoryTable, PositionTable, PositionPie |
| Review | PositionSeriesPanel, TotalAssetsLine |
| Signals | CreateSignalModal, InstrumentDisplay |
| PositionEditor | InstrumentDisplay |
| InstrumentDetail | CandleChart, SignalTags |
| Txn | InstrumentDisplay |

## 设计特点

1. **模块化设计**: 图表组件独立成目录，便于维护
2. **复用性强**: InstrumentDisplay、SignalTags 等组件在多个页面使用
3. **专业性强**: 提供完整的金融图表和技术指标支持
4. **配置灵活**: 组件支持多种显示模式和自定义配置
5. **数据驱动**: 大部分组件都是纯展示组件，依赖外部数据源