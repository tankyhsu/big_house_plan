import client from "./client";
import type { DashboardResp, CategoryRow, PositionRow, SignalRow, TxnCreate } from "./types";

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

export async function cleanupZeroPositions(recalcDate?: string) {
  const { data } = await client.post("/api/position/cleanup-zero", { recalc_date: recalcDate });
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

import type { CategoryLite, InstrumentLite, InstrumentDetail } from "./types";

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
