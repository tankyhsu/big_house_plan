import { useEffect, useState } from "react";
import { Card, DatePicker, Space, Button, Tag, Switch } from "antd";
import dayjs, { Dayjs } from "dayjs";
import HistoricalLineChart, { type SeriesEntry } from "./HistoricalLineChart";
import { usePositionSeries } from "./usePositionSeries";

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

  const { loading: hookLoading, series: hookSeries } = usePositionSeries(tsCodes, range);
  useEffect(() => { setSeries(hookSeries); setLoading(hookLoading); }, [hookLoading, hookSeries]);

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
      bodyStyle={{ padding: 12 }}
      loading={loading}
    >
      {(!tsCodes || tsCodes.length === 0) ? (
        <Tag color="gold">请选择至少一个标的</Tag>
      ) : (
        <HistoricalLineChart series={series} normalize={useIndexed} />
      )}
    </Card>
  );
}
