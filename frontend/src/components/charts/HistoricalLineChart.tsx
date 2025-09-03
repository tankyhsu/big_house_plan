import ReactECharts from "echarts-for-react";
import dayjs from "dayjs";
import { useMemo } from "react";
import { formatQuantity, formatPrice } from "../../utils/format";
import { getSignalConfig, getSignalPriority } from "../../utils/signalUtils";
import type { SignalRow } from "../../api/types";

export type SeriesPoint = { date: string; value: number | null };
export type SeriesEntry = { name: string; points: SeriesPoint[] };
export type TradeEvent = { date: string; action: "BUY"|"SELL"; price: number | null };

type Props = {
  series: Record<string, SeriesEntry>; // key 可以是 ts_code
  normalize?: boolean;                 // 起点=100 的相对比较
  height?: number;                     // 图高，默认 340
  eventsByCode?: Record<string, TradeEvent[]>; // 交易点，用散点覆盖在折线上
  lastPriceMap?: Record<string, number | null>; // 末尾日价格（用于收益计算）
  signalsByCode?: Record<string, SignalRow[]>; // 信号数据，按标的分组
};

function formatMoney(n: number) {
  if (n >= 1e8) return formatQuantity(n / 1e8) + " 亿";
  if (n >= 1e4) return formatQuantity(n / 1e4) + " 万";
  return formatQuantity(n);
}

export default function HistoricalLineChart({ series, normalize = false, height = 340, eventsByCode, lastPriceMap, signalsByCode }: Props) {
  const option = useMemo(() => {
    const codes = Object.keys(series || {});
    const x: string[] = Array.from(
      new Set(codes.flatMap((c) => (series[c]?.points || []).map((p) => p.date)))
    ).sort((a, b) => a.localeCompare(b));

    const sers: any[] = codes.map((code) => {
      const entry = series[code];
      const pts = entry?.points || [];
      const first = pts.find((p) => p && typeof p.value === "number" && p.value !== null);
      const base = first && typeof first.value === "number" ? Number(first.value) : 0;
      const data = x.map((d) => {
        const p = pts.find((pt) => pt.date === d);
        const v = p ? p.value : null;
        if (v == null) return null;
        return normalize && base > 0 ? Number(formatQuantity((Number(v) / base) * 100)) : Number(v);
      });
      const lineSeriesConfig: any = {
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
            return normalize ? `${entry?.name || code}: ${formatQuantity(v)}` : `${entry?.name || code}: ${formatMoney(v)}`;
          },
          distance: 6,
          fontSize: 10,
        },
      };

      return lineSeriesConfig;
    });

    // 叠加交易点（BUY/SELL）
    if (eventsByCode && Object.keys(eventsByCode).length > 0) {
      const symbolFor = (act: string) => (act === "BUY" ? "triangle" : "rect");
      const colorFor = (act: string) => (act === "BUY" ? "#2ecc71" : "#e74c3c");
      codes.forEach((code) => {
        const entry = series[code];
        const pts = entry?.points || [];
        const first = pts.find((p) => p && typeof p.value === "number" && p.value !== null);
        const base = first && typeof first.value === "number" ? Number(first.value) : 0;
        const events = eventsByCode[code] || [];
        if (events.length === 0) return;
        const data = events.map((ev) => {
          const p = pts.find((pt) => pt.date === ev.date);
          const y = p && p.value != null
            ? (normalize && base > 0 ? Number(formatQuantity((Number(p.value) / base) * 100)) : Number(p.value))
            : null;
          return { value: [ev.date, y], ev };
        });
        sers.push({
          name: `${entry?.name || code}-交易`,
          type: "scatter",
          data,
          symbolSize: 10,
          tooltip: {
            trigger: "item",
            formatter: (p: any) => {
              const ev = p.data?.ev as TradeEvent;
              const lp = lastPriceMap ? lastPriceMap[code] : null;
              let retTxt = "";
              if (ev?.price != null && lp != null) {
                const r = ((lp - ev.price) / ev.price) * 100;
                retTxt = `，距今：${formatQuantity(r)}%`;
              }
              const action = ev?.action === "BUY" ? "买入" : "卖出";
              const px = ev?.price != null ? formatPrice(ev.price) : "—";
              return `${entry?.name || code}｜${action}<br/>日期：${dayjs(p.value[0]).format("YYYY-MM-DD")}<br/>成交价：${px}${retTxt}`;
            },
          },
          itemStyle: {
            color: (params: any) => colorFor(params.data?.ev?.action),
          },
          symbol: (val: any) => symbolFor(val?.ev?.action),
          z: 3,
        });
      });
    }

    // 叠加信号标记（竖直线）- 与K线图保持一致的颜色配置
    const markLines: any[] = [];
    if (signalsByCode && Object.keys(signalsByCode).length > 0) {
      // 收集所有信号，按日期去重
      const allSignalsByDate: Record<string, SignalRow[]> = {};
      codes.forEach(code => {
        const signals = signalsByCode[code] || [];
        signals.forEach(signal => {
          if (!allSignalsByDate[signal.trade_date]) {
            allSignalsByDate[signal.trade_date] = [];
          }
          allSignalsByDate[signal.trade_date].push(signal);
        });
      });

      // 为每个日期创建标记线
      Object.entries(allSignalsByDate).forEach(([date, signals]) => {
        // 按优先级排序
        const sortedSignals = signals.sort((a, b) => getSignalPriority(b.type) - getSignalPriority(a.type));
        
        const primarySignal = sortedSignals[0];
        const config = getSignalConfig(primarySignal.type);
        
        // 合并信号名称显示
        const signalNames = signals.map(s => {
          const cfg = getSignalConfig(s.type);
          return `${cfg.emoji}${cfg.name}`;
        }).join(' ');
        
        markLines.push({
          xAxis: date,
          name: signals.map(s => s.message).join('；'),
          label: {
            position: 'end',
            formatter: signalNames,
            fontSize: 9,
            color: config.color,
            backgroundColor: 'rgba(255,255,255,0.9)',
            padding: [2, 4],
            borderRadius: 3,
            borderColor: config.color,
            borderWidth: 1
          },
          lineStyle: {
            color: config.color,
            type: 'dashed',
            width: 2
          }
        });
      });
    }

    // 将信号标记线添加到第一个线条系列
    if (markLines.length > 0 && sers.length > 0) {
      // 找到第一个线条系列（非散点图）
      const firstLineSeriesIndex = sers.findIndex(s => s.type === "line");
      if (firstLineSeriesIndex >= 0) {
        sers[firstLineSeriesIndex].markLine = {
          data: markLines,
          silent: true
        };
      }
    }

    return {
      tooltip: {
        trigger: "axis",
        valueFormatter: (v: any) => (normalize ? `${formatQuantity(Number(v))}` : `${formatMoney(Number(v))}`),
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
  }, [series, normalize, eventsByCode, lastPriceMap, signalsByCode]);

  return <ReactECharts notMerge lazyUpdate option={option as any} style={{ height }} />;
}
