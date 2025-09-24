/**
 * 聚合API hooks - 提供页面级别的数据聚合调用
 * 减少API请求数量，提高性能
 */
import client from "./client";
import type { DashboardResp, CategoryRow, PositionRow, SignalRow, WatchlistItem, MonthlyPnlStats, InstrumentLite, TxnItem, PositionRaw } from "./types";

// 聚合API响应类型定义
export interface DashboardFullResponse {
  dashboard: DashboardResp;
  categories: CategoryRow[];
  positions: PositionRow[];
  signals: SignalRow[];
  _meta: {
    date: string;
    latest_trading_date: string;
    data_keys: string[];
  };
}

export interface WatchlistFullResponse {
  watchlist: {
    items: WatchlistItem[];
  };
  instruments: InstrumentLite[];
  signals_batch: Record<string, SignalRow[]>;
  _meta: {
    date: string;
    latest_trading_date: string;
    data_keys: string[];
  };
}

export interface TransactionPageResponse {
  transactions: {
    total: number;
    items: TxnItem[];
  };
  monthly_stats: {
    items: MonthlyPnlStats[];
  };
  instruments: InstrumentLite[];
  categories_list: any[];
  positions_raw: PositionRaw[];
  settings: any;
  _meta: {
    date?: string;
    latest_trading_date: string;
    data_keys: string[];
  };
}

export interface ReviewPageResponse {
  dashboard_aggregate: {
    period: string;
    start: string;
    end: string;
    items: Array<{
      date: string;
      market_value: number;
      cost: number;
      unrealized_pnl: number;
      ret: number | null;
    }>;
  };
  signals: SignalRow[] | Record<string, SignalRow[]>;
  positions_raw: PositionRaw[];
  position_series?: {
    items: Array<{
      date: string;
      ts_code: string;
      name: string;
      market_value: number;
    }>;
  };
  transactions_range?: {
    items: Array<{
      date: string;
      ts_code: string;
      name?: string | null;
      action: "BUY" | "SELL" | "DIV" | "FEE" | "ADJ";
      shares: number;
      price: number | null;
      amount: number | null;
      fee: number | null;
    }>;
    error?: string;
  };
  _meta: {
    start: string;
    end: string;
    start_date: string;
    end_date: string;
  };
}

export interface FlexibleDataRequest {
  include_dashboard?: boolean;
  include_categories?: boolean;
  include_positions?: boolean;
  include_signals?: boolean;
  include_watchlist?: boolean;
  include_transactions?: boolean;
  include_instruments?: boolean;
  include_settings?: boolean;
  include_monthly_stats?: boolean;

  // 参数配置
  date?: string;
  signal_start_date?: string;
  signal_end_date?: string;
  signal_limit?: number;
  signal_ts_code?: string;
  signal_type?: string;

  txn_page?: number;
  txn_size?: number;

  position_include_zero?: boolean;
  position_with_price?: boolean;
}

/**
 * 获取Dashboard页面完整数据
 * 替代多个API调用：/api/dashboard + /api/category + /api/position + /api/signal/all
 */
export async function fetchDashboardFull(date?: string): Promise<DashboardFullResponse> {
  const params: any = {};
  if (date) params.date = date;

  const { data } = await client.get("/api/aggregated/dashboard", { params });
  return data;
}

/**
 * 获取Watchlist页面完整数据
 * 替代多个API调用：/api/watchlist + /api/instrument/list + 多个/api/signal/all
 */
export async function fetchWatchlistFull(date?: string): Promise<WatchlistFullResponse> {
  const params: any = {};
  if (date) params.date = date;

  const { data } = await client.get("/api/aggregated/watchlist", { params });
  return data;
}

/**
 * 获取Transaction页面完整数据
 * 替代多个API调用：/api/txn/list + /api/txn/monthly-stats + /api/instrument/list + etc
 */
export async function fetchTransactionPage(page: number = 1, size: number = 20): Promise<TransactionPageResponse> {
  const { data } = await client.get("/api/aggregated/transactions", {
    params: { page, size }
  });
  return data;
}

/**
 * 获取Review页面完整数据
 * 替代多个API调用：/api/dashboard/aggregate + /api/signal/all + /api/position/raw + etc
 */
export async function fetchReviewPage(
  start: string,
  end: string,
  ts_codes?: string
): Promise<ReviewPageResponse> {
  const params: any = { start, end };
  if (ts_codes) params.ts_codes = ts_codes;

  const { data } = await client.get("/api/aggregated/review", { params });
  return data;
}

/**
 * 灵活的数据聚合接口
 * 可以按需获取数据，避免过度获取
 */
export async function fetchFlexibleData(request: FlexibleDataRequest): Promise<any> {
  const { data } = await client.post("/api/aggregated/flexible", request);
  return data;
}

