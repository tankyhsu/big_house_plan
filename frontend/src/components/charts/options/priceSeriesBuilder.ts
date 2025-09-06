import { sma as SMA } from "../indicators";
import type { Item, KlineConfig } from './types';

export function buildPriceSeries(params: {
  items: Item[];
  tsCode: string;
  dates: string[];
  kValues: number[][];
  maList: number[];
  klineConfig?: KlineConfig;
}) {
  const { items, tsCode, dates, kValues, maList, klineConfig } = params;
  
  const upColor = "#f04438";   // 红涨
  const downColor = "#12b76a"; // 绿跌
  const closes = items.map(it => it.close);
  const maColors = ["#3b82f6", "#f59e0b", "#8b5cf6", "#ef4444", "#10b981", "#14b8a6"];
  
  const series: any[] = [];
  
  // 主K线图
  series.push({ 
    type: 'candlestick', 
    name: tsCode, 
    data: kValues, 
    itemStyle: { 
      color: upColor, 
      color0: downColor, 
      borderColor: upColor, 
      borderColor0: downColor 
    }, 
    xAxisIndex: 0, 
    yAxisIndex: 0 
  });

  // 均线
  function SMAfor(period: number) { return SMA(closes as number[], period); }
  maList.forEach((p, idx) => {
    series.push({ 
      type: 'line', 
      name: `MA${p}`, 
      data: SMAfor(p), 
      smooth: true, 
      showSymbol: false, 
      xAxisIndex: 0, 
      yAxisIndex: 0, 
      lineStyle: { 
        width: 1.5, 
        color: maColors[idx % maColors.length] 
      }, 
      connectNulls: false, 
      z: 2 
    });
  });

  // 持仓成本线和止盈止损阈值线
  if (klineConfig && typeof klineConfig.avg_cost === 'number' && !isNaN(klineConfig.avg_cost)) {
    const avgCostData = Array(dates.length).fill(klineConfig.avg_cost);
    
    // 获取最新收盘价以判断当前盈亏状态
    const latestPrice = items.length > 0 ? items[items.length - 1].close : klineConfig.avg_cost;
    const isProfitable = latestPrice > klineConfig.avg_cost;

    // 成本线 - 始终显示持仓平均成本价格
    series.push({
      type: 'line',
      name: `成本线 (¥${klineConfig.avg_cost.toFixed(2)})`,
      data: avgCostData,
      showSymbol: false,
      xAxisIndex: 0,
      yAxisIndex: 0,
      lineStyle: {
        width: 1,
        color: '#666666',
        type: 'dashed',
        opacity: 0.8
      },
      connectNulls: false,
      z: 3,
      tooltip: {
        formatter: () => `成本线: ¥${klineConfig.avg_cost.toFixed(2)}`
      }
    });

    // 根据当前盈亏状态显示对应的止盈或止损线
    if (isProfitable && typeof klineConfig.stop_gain_price === 'number' && !isNaN(klineConfig.stop_gain_price)) {
      // 盈利时显示止盈线
      const stopGainData = Array(dates.length).fill(klineConfig.stop_gain_price);
      series.push({
        type: 'line',
        name: `止盈线 (+${(klineConfig.stop_gain_threshold * 100).toFixed(0)}% ¥${klineConfig.stop_gain_price.toFixed(2)})`,
        data: stopGainData,
        showSymbol: false,
        xAxisIndex: 0,
        yAxisIndex: 0,
        lineStyle: {
          width: 2,
          color: '#10b981',
          type: 'dashed',
          opacity: 0.9
        },
        connectNulls: false,
        z: 3,
        tooltip: {
          formatter: () => `止盈线: ¥${klineConfig.stop_gain_price.toFixed(2)} (+${(klineConfig.stop_gain_threshold * 100).toFixed(0)}%)`
        }
      });
    } else if (typeof klineConfig.stop_loss_price === 'number' && !isNaN(klineConfig.stop_loss_price)) {
      // 亏损时显示止损线
      const stopLossData = Array(dates.length).fill(klineConfig.stop_loss_price);
      series.push({
        type: 'line',
        name: `止损线 (-${(klineConfig.stop_loss_threshold * 100).toFixed(0)}% ¥${klineConfig.stop_loss_price.toFixed(2)})`,
        data: stopLossData,
        showSymbol: false,
        xAxisIndex: 0,
        yAxisIndex: 0,
        lineStyle: {
          width: 2,
          color: '#ef4444',
          type: 'dashed',
          opacity: 0.9
        },
        connectNulls: false,
        z: 3,
        tooltip: {
          formatter: () => `止损线: ¥${klineConfig.stop_loss_price.toFixed(2)} (-${(klineConfig.stop_loss_threshold * 100).toFixed(0)}%)`
        }
      });
    }
  }

  return {
    series,
    maColors,
    upColor,
    downColor
  };
}