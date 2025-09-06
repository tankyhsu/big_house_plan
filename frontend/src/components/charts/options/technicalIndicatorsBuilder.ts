import { computeBias, computeKdj, computeMacd, mapVolumes } from "../indicators";
import type { Item, Panel } from './types';

export function buildTechnicalIndicators(params: {
  items: Item[];
  dates: string[];
  panels: Panel[];
  leftPad: number;
  legendH: number;
  upColor: string;
  downColor: string;
  wantVol: boolean;
  wantMacd: boolean;
  wantKdj: boolean;
  wantBias: boolean;
  restPanels: ('vol'|'macd'|'kdj'|'bias')[];
}) {
  const { 
    items, 
    dates, 
    panels, 
    leftPad, 
    legendH, 
    upColor, 
    downColor, 
    wantVol, 
    wantMacd, 
    wantKdj, 
    wantBias, 
    restPanels 
  } = params;

  const closes = items.map(it => it.close);
  const highs = items.map(it => it.high ?? it.close);
  const lows = items.map(it => it.low ?? it.close);
  const volumes = mapVolumes(items as any, upColor, downColor);
  
  // Technical indicators computation
  const { dif, dea, macd } = computeMacd(closes as number[]);
  const { kArr, dArr, jArr } = computeKdj(highs as number[], lows as number[], closes as number[], 9);
  const biasPeriods = [20, 30, 60] as const;
  const biasMap = computeBias(closes as number[], biasPeriods as unknown as number[]);

  const grids: any[] = [];
  const xAxes: any[] = [];
  const yAxes: any[] = [];
  const series: any[] = [];

  let panelIdx = 1;
  
  function addPanelGrid(panelKey: 'vol'|'macd'|'kdj'|'bias') {
    const p = panels.find(pp => pp.key === panelKey);
    if (!p) return null;
    
    grids.push({ 
      left: leftPad, 
      right: 24, 
      top: p.top, 
      height: p.height, 
      containLabel: false, 
      show: true, 
      borderColor: '#e5e7eb', 
      borderWidth: 1 
    });
    
    xAxes.push({ 
      gridIndex: panelIdx, 
      type: 'category', 
      data: dates, 
      boundaryGap: false, 
      axisLabel: { show: false }, 
      axisTick: { show: false } 
    });
    
    const nameMap: Record<string,string> = { 
      vol: '成交量', 
      macd: 'MACD', 
      kdj: 'KDJ', 
      bias: 'BIAS' 
    };
    
    yAxes.push({ 
      gridIndex: panelIdx, 
      scale: true, 
      splitNumber: 2, 
      name: nameMap[panelKey], 
      nameLocation: 'middle', 
      nameGap: 70, 
      nameTextStyle: { color: '#667085' }, 
      axisLabel: { align: 'right', margin: 6 } 
    });
    
    return panelIdx++;
  }

  // Volume panel
  const volIdx = addPanelGrid('vol');
  if (volIdx != null && wantVol) {
    series.push({ 
      type: 'bar', 
      name: 'Volume', 
      data: volumes, 
      xAxisIndex: volIdx, 
      yAxisIndex: volIdx 
    });
  }

  // MACD panel
  if (wantMacd) {
    const macdIdx = addPanelGrid('macd');
    if (macdIdx != null) {
      const macdBarData = macd.map(v => ({ 
        value: v ?? 0, 
        itemStyle: { color: (v ?? 0) >= 0 ? upColor : downColor } 
      }));
      
      series.push({ 
        type: 'bar', 
        name: 'MACD', 
        data: macdBarData, 
        xAxisIndex: macdIdx, 
        yAxisIndex: macdIdx 
      });
      
      series.push({ 
        type: 'line', 
        name: 'DIF', 
        data: dif, 
        xAxisIndex: macdIdx, 
        yAxisIndex: macdIdx, 
        showSymbol: false, 
        lineStyle: { width: 1.2, color: '#ef4444' } 
      });
      
      series.push({ 
        type: 'line', 
        name: 'DEA', 
        data: dea, 
        xAxisIndex: macdIdx, 
        yAxisIndex: macdIdx, 
        showSymbol: false, 
        lineStyle: { width: 1.2, color: '#3b82f6' } 
      });
    }
  }

  // KDJ panel
  if (wantKdj) {
    const kdjIdx = addPanelGrid('kdj');
    if (kdjIdx != null) {
      series.push({ 
        type: 'line', 
        name: 'K', 
        data: kArr, 
        xAxisIndex: kdjIdx, 
        yAxisIndex: kdjIdx, 
        showSymbol: false, 
        lineStyle: { width: 1.2, color: '#22c55e' } 
      });
      
      series.push({ 
        type: 'line', 
        name: 'D', 
        data: dArr, 
        xAxisIndex: kdjIdx, 
        yAxisIndex: kdjIdx, 
        showSymbol: false, 
        lineStyle: { width: 1.2, color: '#f59e0b' } 
      });
      
      series.push({ 
        type: 'line', 
        name: 'J', 
        data: jArr, 
        xAxisIndex: kdjIdx, 
        yAxisIndex: kdjIdx, 
        showSymbol: false, 
        lineStyle: { width: 1.2, color: '#ef4444' } 
      });
    }
  }

  // BIAS panel
  if (wantBias) {
    const biasIdx = addPanelGrid('bias');
    if (biasIdx != null) {
      series.push({ 
        type: 'line', 
        name: 'BIAS20', 
        data: biasMap[20], 
        xAxisIndex: biasIdx, 
        yAxisIndex: biasIdx, 
        showSymbol: false, 
        lineStyle: { width: 1.2, color: '#8b5cf6' } 
      });
      
      series.push({ 
        type: 'line', 
        name: 'BIAS30', 
        data: biasMap[30], 
        xAxisIndex: biasIdx, 
        yAxisIndex: biasIdx, 
        showSymbol: false, 
        lineStyle: { width: 1.2, color: '#06b6d4' } 
      });
      
      series.push({ 
        type: 'line', 
        name: 'BIAS60', 
        data: biasMap[60], 
        xAxisIndex: biasIdx, 
        yAxisIndex: biasIdx, 
        showSymbol: false, 
        lineStyle: { width: 1.2, color: '#9333ea' } 
      });
    }
  }

  return {
    series,
    grids,
    xAxes,
    yAxes,
    restPanels
  };
}