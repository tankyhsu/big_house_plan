import client from "./client";
import type { DashboardResp, CategoryRow, PositionRow, SignalRow, TxnCreate, PositionStatus, KlineConfig, WatchlistItem, MonthlyPnlStats } from "./types";

export async function fetchDashboard(date: string): Promise<DashboardResp> {
  const { data } = await client.get("/api/dashboard", { params: { date } });
  return data;
}

export async function fetchDashboardAgg(startYmd: string, endYmd: string, period: "day"|"week"|"month") {
  const { data } = await client.get("/api/dashboard/aggregate", { params: { start: startYmd, end: endYmd, period } });
  return data as { period: string; items: { date: string; market_value: number; cost: number; unrealized_pnl: number; ret: number | null; }[] };
}
export async function fetchPositionSeries(startYmd: string, endYmd: string, codes: string[]) {
  const ts_codes = codes.join(',');
  const { data } = await client.get("/api/series/position", { params: { start: startYmd, end: endYmd, ts_codes } });
  return data as { items: { date: string; ts_code: string; name: string; market_value: number }[] };
}
export async function fetchCategory(date: string): Promise<CategoryRow[]> {
  const { data } = await client.get("/api/category", { params: { date } });
  return data;
}
export async function fetchPosition(date: string): Promise<PositionRow[]> {
  const { data } = await client.get("/api/position", { params: { date } });
  return data;
}
export async function fetchSignals(date: string, type?: string): Promise<SignalRow[]> {
  const params: any = { date };
  if (type && type !== "ALL") {
    params.type = type;
  }
  const { data } = await client.get("/api/signal", { params });
  return data;
}

export async function fetchSignalsByTsCode(date: string, ts_code: string): Promise<SignalRow[]> {
  const { data } = await client.get("/api/signal", { params: { date, ts_code } });
  return data;
}

export async function fetchAllSignals(type?: string, ts_code?: string, startDate?: string, endDate?: string, limit?: number): Promise<SignalRow[]> {
  const params: any = {};
  if (type && type !== "ALL") params.type = type;
  if (ts_code) params.ts_code = ts_code;
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  if (limit) params.limit = limit;
  const { data } = await client.get("/api/signal/all", { params });
  return data;
}

export interface SignalCreatePayload {
  trade_date: string;           // YYYY-MM-DD format
  ts_code?: string;            // 标的代码（兼容性）
  category_id?: number;        // 类别ID（兼容性）
  scope_type: "INSTRUMENT" | "CATEGORY" | "MULTI_INSTRUMENT" | "MULTI_CATEGORY" | "ALL_INSTRUMENTS" | "ALL_CATEGORIES";
  scope_data?: string[];       // 多选时的ID数组
  level: "HIGH" | "MEDIUM" | "LOW" | "INFO";
  type: string;                // 信号类型
  message: string;             // 信号描述
}

export async function createSignal(payload: SignalCreatePayload) {
  const { data } = await client.post("/api/signal/create", payload);
  return data;
}

export async function postCalc(date: string) {
  const { data } = await client.post("/api/calc", { date });
  return data;
}
export async function postSyncPrices(date: string) {
  const { data } = await client.post("/api/sync-prices", { date, recalc: true });
  return data;
}
export async function createTxn(payload: TxnCreate) {
  const { data } = await client.post("/api/txn/create", payload);
  return data;
}

export async function fetchMonthlyPnlStats(): Promise<MonthlyPnlStats[]> {
  const { data } = await client.get("/api/txn/monthly-stats");
  return data.items;
}

import type { PositionRaw } from "./types";


// === Position raw ===
export async function fetchPositionRaw(includeZero: boolean = true) {
  const { data } = await client.get("/api/position/raw", { params: { include_zero: includeZero, nocache: Date.now() } });
  return data as PositionRaw[];
}

export async function deletePositionOne(ts_code: string, recalcDate?: string) {
  const { data } = await client.post("/api/position/delete", { ts_code, recalc_date: recalcDate });
  return data as { message: string; deleted: number };
}


// 更新一条底仓
export async function updatePositionOne(payload: { ts_code: string; shares?: number; avg_cost?: number; date: string; opening_date?: string; }) {
  const { data } = await client.post("/api/position/update", payload);
  return data;
}

import type { TxnItem } from "./types";

export async function fetchTxnList(page = 1, size = 20): Promise<{ total: number; items: TxnItem[] }> {
  const { data } = await client.get("/api/txn/list", { params: { page, size } });
  return data;
}

