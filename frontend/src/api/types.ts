export type DashboardResp = {
  date: string;
  kpi: { market_value: number; cost: number; unrealized_pnl: number; ret: number | null };
  signals: { stop_gain: number; overweight: number };
  position_status: { stop_gain: number; stop_loss: number; normal: number }; // 新增：实时持仓状态
  price_fallback_used: boolean;
};

export type CategoryRow = {
  category_id: number;
  name: string;
  sub_name: string;
  target_units: number;
  actual_units: number;
  gap_units: number;
  market_value: number;
  cost: number;
  pnl: number;
  ret: number | null;
  overweight: 0 | 1;
  suggest_units: number | null;
};

export type PositionRow = {
  cat_name: string;
  cat_sub: string;
  ts_code: string;
  name: string;
  shares: number | null;
  avg_cost: number | null;
  close: number | null;
  price_source: "eod" | "avg_cost_fallback";
  market_value: number;
  cost: number;
  unrealized_pnl: number;
  ret: number | null;
  stop_gain_hit: boolean;
};

export type SignalType = 
  | "BUY_STRUCTURE"  // 九转买入信号
  | "SELL_STRUCTURE" // 九转卖出信号
  | "ZIG_BUY"        // ZIG买入信号
  | "ZIG_SELL"       // ZIG卖出信号
  | "BULLISH"        // 利好信号
  | "BEARISH";       // 利空信号

export type SignalLevel = "HIGH" | "MEDIUM" | "LOW" | "INFO";

export type SignalScopeType = 
  | "INSTRUMENT"      // 单个标的
  | "CATEGORY"        // 单个类别 
  | "MULTI_INSTRUMENT"  // 多个标的
  | "MULTI_CATEGORY"   // 多个类别
  | "ALL_INSTRUMENTS"  // 所有标的
  | "ALL_CATEGORIES";  // 所有类别

export type SignalRow = {
  id?: number;
  trade_date: string;
  level: SignalLevel;
  type: SignalType;
  category_id?: number | null;
  ts_code?: string | null;
  name?: string | null; // Instrument name from JOIN
  scope_type?: SignalScopeType;
  scope_data?: string; // JSON array of IDs
  message: string;
  created_at?: string;
};

export type TxnCreate = {
  ts_code: string;
  date: string; // YYYY-MM-DD
  action: "BUY" | "SELL" | "DIV" | "FEE" | "ADJ";
  shares: number;
  price?: number;
  amount?: number;
  fee?: number;
  notes?: string;
};

export type PositionRaw = {
  ts_code: string;
  shares: number;
  avg_cost: number;
  last_update: string;
  inst_name?: string;
  category_id?: number | null;
  cat_name?: string | null;
  cat_sub?: string | null;
  opening_date?: string | null;  // NEW
  last_price?: number | null;
  last_price_date?: string | null;
  price_change?: number | null; // 涨跌幅百分比
};

export type TxnItem = {
  id: number;
  trade_date: string; // YYYY-MM-DD
  ts_code: string;
  name?: string | null;
  action: "BUY" | "SELL" | "DIV" | "FEE" | "ADJ";
  shares: number;
  price: number | null;
  amount: number | null;
  fee: number | null;
  notes: string | null;
  realized_pnl?: number | null; // only for SELL
  group_id?: number | null;     // 用于关联自动现金镜像
};

export type InstrumentLite = {
  ts_code: string;
  name: string;
  active: 0 | 1 | boolean;
  category_id?: number | null;
  cat_name?: string | null;
  cat_sub?: string | null;
  type?: "STOCK" | "FUND" | "CASH" | string; // NEW
};

export type CategoryLite = {
  id: number;
  name: string;
  sub_name: string;
  target_units: number;
};

export type InstrumentDetail = {
  ts_code: string;
  name: string;
  type?: "STOCK" | "FUND" | "CASH" | string | null;
  active: boolean | 0 | 1;
  category_id: number | null;
  cat_name?: string | null;
  cat_sub?: string | null;
};

export type FundHolding = {
  stock_code: string;
  stock_name: string;
  current_weight: number;
  previous_weight: number;
  weight_change: number;
  current_mkv: number;
  previous_mkv: number;
  mkv_change: number;
  current_amount: number;
  is_new: boolean;
  is_increased: boolean;
  is_reduced: boolean;
};

export type FundShareData = {
  ann_date?: string;
  end_date?: string;
  fund_type?: string;
  total_share?: number;
  holder_count?: number;
  [key: string]: any;
};

export type FundNavData = {
  ts_code?: string;
  ann_date?: string;
  nav_date?: string;
  unit_nav?: number;
  accum_nav?: number;
  accum_div?: number;
  net_asset?: number;
  total_netasset?: number;
  [key: string]: any;
};

export type FundManager = {
  name: string;
  gender?: string;
  education?: string;
  nationality?: string;
  begin_date?: string;
  end_date?: string;
  resume?: string;
};

export type FundProfile = {
  holdings: {
    current: any[];
    previous: any[];
    changes: FundHolding[];
    error?: string | null;
  };
  scale: {
    recent_shares: FundShareData[];
    nav_data: FundNavData[];
    error?: string | null;
  };
  managers: {
    current_managers: FundManager[];
    error?: string | null;
  };
};

export type SignalDetail = {
  id?: number;
  date: string;
  type: SignalType;
  level?: SignalLevel;
  message: string;
  price?: number | null;
  ts_code?: string;
  category_id?: number | null;
  scope_type?: string;
  created_at?: string;
};

// 新增：持仓状态类型定义
export type PositionStatus = {
  ts_code: string;
  category_id?: number;
  shares: number;
  avg_cost: number;
  current_price: number;
  return_rate: number;
  status: "NORMAL";
  stop_gain_threshold: number;
  stop_loss_threshold: number;
  message: string;
  price_fallback_used: boolean;
};

// K线图的配置信息
export type KlineConfig = {
  avg_cost: number;
  stop_gain_threshold: number;
  stop_loss_threshold: number;
  stop_gain_price: number;
  stop_loss_price: number;
};

// 自选关注 Watchlist
export type WatchlistItem = {
  ts_code: string;
  name: string | null;
  type?: string | null;
  active?: boolean | 0 | 1 | null;
  category_id?: number | null;
  note?: string | null;
  created_at?: string | null;
  last_price?: number | null;
  last_price_date?: string | null;
  price_change?: number | null; // 涨跌幅百分比
  has_position?: boolean; // 是否已持仓
};

// 按月盈亏统计
export type MonthlyPnlStats = {
  month: string;          // YYYY-MM
  total_pnl: number;      // 总盈亏
  profit: number;         // 盈利总额
  loss: number;           // 亏损总额  
  trade_count: number;    // 交易次数
  profit_count: number;   // 盈利交易次数
  loss_count: number;     // 亏损交易次数
};
