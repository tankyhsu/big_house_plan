import { useEffect, useState } from "react";
import dayjs from "dayjs";
import { fetchAllSignals } from "../api/hooks";
import type { SignalRow } from "../api/types";

/**
 * 获取最近一个月内的信号数据
 * @param tsCode 可选，指定标的代码
 * @param limit 最多获取的信号数量
 */
export const useRecentSignals = (tsCode?: string, limit: number = 10) => {
  const [signals, setSignals] = useState<SignalRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const loadSignals = async () => {
      setLoading(true);
      try {
        const oneMonthAgo = dayjs().subtract(1, "month").format("YYYY-MM-DD");
        const today = dayjs().format("YYYY-MM-DD");
        const data = await fetchAllSignals(undefined, tsCode, oneMonthAgo, today, limit);
        setSignals(data || []);
      } catch (error) {
        console.error("Failed to load recent signals:", error);
        setSignals([]);
      } finally {
        setLoading(false);
      }
    };

    loadSignals();
  }, [tsCode, limit]);

  return { signals, loading };
};

/**
 * 从信号列表中获取特定标的的信号
 * @param allSignals 所有信号数据
 * @param tsCode 标的代码
 * @returns 该标的的信号，按日期倒序排列
 */
export const getSignalsForTsCode = (allSignals: SignalRow[] | null | undefined, tsCode: string): SignalRow[] => {
  if (!allSignals || !Array.isArray(allSignals)) {
    return [];
  }
  return allSignals
    .filter(s => s.ts_code === tsCode)
    .sort((a, b) => b.trade_date.localeCompare(a.trade_date));
};