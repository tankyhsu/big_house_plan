# K线图模块化重构架构

## 重构概述
为了解决 `candleOption.ts` 文件过于复杂（800+行）的问题，已将K线图配置拆分为多个专业化的模块，每个模块负责特定的图表功能。

## 新架构文件结构

### 核心模块文件
```
frontend/src/components/charts/options/
├── types.ts                    // 共享类型定义
├── layoutBuilder.ts            // 图表布局计算
├── priceSeriesBuilder.ts       // 主图数据（K线、均线、成本线）
├── tradeMarkersBuilder.ts      // 交易标记（买卖点）
├── signalSeriesBuilder.ts      // 信号处理（含结构信号倒计时）
├── technicalIndicatorsBuilder.ts // 技术指标（MACD、KDJ、BIAS、成交量）
├── tooltipBuilder.ts           // 工具提示格式化
└── legendBuilder.ts            // 图例构建
```

### 主入口文件
- `candleOption.ts` - 重构后的主入口，负责协调各模块工作

## 各模块职责

### 1. types.ts
定义所有共享的 TypeScript 类型：
- `Item`, `Trade`, `Signal`, `KlineConfig`, `Panel`, `CandleOptionParams`

### 2. layoutBuilder.ts
负责图表面板布局计算：
- 全屏/非全屏模式适配
- 多面板（价格、成交量、技术指标）动态布局
- 根据证券类型（STOCK/ETF/FUND/CASH）决定显示哪些指标面板

### 3. priceSeriesBuilder.ts  
构建主图价格数据：
- K线蜡烛图数据
- 移动平均线（MA）
- 持仓成本线
- 条件性止盈/止损线（根据当前盈亏状态显示）

### 4. tradeMarkersBuilder.ts
构建交易标记：
- 买入点标记（红色三角形，向上）
- 卖出点标记（绿色三角形，向下）
- 包含文字标签和样式

### 5. signalSeriesBuilder.ts
处理各类交易信号：
- 统一信号渲染逻辑
- 结构信号9天倒计时功能（BUY_STRUCTURE/SELL_STRUCTURE）
- 信号价格自动匹配和回退机制
- 信号分组和配置应用

### 6. technicalIndicatorsBuilder.ts
技术指标面板构建：
- MACD指标（柱状图+DIF/DEA线）
- KDJ指标（K/D/J线）
- BIAS指标（多周期乖离率）
- 成交量柱状图
- 动态面板网格和坐标轴配置

### 7. tooltipBuilder.ts
工具提示HTML格式化：
- OHLC价格数据
- 成交量信息
- 分类显示：趋势指标、持仓参考、技术指标
- 交易记录和信号信息
- 响应式颜色和样式

### 8. legendBuilder.ts
图例配置构建：
- 主图图例（K线、均线、成本线、止盈止损线、交易标记、信号）
- 技术指标图例（按面板分组）
- 条件性图例显示（根据当前盈亏状态）

## 重构优势

### 1. 可维护性提升
- 单一职责原则：每个模块专注特定功能
- 代码组织清晰：相关功能集中在同一文件
- 易于定位问题：bug通常只涉及特定模块

### 2. 可扩展性增强
- 新增图表功能只需在相应模块中修改
- 模块间解耦，修改某个模块不影响其他模块
- 便于添加新的技术指标或信号类型

### 3. 代码复用
- 共享类型定义避免重复
- 工具函数可在模块间复用
- 样式和配置的一致性

### 4. 测试友好
- 每个模块可独立测试
- 纯函数设计，输入输出明确
- Mock数据更容易构造

## 重要特性保留

### 信号系统
- 完整保留了所有信号类型的渲染
- 结构信号的9天倒计时功能正常工作
- 信号配置统一管理（colors, emojis, positioning）

### 动态止盈止损
- 根据当前盈亏状态智能显示止盈线或止损线
- 成本线始终显示作为参考
- 图例自动更新反映当前显示的线条

### 性能优化
- 数据处理和渲染逻辑分离
- 避免重复计算
- 响应式布局支持全屏模式

## 使用方式
主入口 `buildCandleOption()` 函数的使用方式保持不变，确保了向后兼容性。所有现有的调用代码无需修改即可使用重构后的模块化架构。