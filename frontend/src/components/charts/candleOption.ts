import { buildChartLayout } from "./options/layoutBuilder";
import { buildPriceSeries } from "./options/priceSeriesBuilder";
import { buildTradeMarkers } from "./options/tradeMarkersBuilder";
import { buildSignalSeries } from "./options/signalSeriesBuilder";
import { buildTechnicalIndicators } from "./options/technicalIndicatorsBuilder";
import { buildLegends } from "./options/legendBuilder";
import { buildTooltipFormatter } from "./options/tooltipBuilder";
import type { CandleOptionParams } from "./options/types";

export function buildCandleOption(params: CandleOptionParams) {
  const { items, tsCode, secType, maList, buys, sells, signals, viewportH, fullscreen, klineConfig } = params;
  
  // Basic data preparation
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

  // Build layout configuration
  const layout = buildChartLayout({ secType, viewportH, fullscreen });
  const { panels, layoutH, leftPad, legendH, wantMacd, wantKdj, wantBias, wantVol, restPanels } = layout;

  // Initialize arrays for ECharts configuration
  const allSeries: any[] = [];
  let grids: any[] = [];
  let xAxes: any[] = [];
  let yAxes: any[] = [];

  // Build price panel (main K-line chart)
  const pricePanel = panels.find(p => p.key === 'price')!;
  grids.push({ 
    left: leftPad, 
    right: 24, 
    top: pricePanel.top, 
    height: pricePanel.height, 
    containLabel: false, 
    show: true, 
    borderColor: '#e5e7eb', 
    borderWidth: 1 
  });
  
  xAxes.push({ 
    gridIndex: 0, 
    type: 'category', 
    data: dates, 
    boundaryGap: false, 
    axisLine: { onZero: false } 
  });
  
  yAxes.push({ 
    gridIndex: 0, 
    scale: true, 
    splitNumber: 4, 
    name: '价格', 
    nameLocation: 'middle', 
    nameGap: 70, 
    nameTextStyle: { color: '#667085' }, 
    axisLabel: { align: 'right', margin: 6 } 
  });

  // Build price series (candlestick, MA lines, cost/profit-loss lines)
  const priceSeriesResult = buildPriceSeries({ 
    items, 
    tsCode, 
    dates, 
    kValues, 
    maList, 
    klineConfig 
  });
  
  allSeries.push(...priceSeriesResult.series);

  // Build trade markers (buy/sell points)
  const tradeMarkersResult = buildTradeMarkers({
    buys,
    sells,
    upColor: priceSeriesResult.upColor,
    downColor: priceSeriesResult.downColor
  });
  
  allSeries.push(...tradeMarkersResult.series);

  // Build signal series (various trading signals)
  const signalSeriesResult = buildSignalSeries({ signals, items, dates });
  allSeries.push(...signalSeriesResult.series);

  // Build technical indicators (MACD, KDJ, BIAS, Volume)
  const technicalIndicatorsResult = buildTechnicalIndicators({
    items,
    dates,
    panels,
    leftPad,
    legendH,
    upColor: priceSeriesResult.upColor,
    downColor: priceSeriesResult.downColor,
    wantVol,
    wantMacd,
    wantKdj,
    wantBias,
    restPanels
  });
  
  // Merge technical indicators data
  allSeries.push(...technicalIndicatorsResult.series);
  grids.push(...technicalIndicatorsResult.grids);
  xAxes.push(...technicalIndicatorsResult.xAxes);
  yAxes.push(...technicalIndicatorsResult.yAxes);

  // Build legends
  const legends = buildLegends({
    panels,
    leftPad,
    legendH,
    tsCode,
    maList,
    klineConfig,
    items,
    buys,
    sells,
    signalGroups: signalSeriesResult.signalGroups,
    restPanels
  });

  // Build tooltip formatter
  const tooltipFormatter = buildTooltipFormatter({
    items,
    dates,
    upColor: priceSeriesResult.upColor,
    downColor: priceSeriesResult.downColor,
    maColors: priceSeriesResult.maColors
  });

  // Data zoom configuration
  const xIndexList = xAxes.map((_, idx) => idx);
  const sliderHeight = 24;
  const sliderBottom = 10;

  // Final ECharts option
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
      formatter: tooltipFormatter
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
    series: allSeries,
  } as any;

  return { option, chartHeight: layoutH };
}