export async function fetchTxnRange(startYmd: string, endYmd: string, codes?: string[]) {
  const ts_codes = codes && codes.length > 0 ? codes.join(',') : undefined;
  const { data } = await client.get("/api/txn/range", { params: { start: startYmd, end: endYmd, ts_codes } });
  return data as { items: { date: string; ts_code: string; name?: string | null; action: "BUY"|"SELL"|"DIV"|"FEE"|"ADJ"; shares: number; price: number | null; amount: number | null; fee: number | null; }[] };
}

import type { CategoryLite, InstrumentLite, InstrumentDetail, FundProfile } from "./types";

export async function fetchInstruments(q?: string): Promise<InstrumentLite[]> {
  const { data } = await client.get("/api/instrument/list", { params: { q } });
  return data;
}

// 最近价格（单标的）
export async function fetchLastPrice(ts_code: string, ymd?: string): Promise<{ trade_date: string | null; close: number | null; }> {
  const { data } = await client.get("/api/price/last", { params: { ts_code, date: ymd } });
  return data;
}

export async function fetchCategories(): Promise<CategoryLite[]> {
  const { data } = await client.get("/api/category/list");
  return data;
}

export async function createCategory(payload: { name: string; sub_name?: string; target_units: number }) {
  const { data } = await client.post("/api/category/create", {
    name: payload.name,
    sub_name: payload.sub_name ?? "",
    target_units: payload.target_units,
  });
  return data as { message: string; id: number };
}

export async function updateCategory(payload: { id: number; sub_name?: string; target_units?: number }) {
  const { data } = await client.post("/api/category/update", payload);
  return data as { message: string; category: CategoryLite };
}

export async function updateCategoriesBulk(items: { id: number; sub_name?: string; target_units?: number }[]) {
  const { data } = await client.post("/api/category/bulk-update", { items });
  return data as { message: string; auto_fill: number; total: number; cash_category?: { id: number; name: string; sub_name?: string | null } | null };
}

export async function createInstrument(payload: { ts_code: string; name: string; category_id: number; active?: boolean; type?: string }) {
  const { data } = await client.post("/api/instrument/create", payload);
  return data;
}

export async function lookupInstrument(ts_code: string, ymd?: string) {
  const { data } = await client.get("/api/instrument/lookup", { params: { ts_code, date: ymd } });
  return data as { ts_code: string; name?: string; type?: string; basic?: any; price?: { trade_date: string; close: number } | null };
}

export async function fetchInstrumentDetail(ts_code: string): Promise<InstrumentDetail> {
  const { data } = await client.get("/api/instrument/get", { params: { ts_code, nocache: Date.now() } });
  return data as InstrumentDetail;
}

export async function fetchFundProfile(ts_code: string): Promise<FundProfile> {
  const { data } = await client.get("/api/fund/profile", { params: { ts_code, nocache: Date.now() } });
  return data as FundProfile;
}

export async function editInstrument(payload: { ts_code: string; name: string; category_id: number; active: boolean; type?: string | null; }) {
  const { data } = await client.post("/api/instrument/edit", payload);
  return data as { message: string };
}

// 补充后端返回的原因字段
export type IrrRow = {
  ts_code: string;
  date: string;                  // YYYY-MM-DD
  annualized_mwr: number | null; // 0.123 -> 12.3%
  flows: number;
  used_price_date?: string | null;
  terminal_value?: number | null;
  irr_reason?: string | null;    // NEW: "ok" | "no_solution" | "fallback_opening_date" | ...
};

export async function fetchIrr(ts_code: string, ymd: string) {
  const { data } = await client.get("/api/position/irr", { params: { ts_code, date: ymd, nocache: Date.now() } });
  return data as IrrRow;
}

export async function fetchIrrBatch(ymd: string) {
  const { data } = await client.get("/api/position/irr/batch", { params: { date: ymd, nocache: Date.now() } });
  return data as IrrRow[];
}

export async function fetchSettings() {
  const { data } = await client.get("/api/settings/get", { params: { nocache: Date.now() } });
  return data as {
    unit_amount: number;
    stop_gain_pct: number;
    stop_loss_pct: number;
    overweight_band: number;
    // ... 其它配置字段
  };
}

export async function updateSettings(updates: Record<string, any>) {
  const { data } = await client.post("/api/settings/update", { updates });
  return data as { message: string; updated: string[] };
}

// OHLC for K-line
export type OhlcItem = { date: string; open: number; high: number; low: number; close: number; vol?: number | null };
export async function fetchOhlcRange(ts_code: string, startYmd: string, endYmd: string): Promise<OhlcItem[]> {
  const { data } = await client.get("/api/price/ohlc", { params: { ts_code, start: startYmd, end: endYmd, nocache: Date.now() } });
  return (data?.items || []) as OhlcItem[];
}

