import client from "./client";
import type { DashboardResp, CategoryRow, PositionRow, SignalRow, TxnCreate } from "./types";

export async function fetchDashboard(date: string): Promise<DashboardResp> {
  const { data } = await client.get("/api/dashboard", { params: { date } });
  return data;
}
export async function fetchCategory(date: string): Promise<CategoryRow[]> {
  const { data } = await client.get("/api/category", { params: { date } });
  return data;
}
export async function fetchPosition(date: string): Promise<PositionRow[]> {
  const { data } = await client.get("/api/position", { params: { date } });
  return data;
}
export async function fetchSignals(date: string, type: "ALL" | "STOP_GAIN" | "OVERWEIGHT" = "ALL"): Promise<SignalRow[]> {
  const { data } = await client.get("/api/signal", { params: { date, type } });
  return data;
}
export async function postCalc(date: string) {
  const { data } = await client.post("/api/calc", { date });
  return data;
}
export async function postSyncPrices(date: string) {
  const { data } = await client.post("/api/sync-prices", { date });
  return data;
}
export async function createTxn(payload: TxnCreate) {
  const { data } = await client.post("/api/txn/create", payload);
  return data;
}

import type { PositionRaw } from "./types";

// 读取底仓（position 表）
export async function fetchPositionRaw(): Promise<PositionRaw[]> {
  const { data } = await client.get("/api/position/raw");
  return data;
}

// 更新一条底仓
export async function updatePositionOne(payload: { ts_code: string; shares?: number; avg_cost?: number; date: string; }) {
  const { data } = await client.post("/api/position/update", payload);
  return data;
}

import type { TxnItem } from "./types";

export async function fetchTxnList(page = 1, size = 20): Promise<{ total: number; items: TxnItem[] }> {
  const { data } = await client.get("/api/txn/list", { params: { page, size } });
  return data;
}

import type { InstrumentLite } from "./types";

export async function fetchInstruments(q?: string): Promise<InstrumentLite[]> {
  const { data } = await client.get("/api/instrument/list", { params: { q } });
  return data;
}

import type { CategoryLite, InstrumentLite } from "./types";

export async function fetchCategories(): Promise<CategoryLite[]> {
  const { data } = await client.get("/api/category/list");
  return data;
}

export async function createInstrument(payload: { ts_code: string; name: string; category_id: number; active?: boolean }) {
  const { data } = await client.post("/api/instrument/create", payload);
  return data;
}