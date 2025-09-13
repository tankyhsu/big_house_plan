import type { Trade } from './types';

export function buildTradeMarkers(params: {
  buys: Trade[];
  sells: Trade[];
  upColor: string;
  downColor: string;
}) {
  const { buys, sells, upColor, downColor } = params;
  
  const series: any[] = [];

  // Buy markers
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

  // Sell markers
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
    symbolRotate: 180, 
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

  return { series };
}