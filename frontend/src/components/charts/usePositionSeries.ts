import { useEffect, useState } from "react";
import { Dayjs } from "dayjs";
import { fetchPositionSeries } from "../../api/hooks";
import type { SeriesEntry } from "./HistoricalLineChart";
import { formatQuantity } from "../../utils/format";

export function usePositionSeries(codes: string[], range: [Dayjs, Dayjs]) {
  const [loading, setLoading] = useState(false);
  const [series, setSeries] = useState<Record<string, SeriesEntry>>({});

  useEffect(() => {
    if (!codes || codes.length === 0) { setSeries({}); return; }
    const start = range[0].format("YYYYMMDD");
    const end = range[1].format("YYYYMMDD");
    setLoading(true);
    fetchPositionSeries(start, end, codes)
      .then(res => {
        const map: Record<string, SeriesEntry> = {};
        (res.items || []).forEach(r => {
          const k = r.ts_code;
          if (!map[k]) map[k] = { name: r.name || r.ts_code, points: [] };
          map[k].points.push({ date: r.date, value: Number(formatQuantity(r.market_value || 0)) });
        });
        Object.values(map).forEach(s => s.points.sort((a,b) => a.date.localeCompare(b.date)));
        setSeries(map);
      })
      .catch(() => setSeries({}))
      .finally(() => setLoading(false));
  }, [JSON.stringify(codes), range[0].valueOf(), range[1].valueOf()]);

  return { loading, series } as const;
}
