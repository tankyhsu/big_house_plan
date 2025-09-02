import { computeBias, computeKdj, computeMacd, mapVolumes, sma as SMA } from "./indicators";

type Item = { date: string; open: number; high?: number | null; low?: number | null; close: number; vol?: number | null };
type Trade = { date: string; price: number };
type Signal = { date: string; price: number | null; type: string; message: string };

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
}) {
  const { items, tsCode, secType, maList, buys, sells, signals, viewportH, fullscreen } = params;

  const dates = items.map(it => it.date);
  const kValues = items.map(it => [it.open, it.close, (it.low ?? it.close), (it.high ?? it.close)]);
  const upColor = "#f04438";   // 红涨
  const downColor = "#12b76a"; // 绿跌
  const volumes = mapVolumes(items as any, upColor, downColor);

  // Process signals early to use in series
  console.log('📊 Building candle chart with signals:', signals);
  console.log('📊 K-line data dates range:', items.length > 0 ? `${items[0]?.date} to ${items[items.length-1]?.date}` : 'no data');
  
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
  const processedSignals = signals.map(signal => {
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
  
  const stopGainSignals = processedSignals.filter(s => s.type === 'STOP_GAIN');
  const stopLossSignals = processedSignals.filter(s => s.type === 'STOP_LOSS');
  const otherSignals = processedSignals.filter(s => s.type !== 'STOP_GAIN' && s.type !== 'STOP_LOSS');
  console.log('🔥 Stop gain signals:', stopGainSignals);
  console.log('⚠️ Stop loss signals:', stopLossSignals);

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
    if (n >= 1e8) return (n / 1e8).toFixed(2) + ' 亿';
    if (n >= 1e4) return (n / 1e4).toFixed(2) + ' 万';
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
  series.push({ type: 'scatter', name: 'BUY', data: buys.map(p => [p.date, p.price]), symbol: 'triangle', symbolSize: 8, itemStyle: { color: upColor }, xAxisIndex: 0, yAxisIndex: 0, z: 3 });
  series.push({ type: 'scatter', name: 'SELL', data: sells.map(p => [p.date, p.price]), symbol: 'triangle', symbolRotate: 180, symbolSize: 8, itemStyle: { color: downColor }, xAxisIndex: 0, yAxisIndex: 0, z: 3 });
  
  // Add signal markers
  if (stopGainSignals.length > 0) {
    series.push({ 
      type: 'scatter', 
      name: '止盈', 
      data: stopGainSignals.map(s => {
        // Find the high price for that date to position signal above the candle
        const item = items.find(it => it.date === s.date);
        const highPrice = item ? (item.high ?? item.close) : s.price;
        const signalPrice = highPrice * 1.02; // Position 2% above the high
        
        return { 
          value: [s.date, signalPrice],
          label: { 
            show: true, 
            position: 'top', 
            formatter: '🔥止盈', 
            textStyle: { 
              color: '#f04438', 
              fontSize: 12,
              fontWeight: 'bold',
              backgroundColor: '#fff',
              padding: [2, 4],
              borderRadius: 3,
              borderColor: '#f04438',
              borderWidth: 1
            }
          } 
        };
      }), 
      symbol: 'pin', 
      symbolSize: 16, 
      symbolRotate: 180,
      itemStyle: { 
        color: '#f04438', 
        borderColor: '#fff', 
        borderWidth: 2,
        shadowColor: '#f04438',
        shadowBlur: 8
      }, 
      xAxisIndex: 0, 
      yAxisIndex: 0, 
      z: 5 
    });
  }
  
  if (stopLossSignals.length > 0) {
    series.push({ 
      type: 'scatter', 
      name: '止损', 
      data: stopLossSignals.map(s => {
        // Find the low price for that date to position signal below the candle
        const item = items.find(it => it.date === s.date);
        const lowPrice = item ? (item.low ?? item.close) : s.price;
        const signalPrice = lowPrice * 0.98; // Position 2% below the low
        
        return { 
          value: [s.date, signalPrice],
          label: { 
            show: true, 
            position: 'bottom', 
            formatter: '⚠️止损', 
            textStyle: { 
              color: '#ff6b35', 
              fontSize: 12,
              fontWeight: 'bold',
              backgroundColor: '#fff',
              padding: [2, 4],
              borderRadius: 3,
              borderColor: '#ff6b35',
              borderWidth: 1
            }
          } 
        };
      }), 
      symbol: 'pin', 
      symbolSize: 16, 
      itemStyle: { 
        color: '#ff6b35', 
        borderColor: '#fff', 
        borderWidth: 2,
        shadowColor: '#ff6b35',
        shadowBlur: 8
      }, 
      xAxisIndex: 0, 
      yAxisIndex: 0, 
      z: 5 
    });
  }
  
  if (otherSignals.length > 0) {
    series.push({ 
      type: 'scatter', 
      name: '信号', 
      data: otherSignals.map(s => ({ value: [s.date, s.price], label: { show: true, position: 'top', formatter: '信号', textStyle: { color: '#fff', fontSize: 10 } } })), 
      symbol: 'circle', 
      symbolSize: 10, 
      itemStyle: { color: '#1890ff', borderColor: '#fff', borderWidth: 1 }, 
      xAxisIndex: 0, 
      yAxisIndex: 0, 
      z: 4 
    });
  }

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
  if (buys.length > 0) priceLegendData.push('BUY');
  if (sells.length > 0) priceLegendData.push('SELL');
  if (stopGainSignals.length > 0) priceLegendData.push('止盈');
  if (stopLossSignals.length > 0) priceLegendData.push('止损');
  if (otherSignals.length > 0) priceLegendData.push('信号');
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
      formatter: (params: any[]) => {
        const pK = params.find(p => p.seriesType === 'candlestick');
        const pV = params.find(p => p.seriesType === 'bar');
        const pLines = params.filter(p => p.seriesType === 'line');
        const date = (pK?.axisValue || pV?.axisValue || '').toString();
        const arr = (pK?.data || []) as number[];
        const o = arr[0], c = arr[1], l = arr[2], h = arr[3];
        const vol = (pV?.seriesName === 'Volume') ? ((pV?.data?.value ?? pV?.data ?? null) as number | null) : null;
        const lines = [date];
        if (arr.length) lines.push(`开: ${o}  高: ${h}  低: ${l}  收: ${c}`);
        if (vol != null) lines.push(`量: ${fmtVol(Number(vol))}`);
        if (pLines && pLines.length) {
          pLines.forEach(pl => {
            if (typeof pl.data === 'number') lines.push(`${pl.seriesName}: ${pl.data.toFixed(2)}`);
          });
        }
        return lines.join('<br/>');
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
