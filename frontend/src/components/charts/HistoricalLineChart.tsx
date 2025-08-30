import ReactECharts from "echarts-for-react";
import dayjs from "dayjs";
import { useMemo } from "react";

export type SeriesPoint = { date: string; value: number | null };
export type SeriesEntry = { name: string; points: SeriesPoint[] };

type Props = {
  series: Record<string, SeriesEntry>; // key 可以是 ts_code
  normalize?: boolean;                 // 起点=100 的相对比较
  height?: number;                     // 图高，默认 340
};

function formatMoney(n: number) {
  if (n >= 1e8) return (n / 1e8).toFixed(2) + " 亿";
  if (n >= 1e4) return (n / 1e4).toFixed(2) + " 万";
  return n.toFixed(0);
}

export default function HistoricalLineChart({ series, normalize = false, height = 340 }: Props) {
  const option = useMemo(() => {
    const codes = Object.keys(series || {});
    const x: string[] = Array.from(
      new Set(codes.flatMap((c) => (series[c]?.points || []).map((p) => p.date)))
    ).sort((a, b) => a.localeCompare(b));

    const sers = codes.map((code) => {
      const entry = series[code];
      const pts = entry?.points || [];
      const first = pts.find((p) => p && typeof p.value === "number" && p.value !== null);
      const base = first && typeof first.value === "number" ? Number(first.value) : 0;
      const data = x.map((d) => {
        const p = pts.find((pt) => pt.date === d);
        const v = p ? p.value : null;
        if (v == null) return null;
        return normalize && base > 0 ? Number(((Number(v) / base) * 100).toFixed(2)) : Number(v);
      });
      return {
        name: entry?.name || code,
        type: "line" as const,
        smooth: true,
        showSymbol: false,
        sampling: "lttb" as const,
        data,
        endLabel: {
          show: true,
          formatter: (p: any) => {
            const v = Number(p.value || 0);
            return normalize ? `${entry?.name || code}: ${v.toFixed(1)}` : `${entry?.name || code}: ${formatMoney(v)}`;
          },
          distance: 6,
          fontSize: 10,
        },
      };
    });

    return {
      tooltip: {
        trigger: "axis",
        valueFormatter: (v: any) => (normalize ? `${Number(v).toFixed(1)}` : `${formatMoney(Number(v))}`),
      },
      legend: { type: "scroll", top: 0 },
      grid: { left: 24, right: 32, top: 36, bottom: 28, containLabel: true },
      xAxis: {
        type: "category",
        data: x,
        boundaryGap: false,
        axisLabel: { formatter: (val: string) => dayjs(val).format("YYYY-MM"), margin: 12 },
      },
      yAxis: { type: "value", scale: true, axisLabel: { formatter: (val: number) => (normalize ? `${val}` : formatMoney(val)), margin: 10 } },
      series: sers,
      dataZoom: [{ type: "inside" }, { type: "slider" }],
    };
  }, [series, normalize]);

  return <ReactECharts notMerge lazyUpdate option={option as any} style={{ height }} />;
}

