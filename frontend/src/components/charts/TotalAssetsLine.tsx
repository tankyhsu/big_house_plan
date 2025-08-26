import React, { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { Card, DatePicker, Space } from "antd";
import dayjs, { Dayjs } from "dayjs";
import { fetchDashboard } from "../../api/hooks";

function genDateRange(start: Dayjs, end: Dayjs) {
  const arr: string[] = [];
  let d = start.startOf("day");
  while (d.isBefore(end) || d.isSame(end, "day")) {
    arr.push(d.format("YYYYMMDD"));
    d = d.add(1, "day");
  }
  return arr;
}

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
    const dates = genDateRange(range[0], range[1]);
    setLoading(true);
    Promise.all(dates.map((d) => fetchDashboard(d).catch(() => null)))
      .then((resList) => {
        const rows = resList
          .map((res, i) => {
            const dashDate = dayjs(dates[i], "YYYYMMDD").format("YYYY-MM-DD");
            const mv = res?.kpi?.market_value ?? null;
            return mv != null ? { date: dashDate, value: Number(mv.toFixed(2)) } : null;
          })
          .filter(Boolean) as { date: string; value: number }[];
        setSeries(rows);
      })
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

    // 仅在每月1号显示X轴刻度标签；首尾保留
    const xLabelInterval = (index: number, value: string) => {
      const isFirst = index === 0;
      const isLast = index === x.length - 1;
      const isMonthStart = dayjs(value, "YYYY-MM-DD").date() === 1;
      return isFirst || isLast || isMonthStart;
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
      <ReactECharts notMerge lazyUpdate option={option as any} style={{ height: 340 }} />
    </Card>
  );
}