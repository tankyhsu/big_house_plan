import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { Card, DatePicker, Space, Button } from "antd";
import dayjs, { Dayjs } from "dayjs";
import { fetchDashboardAgg, fetchAllSignals } from "../../api/hooks";
import { formatQuantity } from "../../utils/format";
import { getSignalConfig } from "../../utils/signalConfig";
import type { SignalRow } from "../../api/types";

// 备用：按步长生成日期序列（当前未使用）

// 金额显示友好化（万/亿）
function formatMoney(n: number) {
  if (n >= 1e8) return formatQuantity(n / 1e8) + " 亿";
  if (n >= 1e4) return formatQuantity(n / 1e4) + " 万";
  return formatQuantity(n);
}

export default function TotalAssetsLine() {
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().subtract(180, "day"), dayjs()]);
  const [series, setSeries] = useState<{ date: string; value: number }[]>([]);
  const [signals, setSignals] = useState<SignalRow[]>([]);
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
    const startDate = range[0].format("YYYY-MM-DD");
    const endDate = range[1].format("YYYY-MM-DD");
    
    Promise.all([
      fetchDashboardAgg(start, end, period),
      // 获取全局信号（影响全部标的或类别的信号）
      fetchAllSignals(undefined, undefined, startDate, endDate, 1000)
    ])
      .then(([dashRes, signalsRes]) => {
        const rows = (dashRes.items || []).map((it) => ({ date: it.date, value: Number(formatQuantity(it.market_value || 0)) }));
        setSeries(rows);
        
        // 过滤全局生效的信号
        const globalSignals = signalsRes.filter(signal => 
          !signal.ts_code || // 没有指定具体标的
          signal.scope_type === "ALL_INSTRUMENTS" ||
          signal.scope_type === "ALL_CATEGORIES"
        );
        setSignals(globalSignals);
      })
      .catch(() => {
        setSeries([]);
        setSignals([]);
      })
      .finally(() => setLoading(false));
  }, [range]);

  const option = useMemo(() => {
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

    // 信号标记线 - 与K线图保持一致的颜色配置
    const signalMarkLines = signals.map(signal => {
      const config = getSignalConfig(signal.type);
      return {
        xAxis: signal.trade_date,
        name: `${config.emoji}${config.label}: ${signal.message}`,
        label: {
          position: 'end',
          formatter: `${config.emoji}${config.label}`,
          fontSize: 10,
          color: config.color,
          backgroundColor: 'rgba(255,255,255,0.95)',
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
      };
    });

    const avgMarkLine = y.length > 0 ? {
      type: "average", 
      name: "均值",
      label: { 
        formatter: (p: any) => `均值：${formatMoney(p.value)}`, 
        fontSize: 10 
      }
    } : null;

    const markLine = (y.length > 0 || signalMarkLines.length > 0) ? {
      data: [
        ...(avgMarkLine ? [avgMarkLine] : []),
        ...signalMarkLines
      ]
    } : undefined;
    

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
          const param = Array.isArray(params) ? params[0] : params;
          const date = param.axisValue;
          const value = param.value?.[1] || param.value;
          
          let html = `<div style="padding: 8px;">`;
          
          // Date header
          html += `<div style="font-weight: bold; font-size: 13px; margin-bottom: 8px; color: #fff; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 6px;">${date}</div>`;
          
          // Total assets value
          html += `<div style="margin-bottom: 8px; font-size: 12px;">`;
          html += `<span style="color: #ccc;">总资产:</span> <span style="color: #42a5f5; font-weight: bold; font-size: 14px;">${formatMoney(Number(value))}</span>`;
          html += `</div>`;
          
          // Find signals for this date
          const signalsOnDate = signals.filter(signal => signal.trade_date === date);
          
          // Signals section
          if (signalsOnDate.length > 0) {
            html += `<div style="border-top: 1px solid rgba(255,255,255,0.2); margin-top: 8px; padding-top: 8px;">`;
            html += `<div style="font-weight: bold; font-size: 12px; margin-bottom: 6px; color: #fff;">📡 全局信号</div>`;
            
            signalsOnDate.forEach(signal => {
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
              html += `<span style="color: ${config.color}; font-weight: bold; font-size: 12px;">${config.label}</span>`;
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
      grid: { left: 24, right: 32, top: 28, bottom: 28, containLabel: true },
      xAxis: {
        type: "time",
        boundaryGap: false,
        axisTick: { alignWithLabel: true },
        axisLabel: {
          formatter: (val: number) => dayjs(val).format("YYYY-MM"),
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
          data: series.map(s => [s.date, s.value]),
          showSymbol: false,
          sampling: "lttb", // 大量点时自动抽稀，保留趋势与极值
          markPoint,
          markLine,
          endLabel: {
            show: series.length > 0,
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
