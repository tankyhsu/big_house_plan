import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { Card, DatePicker, Space, Button } from "antd";
import dayjs, { Dayjs } from "dayjs";
import { fetchDashboardAgg } from "../../api/hooks";

// 备用：按步长生成日期序列（当前未使用）

// 金额显示友好化（万/亿）
function formatMoney(n: number) {
  if (n >= 1e8) return (n / 1e8).toFixed(2) + " 亿";
  if (n >= 1e4) return (n / 1e4).toFixed(2) + " 万";
  return n.toFixed(0);
}

export default function TotalAssetsLine() {
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().subtract(180, "day"), dayjs()]);
  const [series, setSeries] = useState<{ date: string; value: number }[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const totalDays = range[1].diff(range[0], "day") + 1;
    // 选择后端聚合的 period
    let period: "day" | "week" | "month" = "day";
    if (totalDays <= 100) period = "day";
    else if (totalDays <= 400) period = "week"; // ~52点/年
    else period = "month"; // 长周期用月

    setLoading(true);
    const start = range[0].format("YYYYMMDD");
    const end = range[1].format("YYYYMMDD");
    fetchDashboardAgg(start, end, period)
      .then((res) => {
        const rows = (res.items || []).map((it) => ({ date: it.date, value: Number((it.market_value || 0).toFixed(2)) }));
        setSeries(rows);
      })
      .catch(() => setSeries([]))
      .finally(() => setLoading(false));
  }, [range]);

  const option = useMemo(() => {
    const x = series.map((s) => s.date);   // 'YYYY-MM-DD'
    const y = series.map((s) => s.value);

    // 自适应窄区间：加呼吸空间，避免Y轴贴边 & 被截断
    let yMin: number | undefined = undefined;
    let yMax: number | undefined = undefined;
    if (y.length > 0) {
      const minVal = Math.min(...y);
      const maxVal = Math.max(...y);
      const span = Math.max(1, maxVal - minVal);
      const pad = Math.max(span * 0.15, maxVal * 0.005);
      yMin = Math.max(0, minVal - pad);
      yMax = maxVal + pad;
    }

    // 标注阶段高/低点
    const markPoint =
      y.length > 0
        ? {
            data: [
              { type: "max", name: "阶段高点" },
              { type: "min", name: "阶段低点" },
            ],
            symbolSize: 40,
            label: {
              formatter: (p: any) => `${p.name}\n${formatMoney(p.value)}`,
              fontSize: 10,
            },
          }
        : undefined;

    const markLine =
      y.length > 0
        ? {
            data: [{ type: "average", name: "均值" }],
            label: { formatter: (p: any) => `均值：${formatMoney(p.value)}`, fontSize: 10 },
          }
        : undefined;

    // 根据区间长度自适应X轴刻度密度
    const totalDays = series.length > 1
      ? dayjs(series[series.length - 1].date).diff(dayjs(series[0].date), "day") + 1
      : 0;

    const xLabelInterval = (index: number, value: string) => {
      const isFirst = index === 0;
      const isLast = index === x.length - 1;
      const d = dayjs(value, "YYYY-MM-DD");
      if (isFirst || isLast) return true;
      if (totalDays <= 100) {
        // 近3个月：每周一标注
        return d.day() === 1;
      } else if (totalDays <= 200) {
        // 近6个月：每月1日与15日
        const day = d.date();
        return day === 1 || day === 15;
      } else if (totalDays <= 400) {
        // 近1年：每月1日
        return d.date() === 1;
      } else {
        // 更长：每季度首月1日（1/4/7/10）
        const m = d.month() + 1;
        return d.date() === 1 && (m === 1 || m === 4 || m === 7 || m === 10);
      }
    };

    return {
      tooltip: {
        trigger: "axis",
        valueFormatter: (v: any) => `${formatMoney(Number(v))}`,
      },
      grid: { left: 24, right: 32, top: 28, bottom: 28, containLabel: true },
      xAxis: {
        type: "category",
        data: x,
        boundaryGap: false,
        axisTick: { alignWithLabel: true },
        axisLabel: {
          interval: xLabelInterval as any,
          formatter: (val: string) => dayjs(val).format("YYYY-MM"),
          rotate: 0,
          hideOverlap: true,
          margin: 12,
        },
      },
      yAxis: {
        type: "value",
        scale: true,
        min: yMin,
        max: yMax,
        splitNumber: 5,
        axisLabel: { formatter: (val: number) => formatMoney(val), margin: 10 },
        splitLine: { show: true },
        axisLine: { show: true },
        axisTick: { show: true },
      },
      series: [
        {
          type: "line",
          smooth: true,
          data: y,
          showSymbol: false,
          sampling: "lttb", // 大量点时自动抽稀，保留趋势与极值
          markPoint,
          markLine,
          endLabel: {
            show: y.length > 0,
            formatter: (p: any) => formatMoney(p.value),
            distance: 6,
            fontSize: 10,
          },
        },
      ],
      // 如需拖拽缩放，可以打开 dataZoom
      dataZoom: [{ type: "inside" }, { type: "slider" }],
    };
  }, [series]);

  return (
    <Card
      title="总资产变化（市值）"
      size="small"
      extra={
        <Space>
          <Button size="small" onClick={() => setRange([dayjs().subtract(3, "month"), dayjs()])}>近3月</Button>
          <Button size="small" onClick={() => setRange([dayjs().subtract(6, "month"), dayjs()])}>近6月</Button>
          <Button size="small" onClick={() => setRange([dayjs().subtract(1, "year"), dayjs()])}>近1年</Button>
          <Button size="small" onClick={() => setRange([dayjs().subtract(3, "year"), dayjs()])}>近3年</Button>
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
      <ReactECharts notMerge lazyUpdate option={option as any} style={{ height: 340 }} />
    </Card>
  );
}
