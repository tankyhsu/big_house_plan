import { getSignalConfig } from "../../../utils/signalConfig";
import type { SignalType } from "../../../api/types";
import type { Signal, Item } from './types';

export function buildSignalSeries(params: {
  signals: Signal[];
  items: Item[];
  dates: string[];
}) {
  const { signals, items, dates } = params;
  
  // Process signals and resolve prices - only include signals that have valid prices
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
  
  // Group signals by type for different visual representations
  const signalGroups = processedSignals.reduce((groups, signal) => {
    if (!groups[signal.type]) {
      groups[signal.type] = [];
    }
    groups[signal.type].push(signal);
    return groups;
  }, {} as Record<string, typeof processedSignals>);

  const series: any[] = [];
  
  // Add all signal types with unified rendering logic
  Object.entries(signalGroups).forEach(([signalType, signalsOfType]) => {
    if (signalsOfType.length === 0) return;
    
    const config = getSignalConfig(signalType as SignalType);
    const isStructureSignal = signalType === 'BUY_STRUCTURE' || signalType === 'SELL_STRUCTURE';
    
    series.push({
      type: 'scatter',
      name: config.label,
      data: signalsOfType.map(signal => {
        const item = items.find(it => it.date === signal.date);
        let signalPrice: number;
        
        if (config.position === 'bottom') {
          const lowPrice = item ? (item.low ?? item.close) : (signal.price ?? 0);
          signalPrice = (lowPrice || 0) * (config.offsetMultiplier || 1.01);
        } else {
          const highPrice = item ? (item.high ?? item.close) : (signal.price ?? 0);
          signalPrice = (highPrice || 0) * (config.offsetMultiplier || 1.01);
        }
        
        return {
          value: [signal.date, signalPrice],
          signalData: signal, // Store the full signal data for click handling
          tooltip: {
            formatter: `${config.emoji}${config.label}: ${signal.message || signal.type}`
          },
          label: {
            show: true,
            position: config.position || 'top',
            formatter: `${config.emoji}${config.label}`,
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
      symbol: config.symbol || 'circle',
      symbolSize: 12,
      symbolRotate: (signalType === 'SELL_SIGNAL' ? 180 : 0),
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

    // 为结构信号添加9天倒计时数字标签
    if (isStructureSignal) {
      const countdownData: any[] = [];
      
      signalsOfType.forEach(signal => {
        const signalDateIdx = dates.indexOf(signal.date);
        if (signalDateIdx >= 9) { // 确保有足够的前置日期
          // 在信号前9天添加数字标签 9, 8, 7, 6, 5, 4, 3, 2, 1
          for (let i = 9; i >= 1; i--) {
            const targetDateIdx = signalDateIdx - i;
            if (targetDateIdx >= 0 && targetDateIdx < dates.length) {
              const targetDate = dates[targetDateIdx];
              const targetItem = items[targetDateIdx];
              
              // 倒计时数字统一显示在蜡烛图下方
              const lowPrice = targetItem.low ?? targetItem.close;
              const countdownPrice = lowPrice * 0.97; // 在蜡烛图下方
              
              countdownData.push({
                value: [targetDate, countdownPrice],
                label: {
                  show: true,
                  position: 'bottom', // 统一在下方显示
                  formatter: String(10 - i), // 显示 9, 8, 7, 6, 5, 4, 3, 2, 1
                  textStyle: {
                    color: config.color,
                    fontSize: 10,
                    fontWeight: 'bold',
                    backgroundColor: '#fff',
                    padding: [1, 2],
                    borderRadius: 2,
                    borderColor: config.color,
                    borderWidth: 1,
                    shadowColor: config.color,
                    shadowBlur: 2,
                    shadowOffsetY: 1
                  }
                }
              });
            }
          }
        }
      });

      if (countdownData.length > 0) {
        series.push({
          type: 'scatter',
          name: `${config.label}倒计时`,
          data: countdownData,
          symbol: 'circle',
          symbolSize: 8,
          itemStyle: {
            color: config.color,
            borderColor: '#fff',
            borderWidth: 1,
            opacity: 0.7
          },
          xAxisIndex: 0,
          yAxisIndex: 0,
          z: 4,
          silent: true // 不响应鼠标事件
        });
      }
    }
  });

  return { 
    series,
    signalGroups 
  };
}