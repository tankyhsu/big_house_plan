# 业务领域详解

## 核心业务流程

### 1. 交易处理流程
```
交易录入 → 交易引擎计算 → 持仓更新 → 投资组合重算 → 信号更新
```

#### 交易引擎 (`domain/txn_engine.py`)
**核心函数**: `compute_position_after_trade(old_shares, old_avg_cost, action, qty, price, fee)`

**支持的交易类型**:
- `BUY` - 买入：加权平均成本计算
- `SELL` - 卖出：已实现损益计算
- `DIV` - 现金股息：无持仓变化
- `STOCK_DIV` - 股票股息：比例调整份额和成本
- `SPLIT` - 股票分割：份额倍增，成本等比减少
- `FEE` - 管理费：成本基础调整

**返回值**: `(新份额, 新均价, 已实现损益)`

### 2. 价格同步与重算

#### 增强价格同步 (`services/pricing_svc.py`)
- **传统模式**: 仅同步当日价格
- **增强模式**: 自动检测过去N天缺失数据并补齐
- **智能重算**: 价格更新后自动重算所有受影响的交易日

**核心功能**:
```python
sync_prices_enhanced(lookback_days=7, ts_codes=None, recalc=True)
```

#### 数据源集成
- **TuShare API**: 股票、ETF、基金、港股数据
- **速率限制**: 防止API调用过频
- **错误处理**: 缺失Token时优雅降级

### 3. 投资组合计算 (`services/calc_svc.py`)

#### 日度快照生成
- `portfolio_daily` - 整体投资组合指标
- `category_daily` - 按类别统计
- 自动触发：交易创建、价格更新、持仓调整

#### 核心指标计算
- **市值**: 当日收盘价 × 持仓份额
- **成本**: 交易引擎计算的加权平均成本
- **损益**: 市值 - 成本 - 累计费用
- **收益率**: 损益 / 成本

### 4. 交易信号系统

#### 信号类型体系
1. **结构信号** - 基于持仓阈值
   - `BUY_STRUCTURE` - 价格跌破成本一定比例
   - `SELL_STRUCTURE` - 价格超过目标收益率
   - 9天倒计时机制

2. **ZIG信号** - 技术分析信号
   - 基于通达信ZIG(3,10)算法
   - 检测价格转向点（V形/倒V形）
   - 84.6%验证准确率

3. **手动信号** - 用户创建
   - 支持多种范围：单个标的/类别/全部
   - 自定义信号类型和参数

#### 信号生成机制
```python
# 结构信号检测
if current_price <= cost_basis * (1 - threshold):
    generate_signal("BUY_STRUCTURE")
    
# ZIG信号检测（3点比较）
if zig[i] > zig[i-1] and zig[i-1] < zig[i-2]:
    generate_signal("BUY_ZIG")
```

## 数据模型关系

### 核心实体
- **Instrument** (标的) ↔ **Category** (类别) - 多对一
- **Transaction** (交易) → **Instrument** - 多对一  
- **Position** (持仓) → **Instrument** - 一对一
- **Signal** (信号) → **Instrument** - 多对一
- **PriceEod** (日终价格) → **Instrument** - 多对一

### 计算依赖链
```
Transactions → Position → Portfolio_Daily
     ↓            ↓           ↓
PriceEod → Market_Value → Category_Daily → Signals
```

## 成本计算增强系统

### 问题解决
- **原问题**: 简单加权平均无法处理复杂场景
- **新方案**: 统一交易引擎处理所有企业行为

### 企业行为处理
- **股票分割**: 2:1分割 → 份额翻倍，成本减半
- **股票股息**: 10%股息 → 份额增加10%，成本按比例调整
- **现金股息**: 不影响持仓，记录现金流
- **管理费用**: 直接调整成本基础

### 已实现损益追踪
```python
realized_pnl = (sell_price - avg_cost) * shares_sold - fees
```

## ZIG信号算法详解

### 通达信ZIG(3,10)含义
- **K=3**: 使用收盘价
- **N=10**: 10%转向阈值  
- **未来函数**: 会根据后续价格修正历史值

### 信号检测公式
```
买入: ZIG(i) > ZIG(i-1) AND ZIG(i-1) < ZIG(i-2)  # V形反转
卖出: ZIG(i) < ZIG(i-1) AND ZIG(i-1) > ZIG(i-2)  # 倒V形反转
```

### 验证数据
基于通达信导出的标准数据验证：
- **301606.SZ**: 100%准确率 (4/4信号)  
- **300573.SZ**: 83.3%准确率 (5/6信号)
- **002847.SZ**: 66.7%准确率 (2/3信号)
- **总体**: 84.6%准确率 (11/13信号)

## 监控和运维

### 操作日志
- 所有关键操作记录在 `operation_log` 表
- 结构化日志便于问题追踪和审计

### 数据备份恢复
- JSON格式业务数据导出
- 事务性数据恢复机制
- 配置热更新支持

### 性能优化
- 智能重算：只计算必要的日期
- 数据缓存：减少重复计算
- 批量操作：减少数据库交互