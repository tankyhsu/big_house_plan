export type DashboardResp = {
  date: string;
  kpi: { market_value: number; cost: number; unrealized_pnl: number; ret: number | null };
  signals: { stop_gain: number; overweight: number };
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

export type SignalRow = {
  trade_date: string;
  level: string;
  type: "STOP_GAIN" | "OVERWEIGHT";
  category_id?: number | null;
  ts_code?: string | null;
  message: string;
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
