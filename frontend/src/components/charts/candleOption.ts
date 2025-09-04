import { computeBias, computeKdj, computeMacd, mapVolumes, sma as SMA } from "./indicators";
import { formatQuantity, formatPrice } from "../../utils/format";

type Item = { date: string; open: number; high?: number | null; low?: number | null; close: number; vol?: number | null };
type Trade = { date: string; price: number };
type Signal = { date: string; price: number | null; type: string; message: string };
type KlineConfig = { avg_cost: number; stop_gain_threshold: number; stop_loss_threshold: number; stop_gain_price: number; stop_loss_price: number } | null;

export function buildCandleOption(params: {
  items: Item[];
  tsCode: string;
  secType?: string;
  maList: number[];
  buys: Trade[];
  sells: Trade[];
  signals: Signal[];
  viewportH: number;
  fullscreen: boolean;
  klineConfig?: KlineConfig;
}) {
  const { items, tsCode, secType, maList, buys, sells, signals, viewportH, fullscreen, klineConfig } = params;
  

  const dates = items.map(it => it.date);
  // ECharts candlestick format: [open, close, low, high]
  // Ensure low and high values are correct by taking min/max
  const kValues = items.map(it => {
    const open = it.open;
    const close = it.close;
    const rawLow = it.low ?? it.close;
    const rawHigh = it.high ?? it.close;
    
    // Ensure low is actually the lower value and high is the higher value
    const actualLow = Math.min(rawLow, rawHigh);
    const actualHigh = Math.max(rawLow, rawHigh);
    
    
    return [open, close, actualLow, actualHigh];
  });
  const upColor = "#f04438";   // 红涨
  const downColor = "#12b76a"; // 绿跌
  const volumes = mapVolumes(items as any, upColor, downColor);

  // 过滤掉止盈止损信号，因为我们要用阈值线替代时间点信号
  const filteredSignals = signals.filter(signal => 
    signal.type !== 'STOP_GAIN' && signal.type !== 'STOP_LOSS'
  );
  
  // Process signals early to use in series
  // console.log('📊 Building candle chart with signals:', filteredSignals);
  // console.log('📊 K-line data dates range:', items.length > 0 ? `${items[0]?.date} to ${items[items.length-1]?.date}` : 'no data');
  
  // Helper function to find price for a signal date
  const findPriceForDate = (date: string): number | null => {
    // First try exact match
    const exactItem = items.find(it => it.date === date);
    if (exactItem) return exactItem.close;
    
    // If no exact match, find the closest earlier date
    const signalDate = new Date(date);
    const validItems = items.filter(it => new Date(it.date) <= signalDate);
    if (validItems.length === 0) return null;
    
    // Sort by date descending and take the most recent
    validItems.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
    return validItems[0].close;
  };
  
  // Process signals and resolve prices - only include signals that have valid prices
  const processedSignals = filteredSignals.map(signal => {
    const price = signal.price || findPriceForDate(signal.date);
    if (price === null || price === undefined) return null;
    
    // If we used a fallback date, use the actual date from K-line data
    let displayDate = signal.date;
    if (!items.find(it => it.date === signal.date)) {
      // Find the closest earlier date that we actually have data for
      const signalDate = new Date(signal.date);
      const validItems = items.filter(it => new Date(it.date) <= signalDate);
      if (validItems.length > 0) {
        validItems.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
        displayDate = validItems[0].date;
      }
    }
    
    return {
      ...signal,
      date: displayDate, // Use the date we actually have K-line data for
      price
    };
  }).filter(signal => signal !== null) as typeof signals;
  
  // Group signals by type for different visual representations
  const signalGroups = processedSignals.reduce((groups, signal) => {
    if (!groups[signal.type]) {
      groups[signal.type] = [];
    }
    groups[signal.type].push(signal);
    return groups;
  }, {} as Record<string, typeof processedSignals>);
  
  // Define signal type configurations for visual representation
  const signalConfigs: Record<string, {
    symbol: string;
    color: string;
    emoji: string;
    name: string;
    position: 'top' | 'bottom';
    offsetMultiplier: number;
  }> = {
    'STOP_GAIN': { symbol: 'pin', color: '#f04438', emoji: '🔥', name: '止盈', position: 'top', offsetMultiplier: 1.02 },
    'STOP_LOSS': { symbol: 'pin', color: '#ff6b35', emoji: '⚠️', name: '止损', position: 'bottom', offsetMultiplier: 0.98 },
    'UNDERWEIGHT': { symbol: 'circle', color: '#3b82f6', emoji: '📊', name: '低配', position: 'top', offsetMultiplier: 1.01 },
    'BUY_SIGNAL': { symbol: 'triangle', color: '#10b981', emoji: '📈', name: '买入', position: 'top', offsetMultiplier: 1.015 },
    'SELL_SIGNAL': { symbol: 'triangle', color: '#ef4444', emoji: '📉', name: '卖出', position: 'top', offsetMultiplier: 1.015 },
    'REBALANCE': { symbol: 'diamond', color: '#8b5cf6', emoji: '⚖️', name: '再平衡', position: 'top', offsetMultiplier: 1.025 },
    'RISK_ALERT': { symbol: 'circle', color: '#ec4899', emoji: '⚡', name: '风险预警', position: 'top', offsetMultiplier: 1.01 },
    'MOMENTUM': { symbol: 'circle', color: '#06b6d4', emoji: '🚀', name: '动量', position: 'top', offsetMultiplier: 1.008 },
    'MEAN_REVERT': { symbol: 'circle', color: '#1e40af', emoji: '🔄', name: '均值回归', position: 'top', offsetMultiplier: 1.008 },
    'BULLISH': { symbol: 'circle', color: '#52c41a', emoji: '📈', name: '利好', position: 'top', offsetMultiplier: 1.01 },
    'BEARISH': { symbol: 'circle', color: '#fa8c16', emoji: '📉', name: '利空', position: 'top', offsetMultiplier: 1.01 }
  };

  // 布局参数
  const padTop = 12;
  const padGap = 28;
  const sliderHeight = 24;
  const sliderBottom = 10;
  const padBottom = sliderHeight + sliderBottom + 6;
  const leftPad = 120;
  const legendH = 18;
  const g1Top = padTop;

  const t = (secType || '').toUpperCase();
  const wantMacd = t !== 'CASH';
  const wantKdj = t !== 'CASH';
  const wantBias = ['ETF', 'FUND'].includes(t);
  const wantVol = t !== 'FUND';

  const panels: { key: 'price'|'vol'|'macd'|'kdj'|'bias'; height: number; top: number }[] = [];
  const restPanels: ('vol'|'macd'|'kdj'|'bias')[] = [];
  if (wantVol) restPanels.push('vol');
  if (wantMacd) restPanels.push('macd');
  if (wantKdj) restPanels.push('kdj');
  if (wantBias) restPanels.push('bias');

  let layoutH = 300;
  if (fullscreen) {
    const baseH = Math.max(520, viewportH - 108);
    const totalAvail = baseH - padTop - padBottom;
    const priceWeight = 0.3;
    const priceHeight = Math.floor(totalAvail * priceWeight);
    panels.push({ key: 'price', height: priceHeight, top: g1Top + legendH });
    let cursorTop = g1Top + legendH + priceHeight + padGap;
    const restCount = restPanels.length;
    const per = restCount > 0 ? Math.floor((totalAvail - priceHeight - padGap * restCount) / restCount) : 0;
    restPanels.forEach((key, idx) => {
      let h = per;
      if (idx === restCount - 1) {
        const used = priceHeight + per * (restCount - 1) + padGap * restCount;
        const remain = totalAvail - used;
        h = Math.max(per, remain);
      }
      panels.push({ key, height: h, top: cursorTop + legendH });
      cursorTop += legendH + h + padGap;
    });
    layoutH = baseH;
  } else {
    const priceH = 280; const volH = 160; const macdH = 180; const kdjH = 180; const biasH = 180;
    panels.push({ key: 'price', height: priceH, top: g1Top + legendH });
    let cursorTop = g1Top + legendH + priceH + padGap;
    for (const key of restPanels) {
      const h = key === 'vol' ? volH : (key === 'macd' ? macdH : (key === 'kdj' ? kdjH : biasH));
      panels.push({ key, height: h, top: cursorTop + legendH });
      cursorTop += legendH + h + padGap;
    }
    layoutH = cursorTop - padGap + padBottom;
  }

  function fmtVol(n: number) {
    if (n >= 1e8) return formatQuantity(n / 1e8) + ' 亿';
    if (n >= 1e4) return formatQuantity(n / 1e4) + ' 万';
    return String(Math.round(n));
  }

  const closes = items.map(it => it.close);
  const maColors = ["#3b82f6", "#f59e0b", "#8b5cf6", "#ef4444", "#10b981", "#14b8a6"]; // 轮询颜色
  const { dif, dea, macd } = computeMacd(closes as number[]);
  const highs = items.map(it => it.high ?? it.close);
  const lows = items.map(it => it.low ?? it.close);
  const { kArr, dArr, jArr } = computeKdj(highs as number[], lows as number[], closes as number[], 9);
  const biasPeriods = [20, 30, 60] as const;
  const biasMap = computeBias(closes as number[], biasPeriods as unknown as number[]);

  const grids: any[] = [];
  const xAxes: any[] = [];
  const yAxes: any[] = [];
  const series: any[] = [];

  const pricePanel = panels.find(p => p.key === 'price')!;
  grids.push({ left: leftPad, right: 24, top: pricePanel.top, height: pricePanel.height, containLabel: false, show: true, borderColor: '#e5e7eb', borderWidth: 1 });
  xAxes.push({ gridIndex: 0, type: 'category', data: dates, boundaryGap: false, axisLine: { onZero: false } });
  yAxes.push({ gridIndex: 0, scale: true, splitNumber: 4, name: '价格', nameLocation: 'middle', nameGap: 70, nameTextStyle: { color: '#667085' }, axisLabel: { align: 'right', margin: 6 } });
  series.push({ type: 'candlestick', name: tsCode, data: kValues, itemStyle: { color: upColor, color0: downColor, borderColor: upColor, borderColor0: downColor }, xAxisIndex: 0, yAxisIndex: 0 });
  function SMAfor(period: number) { return SMA(closes as number[], period); }
  maList.forEach((p, idx) => {
    series.push({ type: 'line', name: `MA${p}`, data: SMAfor(p), smooth: true, showSymbol: false, xAxisIndex: 0, yAxisIndex: 0, lineStyle: { width: 1.5, color: maColors[idx % maColors.length] }, connectNulls: false, z: 2 });
  });

  // 添加持仓成本线和止盈止损阈值线
  if (klineConfig) {
    const avgCostData = Array(dates.length).fill(klineConfig.avg_cost);
    const stopGainData = Array(dates.length).fill(klineConfig.stop_gain_price);
    const stopLossData = Array(dates.length).fill(klineConfig.stop_loss_price);

    // 成本线 - 显示持仓平均成本价格
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

    // 止盈阈值线 - 基于成本价计算的止盈目标价格
    series.push({
      type: 'line',
      name: `止盈线 (+${(klineConfig.stop_gain_threshold * 100).toFixed(0)}% ¥${klineConfig.stop_gain_price.toFixed(2)})`,
      data: stopGainData,
      showSymbol: false,
      xAxisIndex: 0,
      yAxisIndex: 0,
      lineStyle: {
        width: 1,
        color: '#10b981',
        type: 'dashed',
        opacity: 0.8
      },
      connectNulls: false,
      z: 3,
      tooltip: {
        formatter: () => `止盈线: ¥${klineConfig.stop_gain_price.toFixed(2)} (+${(klineConfig.stop_gain_threshold * 100).toFixed(0)}%)`
      }
    });

    // 止损阈值线 - 基于成本价计算的止损价格
    series.push({
      type: 'line',
      name: `止损线 (-${(klineConfig.stop_loss_threshold * 100).toFixed(0)}% ¥${klineConfig.stop_loss_price.toFixed(2)})`,
      data: stopLossData,
      showSymbol: false,
      xAxisIndex: 0,
      yAxisIndex: 0,
      lineStyle: {
        width: 1,
        color: '#ef4444',
        type: 'dashed',
        opacity: 0.8
      },
      connectNulls: false,
      z: 3,
      tooltip: {
        formatter: () => `止损线: ¥${klineConfig.stop_loss_price.toFixed(2)} (-${(klineConfig.stop_loss_threshold * 100).toFixed(0)}%)`
      }
    });
  }
  // Enhanced buy/sell markers with text labels
  series.push({ 
    type: 'scatter', 
    name: 'BUY', 
    data: buys.map(p => ({
      value: [p.date, p.price],
      label: {
        show: true,
        position: 'top',
        formatter: '买入',
        textStyle: {
          color: upColor,
          fontSize: 11,
          fontWeight: 'bold',
          backgroundColor: '#fff',
          padding: [1, 3],
          borderRadius: 3,
          borderColor: upColor,
          borderWidth: 1,
          shadowColor: upColor,
          shadowBlur: 3,
          shadowOffsetY: 1
        }
      }
    })), 
    symbol: 'triangle', 
    symbolSize: 10, 
    itemStyle: { 
      color: upColor,
      borderColor: '#fff',
      borderWidth: 2,
      shadowColor: upColor,
      shadowBlur: 6,
      shadowOffsetY: 2
    }, 
    xAxisIndex: 0, 
    yAxisIndex: 0, 
    z: 3 
  });
  series.push({ 
    type: 'scatter', 
    name: 'SELL', 
    data: sells.map(p => ({
      value: [p.date, p.price],
      label: {
        show: true,
        position: 'bottom',
        formatter: '卖出',
        textStyle: {
          color: downColor,
          fontSize: 11,
          fontWeight: 'bold',
          backgroundColor: '#fff',
          padding: [1, 3],
          borderRadius: 3,
          borderColor: downColor,
          borderWidth: 1,
          shadowColor: downColor,
          shadowBlur: 3,
          shadowOffsetY: 1
        }
      }
    })), 
    symbol: 'triangle', 
    symbolRotate: 180, 
    symbolSize: 10, 
    itemStyle: { 
      color: downColor,
      borderColor: '#fff',
      borderWidth: 2,
      shadowColor: downColor,
      shadowBlur: 6,
      shadowOffsetY: 2
    }, 
    xAxisIndex: 0, 
    yAxisIndex: 0, 
    z: 3 
  });
  
  // Add all signal types with unified rendering logic
  Object.entries(signalGroups).forEach(([signalType, signalsOfType]) => {
    if (signalsOfType.length === 0) return;
    
    const config = signalConfigs[signalType] || {
      symbol: 'circle',
      color: '#1890ff',
      emoji: '📍',
      name: signalType,
      position: 'top' as const,
      offsetMultiplier: 1.01
    };
    
    series.push({
      type: 'scatter',
      name: config.name,
      data: signalsOfType.map(signal => {
        const item = items.find(it => it.date === signal.date);
        let signalPrice: number;
        
        if (config.position === 'bottom') {
          const lowPrice = item ? (item.low ?? item.close) : (signal.price ?? 0);
          signalPrice = (lowPrice || 0) * config.offsetMultiplier;
        } else {
          const highPrice = item ? (item.high ?? item.close) : (signal.price ?? 0);
          signalPrice = (highPrice || 0) * config.offsetMultiplier;
        }
        
        return {
          value: [signal.date, signalPrice],
          signalData: signal, // Store the full signal data for click handling
          tooltip: {
            formatter: `${config.emoji}${config.name}: ${signal.message || signal.type}`
          },
          label: {
            show: true,
            position: config.position,
            formatter: `${config.emoji}${config.name}`,
            textStyle: {
              color: config.color,
              fontSize: 11,
              fontWeight: 'bold',
              backgroundColor: '#fff',
              padding: [1, 3],
              borderRadius: 3,
              borderColor: config.color,
              borderWidth: 1,
              shadowColor: config.color,
              shadowBlur: 3,
              shadowOffsetY: 1
            }
          }
        };
      }),
      symbol: config.symbol,
      symbolSize: signalType === 'STOP_GAIN' || signalType === 'STOP_LOSS' ? 16 : 12,
      symbolRotate: signalType === 'STOP_GAIN' ? 180 : (signalType === 'SELL_SIGNAL' ? 180 : 0),
      itemStyle: {
        color: config.color,
        borderColor: '#fff',
        borderWidth: 2,
        shadowColor: config.color,
        shadowBlur: 6,
        shadowOffsetY: 2
      },
      xAxisIndex: 0,
      yAxisIndex: 0,
      z: 5
    });
  });

  let panelIdx = 1;
  function addPanelGrid(panelKey: 'vol'|'macd'|'kdj'|'bias') {
    const p = panels.find(pp => pp.key === panelKey);
    if (!p) return null;
    grids.push({ left: leftPad, right: 24, top: p.top, height: p.height, containLabel: false, show: true, borderColor: '#e5e7eb', borderWidth: 1 });
    xAxes.push({ gridIndex: panelIdx, type: 'category', data: dates, boundaryGap: false, axisLabel: { show: false }, axisTick: { show: false } });
    const nameMap: Record<string,string> = { vol: '成交量', macd: 'MACD', kdj: 'KDJ', bias: 'BIAS' };
    yAxes.push({ gridIndex: panelIdx, scale: true, splitNumber: 2, name: nameMap[panelKey], nameLocation: 'middle', nameGap: 70, nameTextStyle: { color: '#667085' }, axisLabel: { align: 'right', margin: 6 } });
    return panelIdx++;
  }

  const volIdx = addPanelGrid('vol');
  if (volIdx != null && wantVol) series.push({ type: 'bar', name: 'Volume', data: volumes, xAxisIndex: volIdx, yAxisIndex: volIdx });
  if (wantMacd) {
    const macdIdx = addPanelGrid('macd');
    if (macdIdx != null) {
      const macdBarData = macd.map(v => ({ value: v ?? 0, itemStyle: { color: (v ?? 0) >= 0 ? upColor : downColor } }));
      series.push({ type: 'bar', name: 'MACD', data: macdBarData, xAxisIndex: macdIdx, yAxisIndex: macdIdx });
      series.push({ type: 'line', name: 'DIF', data: dif, xAxisIndex: macdIdx, yAxisIndex: macdIdx, showSymbol: false, lineStyle: { width: 1.2, color: '#ef4444' } });
      series.push({ type: 'line', name: 'DEA', data: dea, xAxisIndex: macdIdx, yAxisIndex: macdIdx, showSymbol: false, lineStyle: { width: 1.2, color: '#3b82f6' } });
    }
  }
  if (wantKdj) {
    const kdjIdx = addPanelGrid('kdj');
    if (kdjIdx != null) {
      series.push({ type: 'line', name: 'K', data: kArr, xAxisIndex: kdjIdx, yAxisIndex: kdjIdx, showSymbol: false, lineStyle: { width: 1.2, color: '#22c55e' } });
      series.push({ type: 'line', name: 'D', data: dArr, xAxisIndex: kdjIdx, yAxisIndex: kdjIdx, showSymbol: false, lineStyle: { width: 1.2, color: '#f59e0b' } });
      series.push({ type: 'line', name: 'J', data: jArr, xAxisIndex: kdjIdx, yAxisIndex: kdjIdx, showSymbol: false, lineStyle: { width: 1.2, color: '#ef4444' } });
    }
  }
  if (wantBias) {
    const biasIdx = addPanelGrid('bias');
    if (biasIdx != null) {
      series.push({ type: 'line', name: 'BIAS20', data: biasMap[20], xAxisIndex: biasIdx, yAxisIndex: biasIdx, showSymbol: false, lineStyle: { width: 1.2, color: '#8b5cf6' } });
      series.push({ type: 'line', name: 'BIAS30', data: biasMap[30], xAxisIndex: biasIdx, yAxisIndex: biasIdx, showSymbol: false, lineStyle: { width: 1.2, color: '#06b6d4' } });
      series.push({ type: 'line', name: 'BIAS60', data: biasMap[60], xAxisIndex: biasIdx, yAxisIndex: biasIdx, showSymbol: false, lineStyle: { width: 1.2, color: '#9333ea' } });
    }
  }

  const xIndexList = xAxes.map((_, idx) => idx);
  const legends: any[] = [];
  const priceLegendData: string[] = [tsCode, ...maList.map(p => `MA${p}`)];
  if (klineConfig) {
    priceLegendData.push(`成本线 (¥${klineConfig.avg_cost.toFixed(2)})`);
    priceLegendData.push(`止盈线 (+${(klineConfig.stop_gain_threshold * 100).toFixed(0)}% ¥${klineConfig.stop_gain_price.toFixed(2)})`);
    priceLegendData.push(`止损线 (-${(klineConfig.stop_loss_threshold * 100).toFixed(0)}% ¥${klineConfig.stop_loss_price.toFixed(2)})`);
  }
  if (buys.length > 0) priceLegendData.push('BUY');
  if (sells.length > 0) priceLegendData.push('SELL');
  
  // Add all signal types to legend
  Object.entries(signalGroups).forEach(([signalType, signalsOfType]) => {
    if (signalsOfType.length > 0) {
      const config = signalConfigs[signalType];
      priceLegendData.push(config ? config.name : signalType);
    }
  });
  legends.push({ type: 'plain', top: (pricePanel.top || 0) - legendH + 2, left: leftPad, right: 24, data: priceLegendData, icon: 'circle', itemWidth: 8, itemHeight: 8, textStyle: { color: '#667085' } });
  for (const key of restPanels) {
    const p = panels.find(pp => pp.key === key);
    if (!p) continue;
    let data: string[] = [];
    if (key === 'macd') data = ['MACD','DIF','DEA'];
    if (key === 'kdj') data = ['K','D','J'];
    if (key === 'bias') data = ['BIAS20','BIAS30','BIAS60'];
    if (data.length) legends.push({ type: 'plain', top: (p.top || 0) - legendH + 2, left: leftPad, right: 24, data, icon: 'circle', itemWidth: 8, itemHeight: 8, textStyle: { color: '#667085' } });
  }

  const option = {
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
        
        const pK = params.find(p => p.seriesType === 'candlestick');
        const pV = params.find(p => p.seriesType === 'bar');
        const pLines = params.filter(p => p.seriesType === 'line');
        const pSignals = params.filter(p => p.seriesType === 'scatter' && p.data?.signalData);
        
        const date = (pK?.axisValue || pV?.axisValue || '').toString();
        const arr = (pK?.data || []) as number[];
        
        // Universal fix: Always use original data to ensure accuracy for all symbols
        const dateIndex = dates.indexOf(date);
        let o: number, c: number, l: number, h: number;
        
        if (dateIndex >= 0 && dateIndex < items.length) {
          // Always use original data from items array to avoid any tooltip data corruption
          const item = items[dateIndex];
          o = item.open;
          c = item.close;
          l = Math.min(item.low ?? item.close, item.high ?? item.close);
          h = Math.max(item.low ?? item.close, item.high ?? item.close);
        } else {
          // Fallback to ECharts data if date not found
          o = arr[0] || 0; c = arr[1] || 0; l = arr[2] || 0; h = arr[3] || 0;
        }
        
        const vol = (pV?.seriesName === 'Volume') ? ((pV?.data?.value ?? pV?.data ?? null) as number | null) : null;
        
        let html = `<div style="padding: 8px;">`;
        
        // Date header
        html += `<div style="font-weight: bold; font-size: 13px; margin-bottom: 8px; color: #fff; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 6px;">${date}</div>`;
        
        // Price data (OHLC)
        if (arr.length) {
          const isRising = c >= o;
          const priceColor = isRising ? upColor : downColor;
          html += `<div style="margin-bottom: 8px;">`;
          html += `<div style="display: flex; gap: 12px; font-size: 12px;">`;
          html += `<span style="color: #ccc;">开:</span><span style="color: ${priceColor}; font-weight: bold;">${formatPrice(o)}</span>`;
          html += `<span style="color: #ccc;">高:</span><span style="color: ${priceColor}; font-weight: bold;">${formatPrice(h)}</span>`;
          html += `<span style="color: #ccc;">低:</span><span style="color: ${priceColor}; font-weight: bold;">${formatPrice(l)}</span>`;
          html += `<span style="color: #ccc;">收:</span><span style="color: ${priceColor}; font-weight: bold;">${formatPrice(c)}</span>`;
          html += `</div>`;
          html += `</div>`;
        }
        
        // Volume
        if (vol != null) {
          html += `<div style="margin-bottom: 8px; font-size: 12px;">`;
          html += `<span style="color: #ccc;">成交量:</span> <span style="color: #ffa726; font-weight: bold;">${fmtVol(Number(vol))}</span>`;
          html += `</div>`;
        }
        
        // 按业务意义分组显示指标
        if (pLines && pLines.length > 0) {
          // 1. 趋势指标 (MA均线) - 一行显示
          const maLines = pLines.filter(pl => pl.seriesName.startsWith('MA'));
          if (maLines.length > 0) {
            html += `<div style="margin-bottom: 8px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 6px;">`;
            html += `<div style="color: #ffa726; font-size: 11px; margin-bottom: 4px;">趋势指标</div>`;
            html += `<div style="display: flex; flex-wrap: wrap; gap: 8px; font-size: 11px;">`;
            maLines.forEach((pl, idx) => {
              const color = maColors[idx % maColors.length];
              if (typeof pl.data === 'number') {
                html += `<span><span style="color: ${color};">●</span> ${pl.seriesName}: <span style="color: ${color}; font-weight: bold;">${formatQuantity(pl.data)}</span></span>`;
              }
            });
            html += `</div></div>`;
          }
          
          // 2. 持仓参考线 (成本线、止盈线、止损线) - 分行显示
          const positionLines = pLines.filter(pl => 
            pl.seriesName.includes('成本线') || 
            pl.seriesName.includes('止盈线') || 
            pl.seriesName.includes('止损线')
          );
          if (positionLines.length > 0) {
            html += `<div style="margin-bottom: 8px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 6px;">`;
            html += `<div style="color: #10b981; font-size: 11px; margin-bottom: 4px;">持仓参考</div>`;
            positionLines.forEach(pl => {
              if (typeof pl.data === 'number') {
                let lineColor = '#666666';
                let lineIcon = '━';
                if (pl.seriesName.includes('止盈')) {
                  lineColor = '#10b981';
                  lineIcon = '━';
                } else if (pl.seriesName.includes('止损')) {
                  lineColor = '#ef4444';  
                  lineIcon = '━';
                }
                html += `<div style="font-size: 11px; margin-bottom: 2px;"><span style="color: ${lineColor};">${lineIcon}</span> <span style="color: #ccc;">${pl.seriesName}:</span> <span style="color: ${lineColor}; font-weight: bold;">${formatPrice(pl.data)}</span></div>`;
              }
            });
            html += `</div>`;
          }
          
          // 3. 技术指标 (MACD, KDJ, BIAS等) - 按类型分行
          const techLines = pLines.filter(pl => 
            !pl.seriesName.startsWith('MA') && 
            !pl.seriesName.includes('成本线') && 
            !pl.seriesName.includes('止盈线') && 
            !pl.seriesName.includes('止损线')
          );
          if (techLines.length > 0) {
            html += `<div style="margin-bottom: 8px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 6px;">`;
            html += `<div style="color: #42a5f5; font-size: 11px; margin-bottom: 4px;">技术指标</div>`;
            
            // MACD 指标一行
            const macdLines = techLines.filter(pl => pl.seriesName.includes('DIF') || pl.seriesName.includes('DEA') || pl.seriesName.includes('MACD'));
            if (macdLines.length > 0) {
              html += `<div style="font-size: 11px; margin-bottom: 2px;">`;
              macdLines.forEach((pl, idx) => {
                if (typeof pl.data === 'number') {
                  let indicatorColor = '#42a5f5';
                  if (pl.seriesName.includes('DIF')) indicatorColor = '#ef4444';
                  else if (pl.seriesName.includes('DEA')) indicatorColor = '#3b82f6';
                  else if (pl.seriesName.includes('MACD')) indicatorColor = '#10b981';
                  html += `<span><span style="color: ${indicatorColor};">●</span> ${pl.seriesName}: <span style="color: ${indicatorColor}; font-weight: bold;">${formatQuantity(pl.data)}</span></span>`;
                  if (idx < macdLines.length - 1) html += `<span style="color: #666; margin: 0 4px;">|</span>`;
                }
              });
              html += `</div>`;
            }
            
            // KDJ 指标一行  
            const kdjLines = techLines.filter(pl => pl.seriesName.includes('K') || pl.seriesName.includes('D') || pl.seriesName.includes('J'));
            if (kdjLines.length > 0) {
              html += `<div style="font-size: 11px; margin-bottom: 2px;">`;
              kdjLines.forEach((pl, idx) => {
                if (typeof pl.data === 'number') {
                  let indicatorColor = '#42a5f5';
                  if (pl.seriesName.includes('K')) indicatorColor = '#22c55e';
                  else if (pl.seriesName.includes('D')) indicatorColor = '#f59e0b';
                  else if (pl.seriesName.includes('J')) indicatorColor = '#ef4444';
                  html += `<span><span style="color: ${indicatorColor};">●</span> ${pl.seriesName}: <span style="color: ${indicatorColor}; font-weight: bold;">${formatQuantity(pl.data)}</span></span>`;
                  if (idx < kdjLines.length - 1) html += `<span style="color: #666; margin: 0 4px;">|</span>`;
                }
              });
              html += `</div>`;
            }
            
            // BIAS 指标一行
            const biasLines = techLines.filter(pl => pl.seriesName.includes('BIAS'));
            if (biasLines.length > 0) {
              html += `<div style="font-size: 11px; margin-bottom: 2px;">`;
              biasLines.forEach((pl, idx) => {
                if (typeof pl.data === 'number') {
                  html += `<span><span style="color: #8b5cf6;">●</span> ${pl.seriesName}: <span style="color: #8b5cf6; font-weight: bold;">${formatQuantity(pl.data)}%</span></span>`;
                  if (idx < biasLines.length - 1) html += `<span style="color: #666; margin: 0 4px;">|</span>`;
                }
              });
              html += `</div>`;
            }
            
            html += `</div>`;
          }
        }
        
        // Add trading events information
        const pBuys = params.filter(p => p.seriesName === 'BUY');
        const pSells = params.filter(p => p.seriesName === 'SELL');
        const tradingEvents = [...pBuys, ...pSells];
        
        if (tradingEvents.length > 0) {
          html += `<div style="border-top: 1px solid rgba(255,255,255,0.2); margin-top: 8px; padding-top: 8px;">`;
          html += `<div style="font-weight: bold; font-size: 12px; margin-bottom: 6px; color: #fff;">💼 交易记录</div>`;
          
          tradingEvents.forEach(trade => {
            const isBuy = trade.seriesName === 'BUY';
            const action = isBuy ? '买入' : '卖出';
            const actionColor = isBuy ? upColor : downColor;
            const actionIcon = isBuy ? '📈' : '📉';
            const price = trade.value[1];
            
            html += `<div style="margin-bottom: 6px; padding: 4px 0;">`;
            html += `<div style="display: flex; align-items: center; margin-bottom: 2px;">`;
            html += `<span style="font-size: 14px; margin-right: 4px;">${actionIcon}</span>`;
            html += `<span style="color: ${actionColor}; font-weight: bold; font-size: 12px;">${action}</span>`;
            html += `</div>`;
            html += `<div style="color: #ccc; font-size: 11px; line-height: 1.4; margin-left: 20px;">成交价: <span style="color: ${actionColor}; font-weight: bold;">¥${price}</span></div>`;
            html += `</div>`;
          });
          
          html += `</div>`;
        }
        
        // Signals section
        if (pSignals && pSignals.length > 0) {
          html += `<div style="border-top: 1px solid rgba(255,255,255,0.2); margin-top: 8px; padding-top: 8px;">`;
          html += `<div style="font-weight: bold; font-size: 12px; margin-bottom: 6px; color: #fff;">📡 交易信号</div>`;
          
          pSignals.forEach(ps => {
            const signal = ps.data.signalData;
            const config = signalConfigs[signal.type] || { emoji: '📍', name: signal.type, color: '#1890ff' };
            
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
    legend: legends,
    axisPointer: { link: [{ xAxisIndex: xIndexList }] },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: [
      { type: "inside", xAxisIndex: xIndexList },
      { type: "slider", xAxisIndex: xIndexList, bottom: sliderBottom, height: sliderHeight, showDetail: false, brushSelect: false },
    ],
    series,
  } as any;

  return { option, chartHeight: layoutH };
}
