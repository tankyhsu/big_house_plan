import { useEffect, useState } from "react";
import { Card, DatePicker, Space, Button, Tag, Switch } from "antd";
import dayjs, { Dayjs } from "dayjs";
import HistoricalLineChart, { type SeriesEntry, type TradeEvent } from "./HistoricalLineChart";
import { usePositionSeries } from "./usePositionSeries";
import { fetchLastPrice, fetchTxnRange } from "../../api/hooks";

type Props = {
  tsCodes: string[];            // 一个或多个 ts_code
  title?: string;
  normalize?: boolean;          // 归一化比较（起点=100）
};

// 保留空实现占位（历史遗留格式器已迁移至基础组件）

export default function PositionSeriesLine({ tsCodes, title, normalize = false }: Props) {
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().subtract(180, "day"), dayjs()]);
  const [loading, setLoading] = useState(false);
  const [series, setSeries] = useState<Record<string, SeriesEntry>>({});
  const [useIndexed, setUseIndexed] = useState<boolean>(normalize);
  const [eventsByCode, setEventsByCode] = useState<Record<string, TradeEvent[]>>({});
  const [lastPriceMap, setLastPriceMap] = useState<Record<string, number | null>>({});

  const { loading: hookLoading, series: hookSeries } = usePositionSeries(tsCodes, range);
  useEffect(() => { setSeries(hookSeries); setLoading(hookLoading); }, [hookLoading, hookSeries]);

  // 拉取交易点 & 末尾日价格
  useEffect(() => {
    if (!tsCodes || tsCodes.length === 0) { setEventsByCode({}); setLastPriceMap({}); return; }
    const start = range[0].format("YYYYMMDD");
    const end = range[1].format("YYYYMMDD");
    fetchTxnRange(start, end, tsCodes).then(res => {
      const map: Record<string, TradeEvent[]> = {};
      (res.items || []).forEach(it => {
        if (it.action !== "BUY" && it.action !== "SELL") return; // 只标记买卖
        const code = it.ts_code;
        if (!map[code]) map[code] = [];
        map[code].push({ date: it.date, action: it.action, price: it.price });
      });
      // 每个code按日期排序
      Object.keys(map).forEach(k => map[k].sort((a,b) => a.date.localeCompare(b.date)));
      setEventsByCode(map);
    }).catch(() => setEventsByCode({}));

    Promise.all(tsCodes.map(c => fetchLastPrice(c, end).then(r => [c, r.close] as const).catch(() => [c, null] as const)))
      .then(entries => {
        const prices: Record<string, number | null> = {};
        entries.forEach(([c, p]) => { prices[c] = (typeof p === 'number' ? p : null); });
        setLastPriceMap(prices);
      })
      .catch(() => setLastPriceMap({}));
  }, [JSON.stringify(tsCodes), range[0].valueOf(), range[1].valueOf()]);

  return (
    <Card
      title={title || (tsCodes.length > 1 ? "持仓市值变化对比" : "持仓市值变化")}
      size="small"
      extra={
        <Space>
          <Button size="small" onClick={() => setRange([dayjs().subtract(3, "month"), dayjs()])}>近3月</Button>
          <Button size="small" onClick={() => setRange([dayjs().subtract(6, "month"), dayjs()])}>近6月</Button>
          <Button size="small" onClick={() => setRange([dayjs().subtract(1, "year"), dayjs()])}>近1年</Button>
          <Button size="small" onClick={() => setRange([dayjs().subtract(3, "year"), dayjs()])}>近3年</Button>
          <span style={{ marginLeft: 8 }}>归一化</span>
          <Switch size="small" checked={useIndexed} onChange={setUseIndexed} />
          <DatePicker.RangePicker
            value={range}
            allowClear={false}
            onChange={(v) => {
              if (!v || !v[0] || !v[1]) return;
              setRange([v[0], v[1]]);
            }}
          />
        </Space>
      }
      styles={{ body: { padding: 12 } }}
      loading={loading}
    >
      {(!tsCodes || tsCodes.length === 0) ? (
        <Tag color="gold">请选择至少一个标的</Tag>
      ) : (
        <HistoricalLineChart series={series} normalize={useIndexed} eventsByCode={eventsByCode} lastPriceMap={lastPriceMap} />
      )}
    </Card>
  );
}