// 数据备份和恢复
export async function downloadBackup(): Promise<void> {
  const response = await client.post("/api/backup", {}, { 
    responseType: "blob",
    headers: {
      'Accept': 'application/json'
    }
  });
  
  // 创建下载链接
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  
  // 从响应头获取文件名，如果没有则使用默认文件名
  const contentDisposition = response.headers['content-disposition'];
  let filename = 'portfolio_backup.json';
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename=([^;]+)/);
    if (filenameMatch) {
      filename = filenameMatch[1].replace(/"/g, '');
    }
  }
  
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function uploadRestore(file: File): Promise<{ message: string }> {
  const formData = new FormData();
  formData.append('file', file);
  
  const { data } = await client.post("/api/restore", formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
  
  return data;
}

// 新增：获取持仓状态信息（用于K线图阈值线展示）
export async function fetchPositionStatus(date: string, ts_code?: string): Promise<PositionStatus[]> {
  const params: any = { date };
  if (ts_code) params.ts_code = ts_code;
  const { data } = await client.get("/api/positions/status", { params });
  return Array.isArray(data) ? data : [data].filter(Boolean);
}

// 计算K线图配置信息
export async function fetchKlineConfig(ts_code: string, date: string): Promise<KlineConfig | null> {
  try {
    const positionStatus = await fetchPositionStatus(date, ts_code);
    if (!positionStatus || positionStatus.length === 0) return null;
    
    const position = positionStatus[0];
    return {
      avg_cost: position.avg_cost,
      stop_gain_threshold: position.stop_gain_threshold,
      stop_loss_threshold: position.stop_loss_threshold,
      stop_gain_price: position.avg_cost * (1 + position.stop_gain_threshold),
      stop_loss_price: position.avg_cost * (1 - position.stop_loss_threshold)
    };
  } catch (error) {
    console.warn('Failed to fetch kline config:', error);
    return null;
  }
}

// 自选关注 Watchlist APIs
export async function fetchWatchlist(date?: string): Promise<WatchlistItem[]> {
  const params: any = {};
  if (date) params.date = date;
  const { data } = await client.get("/api/watchlist", { params });
  return (data?.items || []) as WatchlistItem[];
}

export async function addWatchlist(ts_code: string, note?: string) {
  const { data } = await client.post("/api/watchlist/add", { ts_code, note });
  return data as { message: string };
}

export async function removeWatchlist(ts_code: string) {
  const { data } = await client.post("/api/watchlist/remove", { ts_code });
  return data as { message: string };
}

export async function rebuildHistoricalSignals() {
  const { data } = await client.post("/api/signal/rebuild-historical");
  return data;
}

export async function rebuildZigSignals() {
  const { data } = await client.post("/api/signal/rebuild-zig");
  return data;
}

// 同步价格数据
export type SyncPricesParams = {
  date?: string;        // 结束日期，格式YYYYMMDD，不传则今天
  days?: number;        // 同步过去N天的数据
  ts_codes?: string[];  // 指定要同步的标的代码
  recalc?: boolean;     // 是否重新计算
};

export type SyncPricesResult = {
  message: string;
  dates_processed: number;
  total_found: number;
  total_updated: number;
  total_skipped: number;
  used_dates_uniq: string[];
  details: any[];
};

export async function syncPrices(params: SyncPricesParams): Promise<SyncPricesResult> {
  const { data } = await client.post("/api/sync-prices", params);
  return data;
}

// 增强的价格同步：自动检测并补齐过去几天缺失的价格数据
export type SyncPricesEnhancedParams = {
  lookback_days?: number;   // 向前检查的天数，默认7天
  ts_codes?: string[];      // 指定要同步的标的代码
  recalc?: boolean;         // 是否重新计算，默认true
};

export type SyncPricesEnhancedResult = {
  message: string;
  dates_processed: number;
  total_found: number;
  total_updated: number;
  total_skipped: number;
  missing_summary: Record<string, number>;  // {date: missing_count}
  details: any[];
  recalc_performed?: boolean;
};

export async function syncPricesEnhanced(params: SyncPricesEnhancedParams = {}): Promise<SyncPricesEnhancedResult> {
  const { data } = await client.post("/api/sync-prices-enhanced", params);
  return data;
}

// 检测最近有效交易日：通过获取一个代表性标的的最近价格来判断
export async function getLastValidTradingDate(ymd?: string): Promise<{ trade_date: string | null; close: number | null; }> {
  // 使用沪深300指数作为代表性标的检测交易日
  const { data } = await client.get("/api/price/last", { params: { ts_code: "399300.SZ", date: ymd } });
  return data;
}

// 获取price_eod表中的最新交易日
export async function getLatestTradingDate(): Promise<{ latest_trading_date: string | null }> {
  const { data } = await client.get("/api/price/latest-trading-date");
  return data;
}
