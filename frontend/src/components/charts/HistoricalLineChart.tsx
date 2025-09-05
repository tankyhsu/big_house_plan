import ReactECharts from "echarts-for-react";
import dayjs from "dayjs";
import { useMemo } from "react";
import { formatQuantity, formatPrice } from "../../utils/format";
import { getSignalConfig, getSignalPriority } from "../../utils/signalConfig";
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
      codes.forEach((code) => {
        const entry = series[code];
        const pts = entry?.points || [];
        const first = pts.find((p) => p && typeof p.value === "number" && p.value !== null);
        const base = first && typeof first.value === "number" ? Number(first.value) : 0;
        const events = eventsByCode[code] || [];
        if (events.length === 0) return;

        // 分别处理买入和卖出事件
        const buyEvents = events.filter(ev => ev.action === "BUY");
        const sellEvents = events.filter(ev => ev.action === "SELL");

        // 添加买入标记
        if (buyEvents.length > 0) {
          const buyData = buyEvents.map((ev) => {
            const p = pts.find((pt) => pt.date === ev.date);
            const y = p && p.value != null
              ? (normalize && base > 0 ? Number(formatQuantity((Number(p.value) / base) * 100)) : Number(p.value))
              : null;
            return { value: [ev.date, y], ev };
          });

          sers.push({
            name: `${entry?.name || code}-买入`,
            type: "scatter",
            data: buyData.map(d => ({
              ...d,
              tradeData: d.ev
            })),
            symbol: "triangle",
            symbolSize: 12,
            itemStyle: {
              color: "#2ecc71",
              borderColor: '#fff',
              borderWidth: 2,
              shadowColor: "#2ecc71",
              shadowBlur: 6,
              shadowOffsetY: 2
            },
            z: 3,
          });
        }

        // 添加卖出标记
        if (sellEvents.length > 0) {
          const sellData = sellEvents.map((ev) => {
            const p = pts.find((pt) => pt.date === ev.date);
            const y = p && p.value != null
              ? (normalize && base > 0 ? Number(formatQuantity((Number(p.value) / base) * 100)) : Number(p.value))
              : null;
            return { value: [ev.date, y], ev };
          });

          sers.push({
            name: `${entry?.name || code}-卖出`,
            type: "scatter", 
            data: sellData.map(d => ({
              ...d,
              tradeData: d.ev
            })),
            symbol: "triangle",
            symbolSize: 12,
            symbolRotate: 180, // 卖出三角形倒转
            itemStyle: {
              color: "#e74c3c",
              borderColor: '#fff',
              borderWidth: 2,
              shadowColor: "#e74c3c",
              shadowBlur: 6,
              shadowOffsetY: 2
            },
            z: 3,
          });
        }
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
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        borderColor: 'transparent',
        textStyle: {
          color: '#fff',
          fontSize: 12
        },
        extraCssText: 'border-radius: 6px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);',
        formatter: (params: any[]) => {
          if (!Array.isArray(params) || params.length === 0) return '';
          
          const date = params[0].axisValue;
          const lineParams = params.filter(p => p.seriesType === 'line');
          const scatterParams = params.filter(p => p.seriesType === 'scatter');
          
          let html = `<div style="padding: 8px;">`;
          
          // Date header
          html += `<div style="font-weight: bold; font-size: 13px; margin-bottom: 8px; color: #fff; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 6px;">${dayjs(date).format('YYYY-MM-DD')}</div>`;
          
          // Line series (market values)
          if (lineParams.length > 0) {
            html += `<div style="margin-bottom: 8px;">`;
            lineParams.forEach((param, idx) => {
              const value = param.value;
              if (value != null) {
                const displayValue = normalize ? `${formatQuantity(Number(value))}` : `${formatMoney(Number(value))}`;
                const seriesColor = param.color || '#42a5f5';
                html += `<div style="display: flex; align-items: center; margin-bottom: 4px;">`;
                html += `<span style="color: ${seriesColor};">●</span>`;
                html += `<span style="color: #ccc; margin: 0 6px;">${param.seriesName}:</span>`;
                html += `<span style="color: ${seriesColor}; font-weight: bold;">${displayValue}</span>`;
                html += `</div>`;
              }
            });
            html += `</div>`;
          }
          
          // Find trading events for this date from scatter series
          const tradingEvents: Array<{code: string, name: string, event: TradeEvent}> = [];
          const scatterTradeSeries = params.filter(p => 
            p.seriesType === 'scatter' && 
            (p.seriesName.includes('-买入') || p.seriesName.includes('-卖出')) &&
            p.data?.ev
          );
          
          scatterTradeSeries.forEach(param => {
            const event = param.data.ev;
            const seriesName = param.seriesName;
            const code = seriesName.replace('-买入', '').replace('-卖出', '');
            const entry = series[code];
            
            tradingEvents.push({
              code,
              name: entry?.name || code,
              event
            });
          });
          
          // Trading events section - styled like signals
          if (tradingEvents.length > 0) {
            html += `<div style="border-top: 1px solid rgba(255,255,255,0.2); margin-top: 8px; padding-top: 8px;">`;
            html += `<div style="font-weight: bold; font-size: 12px; margin-bottom: 6px; color: #fff;">💼 交易记录</div>`;
            
            tradingEvents.forEach(({code, name, event}) => {
              const action = event.action === 'BUY' ? '买入' : '卖出';
              const actionColor = event.action === 'BUY' ? '#2ecc71' : '#e74c3c';
              const actionIcon = event.action === 'BUY' ? '📈' : '📉';
              const price = event.price != null ? formatPrice(event.price) : '—';
              
              // Calculate return if we have current price
              let returnInfo = '';
              if (lastPriceMap && lastPriceMap[code] != null && event.price != null) {
                const currentPrice = lastPriceMap[code]!;
                const returnPct = ((currentPrice - event.price) / event.price) * 100;
                const returnColor = returnPct >= 0 ? '#2ecc71' : '#e74c3c';
                returnInfo = `<span style="color: ${returnColor}; font-size: 10px; margin-left: 8px;">(${returnPct >= 0 ? '+' : ''}${formatQuantity(returnPct)}%)</span>`;
              }
              
              html += `<div style="margin-bottom: 6px; padding: 4px 0;">`;
              html += `<div style="display: flex; align-items: center; margin-bottom: 2px;">`;
              html += `<span style="font-size: 14px; margin-right: 4px;">${actionIcon}</span>`;
              html += `<span style="color: ${actionColor}; font-weight: bold; font-size: 12px;">${action}</span>`;
              html += `<span style="color: #ccc; font-size: 11px; margin-left: 6px;">${name}</span>`;
              html += `</div>`;
              html += `<div style="color: #ccc; font-size: 11px; line-height: 1.4; margin-left: 20px;">成交价: <span style="color: ${actionColor}; font-weight: bold;">${price}</span>${returnInfo}</div>`;
              html += `</div>`;
            });
            
            html += `</div>`;
          }
          
          // Find signals for this date across all codes
          const signalsOnDate: SignalRow[] = [];
          if (signalsByCode && Object.keys(signalsByCode).length > 0) {
            Object.values(signalsByCode).forEach(signalList => {
              signalList.forEach(signal => {
                if (signal.trade_date === date) {
                  signalsOnDate.push(signal);
                }
              });
            });
          }
          
          // Remove duplicate signals (same type and message on same date)
          const uniqueSignals = signalsOnDate.filter((signal, index, arr) => {
            return arr.findIndex(s => s.type === signal.type && s.message === signal.message) === index;
          });
          
          // Signals section
          if (uniqueSignals.length > 0) {
            html += `<div style="border-top: 1px solid rgba(255,255,255,0.2); margin-top: 8px; padding-top: 8px;">`;
            html += `<div style="font-weight: bold; font-size: 12px; margin-bottom: 6px; color: #fff;">📡 交易信号</div>`;
            
            uniqueSignals.forEach(signal => {
              const config = getSignalConfig(signal.type);
              
              // Signal level badge
              let levelBadge = '';
              if (signal.level) {
                let levelColor = '#666';
                let levelText = '';
                switch(signal.level) {
                  case 'HIGH': levelColor = '#ff4757'; levelText = '高'; break;
                  case 'MEDIUM': levelColor = '#ff9500'; levelText = '中'; break;
                  case 'LOW': levelColor = '#5352ed'; levelText = '低'; break;
                  case 'INFO': levelColor = '#747d8c'; levelText = '信息'; break;
                }
                levelBadge = `<span style="background: ${levelColor}; color: white; font-size: 10px; padding: 1px 4px; border-radius: 2px; margin-left: 4px;">${levelText}</span>`;
              }
              
              html += `<div style="margin-bottom: 6px; padding: 4px 0;">`;
              html += `<div style="display: flex; align-items: center; margin-bottom: 2px;">`;
              html += `<span style="font-size: 14px; margin-right: 4px;">${config.emoji}</span>`;
              html += `<span style="color: ${config.color}; font-weight: bold; font-size: 12px;">${config.name}</span>`;
              html += levelBadge;
              html += `</div>`;
              html += `<div style="color: #ccc; font-size: 11px; line-height: 1.4; margin-left: 20px;">${signal.message}</div>`;
              html += `</div>`;
            });
            
            html += `</div>`;
          }
          
          html += `</div>`;
          return html;
        }
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
