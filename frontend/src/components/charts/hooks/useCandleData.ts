import { useEffect, useState } from "react";
import dayjs, { Dayjs } from "dayjs";
import { fetchOhlcRange, fetchTxnRange, type OhlcItem } from "../../../api/hooks";

export type CandleRange = [Dayjs, Dayjs];

export function useCandleData(params: { tsCode: string; months?: number }) {
  const { tsCode, months = 6 } = params;
  const [items, setItems] = useState<OhlcItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [range, setRange] = useState<CandleRange>(() => [dayjs().subtract(months, "month"), dayjs()]);
  const [buys, setBuys] = useState<{ date: string; price: number }[]>([]);
  const [sells, setSells] = useState<{ date: string; price: number }[]>([]);

  // OHLC data
  useEffect(() => {
    if (!tsCode) { setItems([]); return; }
    setLoading(true);
    const [start, end] = range;
    fetchOhlcRange(tsCode, start.format("YYYYMMDD"), end.format("YYYYMMDD"))
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [tsCode, range[0].valueOf(), range[1].valueOf()]);

  // Txn markers
  useEffect(() => {
    if (!tsCode) { setBuys([]); setSells([]); return; }
    const [start, end] = range;
    fetchTxnRange(start.format("YYYYMMDD"), end.format("YYYYMMDD"), [tsCode])
      .then(res => {
        const closeMap = new Map<string, number>();
        items.forEach(it => closeMap.set(it.date, it.close));
        const b: { date: string; price: number }[] = [];
        const s: { date: string; price: number }[] = [];
        (res.items || []).forEach(it => {
          const y = typeof it.price === 'number' ? it.price : (closeMap.get(it.date) ?? 0);
          if (it.action === 'BUY') b.push({ date: it.date, price: y });
          if (it.action === 'SELL') s.push({ date: it.date, price: y });
        });
        setBuys(b); setSells(s);
      })
      .catch(() => { setBuys([]); setSells([]); });
  }, [tsCode, range[0].valueOf(), range[1].valueOf(), items.length]);

  return { items, loading, range, setRange, buys, sells } as const;
}