// React Query Hook helpers（如果项目使用React Query）
export const aggregatedKeys = {
  dashboard: (date?: string) => ['aggregated', 'dashboard', date] as const,
  watchlist: (date?: string) => ['aggregated', 'watchlist', date] as const,
  transactions: (page: number, size: number) => ['aggregated', 'transactions', page, size] as const,
  review: (start: string, end: string, ts_codes?: string) => ['aggregated', 'review', start, end, ts_codes] as const,
  flexible: (request: FlexibleDataRequest) => ['aggregated', 'flexible', request] as const,
};

// 性能优化hooks - 带缓存的版本
export class AggregatedDataCache {
  private cache = new Map<string, { data: any; timestamp: number }>();
  private readonly TTL = 30 * 1000; // 30秒缓存

  private getCacheKey(endpoint: string, params: any): string {
    return `${endpoint}:${JSON.stringify(params)}`;
  }

  private isValid(timestamp: number): boolean {
    return Date.now() - timestamp < this.TTL;
  }

  async fetchWithCache<T>(
    endpoint: string,
    params: any,
    fetcher: () => Promise<T>
  ): Promise<T> {
    const key = this.getCacheKey(endpoint, params);
    const cached = this.cache.get(key);

    if (cached && this.isValid(cached.timestamp)) {
      return cached.data as T;
    }

    const data = await fetcher();
    this.cache.set(key, { data, timestamp: Date.now() });
    return data;
  }

  clear(): void {
    this.cache.clear();
  }
}

// 全局缓存实例
export const aggregatedCache = new AggregatedDataCache();

/**
 * 带缓存的Dashboard数据获取
 */
export async function fetchDashboardFullCached(date?: string): Promise<DashboardFullResponse> {
  return aggregatedCache.fetchWithCache(
    'dashboard',
    { date },
    () => fetchDashboardFull(date)
  );
}

/**
 * 带缓存的Watchlist数据获取
 */
export async function fetchWatchlistFullCached(date?: string): Promise<WatchlistFullResponse> {
  return aggregatedCache.fetchWithCache(
    'watchlist',
    { date },
    () => fetchWatchlistFull(date)
  );
}

/**
 * 带缓存的Transaction数据获取
 */
export async function fetchTransactionPageCached(page: number = 1, size: number = 20): Promise<TransactionPageResponse> {
  return aggregatedCache.fetchWithCache(
    'transactions',
    { page, size },
    () => fetchTransactionPage(page, size)
  );
}

/**
 * 性能监控工具 - 对比聚合API与原始API的性能
 */
export interface PerformanceMetrics {
  endpoint: string;
  startTime: number;
  endTime: number;
  duration: number;
  requestCount: number;
  cacheHit: boolean;
}

export class PerformanceMonitor {
  private metrics: PerformanceMetrics[] = [];

  startTracking(endpoint: string, requestCount: number = 1, cacheHit: boolean = false): number {
    const startTime = performance.now();
    const id = this.metrics.length;

    this.metrics.push({
      endpoint,
      startTime,
      endTime: 0,
      duration: 0,
      requestCount,
      cacheHit
    });

    return id;
  }

  endTracking(id: number): PerformanceMetrics {
    const metric = this.metrics[id];
    if (metric) {
      metric.endTime = performance.now();
      metric.duration = metric.endTime - metric.startTime;
    }
    return metric;
  }

  getMetrics(): PerformanceMetrics[] {
    return [...this.metrics];
  }

  getSummary(): { averageDuration: number; totalRequests: number; cacheHitRate: number } {
    const metrics = this.metrics.filter(m => m.endTime > 0);
    const totalRequests = metrics.reduce((sum, m) => sum + m.requestCount, 0);
    const cacheHits = metrics.filter(m => m.cacheHit).length;
    const averageDuration = metrics.reduce((sum, m) => sum + m.duration, 0) / metrics.length;

    return {
      averageDuration,
      totalRequests,
      cacheHitRate: cacheHits / metrics.length
    };
  }

  clear(): void {
    this.metrics = [];
  }
}

// 全局性能监控实例
export const performanceMonitor = new PerformanceMonitor();

/**
 * 带性能监控的数据获取装饰器
 */
export function withPerformanceTracking<T extends (...args: any[]) => Promise<any>>(
  fn: T,
  endpoint: string,
  requestCount: number = 1
): T {
  return (async (...args: any[]) => {
    const id = performanceMonitor.startTracking(endpoint, requestCount);
    try {
      const result = await fn(...args);
      performanceMonitor.endTracking(id);
      return result;
    } catch (error) {
      performanceMonitor.endTracking(id);
      throw error;
    }
  }) as T;
}