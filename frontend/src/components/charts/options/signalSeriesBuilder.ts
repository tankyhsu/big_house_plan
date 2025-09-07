import { getSignalConfig } from "../../../utils/signalConfig";
import type { SignalType } from "../../../api/types";
import type { Signal, Item } from './types';

export function buildSignalSeries(params: {
  signals: Signal[];
  items: Item[];
  dates: string[];
}) {
  const { signals, items, dates } = params;
  
  // 分离ZIG信号、利空利好信号和其他信号
  const zigSignals = signals.filter(s => s.type === 'ZIG_BUY' || s.type === 'ZIG_SELL');
  const sentimentSignals = signals.filter(s => s.type === 'BULLISH' || s.type === 'BEARISH');
  const otherSignals = signals.filter(s => 
    s.type !== 'ZIG_BUY' && s.type !== 'ZIG_SELL' && 
    s.type !== 'BULLISH' && s.type !== 'BEARISH'
  );
  
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
  
  const processedSignals = otherSignals.map(signal => {
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
    
    // 为了确保信号不影响Y轴范围，将信号位置限制在价格范围内
    // 同时添加一个隐形的tooltip系列用于交互
    const signalData = signalsOfType.map(signal => {
      const item = items.find(it => it.date === signal.date);
      let signalPrice: number;
      
      if (config.position === 'bottom') {
        const lowPrice = item ? (item.low ?? item.close) : (signal.price ?? 0);
        // 将信号位置限制在低价附近，不超出合理范围
        signalPrice = Math.max((lowPrice || 0) * (config.offsetMultiplier || 0.995), (lowPrice || 0) * 0.99);
      } else {
        const highPrice = item ? (item.high ?? item.close) : (signal.price ?? 0);
        // 将信号位置限制在高价附近，不超出合理范围
        signalPrice = Math.min((highPrice || 0) * (config.offsetMultiplier || 1.005), (highPrice || 0) * 1.01);
      }
      
      return {
        value: [signal.date, signalPrice],
        signalData: signal, // Store the full signal data for click handling
        tooltip: {
          formatter: `${config.emoji}${config.label}: ${signal.message || signal.type}`
        },
        label: {
          show: !isStructureSignal, // 隐藏结构信号的文字标签
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
    });

    series.push({
      type: 'scatter',
      name: config.label,
      data: signalData,
      symbol: config.symbol || 'circle',
      symbolSize: 12,
      symbolRotate: config.symbolRotate || 0,
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

    // 为结构信号添加倒计时数字标签：
    // 规则调整：向前倒数8天（标记1~8），第9天为信号当日标记为“9”
    if (isStructureSignal) {
      const countdownData: any[] = [];
      
      signalsOfType.forEach(signal => {
        const signalDateIdx = dates.indexOf(signal.date);
        if (signalDateIdx >= 8) { // 确保有足够的前置日期（仅前8天）
          // 在信号前8天添加数字标签 1..8（离信号越近数字越大）
          for (let i = 8; i >= 1; i--) {
            const targetDateIdx = signalDateIdx - i;
            if (targetDateIdx >= 0 && targetDateIdx < dates.length) {
              const targetDate = dates[targetDateIdx];
              const targetItem = items[targetDateIdx];
              
              // 根据信号类型决定倒计时数字位置
              let countdownPrice;
              let labelPosition;
              
              if (signalType === 'SELL_STRUCTURE') {
                // 卖出信号倒计时显示在蜡烛图上方，使用合理的固定偏移
                const highPrice = targetItem.high ?? targetItem.close;
                countdownPrice = highPrice * 1.015; // 使用较小的固定倍数避免过度偏移
                labelPosition = 'top';
              } else {
                // 买入信号倒计时显示在蜡烛图下方，使用合理的固定偏移
                const lowPrice = targetItem.low ?? targetItem.close;
                countdownPrice = lowPrice * 0.985; // 使用较小的固定倍数避免过度偏移
                labelPosition = 'bottom';
              }
              
              const labelText = String(9 - i); // i=8..1 -> 1..8
              countdownData.push({
                value: [targetDate, countdownPrice],
                label: {
                  show: true,
                  position: labelPosition, // 根据信号类型动态调整位置
                  formatter: labelText, // 显示 1..8
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
          // 在信号当日追加“9”标记
          const todayItem = items[signalDateIdx];
          if (todayItem) {
            let todayPrice;
            let todayPos;
            if (signalType === 'SELL_STRUCTURE') {
              const highPrice = todayItem.high ?? todayItem.close;
              todayPrice = highPrice * 1.015; // 使用与倒计时标签一致的偏移
              todayPos = 'top';
            } else {
              const lowPrice = todayItem.low ?? todayItem.close;
              todayPrice = lowPrice * 0.985; // 使用与倒计时标签一致的偏移
              todayPos = 'bottom';
            }
            countdownData.push({
              value: [signal.date, todayPrice],
              label: {
                show: true,
                position: todayPos,
                formatter: '9',
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

  // 处理ZIG信号和利空利好信号 - 转换为markPoint格式，不影响Y轴范围
  const processSpecialSignals = (signalsArray: typeof signals, yPosition: 'top' | 'bottom') => {
    return signalsArray.map(signal => {
      const price = signal.price || findPriceForDate(signal.date);
      if (price === null || price === undefined) return null;
      
      let displayDate = signal.date;
      if (!items.find(it => it.date === signal.date)) {
        const signalDate = new Date(signal.date);
        const validItems = items.filter(it => new Date(it.date) <= signalDate);
        if (validItems.length > 0) {
          validItems.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
          displayDate = validItems[0].date;
        }
      }
      
      return {
        ...signal,
        date: displayDate,
        price,
        yPosition
      };
    }).filter(signal => signal !== null);
  };

  const processedZigSignals = processSpecialSignals(zigSignals, 'bottom');
  const processedSentimentSignals = processSpecialSignals(sentimentSignals, 'top');

  // 计算基于Y轴实际值的信号位置，确保信号始终在可视范围内
  const calculateAxisPosition = (items: Item[], yPosition: 'top' | 'bottom') => {
    if (items.length === 0) return 0;
    
    const allPrices = items.flatMap(item => [
      item.open, item.close, item.high || item.close, item.low || item.close
    ]).filter(p => p != null && !isNaN(p));
    
    const minPrice = Math.min(...allPrices);
    const maxPrice = Math.max(...allPrices);
    const priceRange = maxPrice - minPrice;
    
    // 使用固定的像素等价偏移量，避免百分比带来的不稳定
    // 根据价格数量级动态计算合适的偏移量
    const priceDigits = Math.floor(Math.log10(maxPrice)) + 1;
    const baseOffset = Math.pow(10, Math.max(priceDigits - 3, -2)); // 基础偏移量
    
    if (yPosition === 'bottom') {
      // 在最低价下方留出更多空间，让买卖点显示更低
      return Math.max(minPrice - Math.max(baseOffset, priceRange * 0.1), minPrice * 0.98);
    } else {
      // 在最高价上方留出固定空间，但不超出合理范围
      return Math.min(maxPrice + Math.max(baseOffset, priceRange * 0.02), maxPrice * 1.02);
    }
  };

  const bottomAxisY = calculateAxisPosition(items, 'bottom');
  const topAxisY = calculateAxisPosition(items, 'top');

  // 添加隐形散点系列，用于让 ZIG/情绪信号参与 tooltip（不改变视觉与坐标范围）
  if (processedZigSignals.length > 0) {
    series.push({
      type: 'scatter',
      name: '__ZIG_TOOLTIP__',
      data: processedZigSignals.map((signal: any) => {
        const idx = dates.indexOf(signal.date);
        const base = idx >= 0 && items[idx] ? (items[idx].close ?? signal.price ?? 0) : (signal.price ?? 0);
        return { value: [signal.date, base], signalData: signal };
      }),
      symbolSize: 1,
      itemStyle: { opacity: 0 },
      xAxisIndex: 0,
      yAxisIndex: 0,
      z: 0
    });
  }

  if (processedSentimentSignals.length > 0) {
    series.push({
      type: 'scatter',
      name: '__SENTIMENT_TOOLTIP__',
      data: processedSentimentSignals.map((signal: any) => {
        const idx = dates.indexOf(signal.date);
        const base = idx >= 0 && items[idx] ? (items[idx].close ?? signal.price ?? 0) : (signal.price ?? 0);
        return { value: [signal.date, base], signalData: signal };
      }),
      symbolSize: 1,
      itemStyle: { opacity: 0 },
      xAxisIndex: 0,
      yAxisIndex: 0,
      z: 0
    });
  }

  return { 
    series,
    signalGroups,
    specialMarkPoints: [
      // ZIG信号标记点 - 显示在X轴上方
      ...processedZigSignals.map((signal: any) => {
        const config = getSignalConfig(signal.type as SignalType);
        return {
          coord: [signal.date, bottomAxisY],
          symbol: config.symbol || 'triangle',
          symbolSize: 14,
          symbolRotate: config.symbolRotate || 0,
          itemStyle: {
            color: config.color,
            borderColor: '#fff',
            borderWidth: 2
          },
          label: {
            show: true,
            position: 'top',
            formatter: config.label,
            textStyle: {
              color: config.color,
              fontSize: 10,
              fontWeight: 'bold',
              backgroundColor: 'rgba(255,255,255,0.9)',
              padding: [2, 4],
              borderRadius: 3,
              borderColor: config.color,
              borderWidth: 1
            }
          },
          signalData: signal
        };
      }),
      // 利空利好信号标记点 - 显示在图表顶部
      ...processedSentimentSignals.map((signal: any) => {
        const config = getSignalConfig(signal.type as SignalType);
        return {
          coord: [signal.date, topAxisY],
          symbol: config.symbol || 'circle',
          symbolSize: 14,
          symbolRotate: config.symbolRotate || 0,
          itemStyle: {
            color: config.color,
            borderColor: '#fff',
            borderWidth: 2
          },
          label: {
            show: true,
            position: 'top',
            formatter: `${config.emoji}${config.label}`,
            textStyle: {
              color: config.color,
              fontSize: 10,
              fontWeight: 'bold',
              backgroundColor: 'rgba(255,255,255,0.9)',
              padding: [1, 3],
              borderRadius: 2,
              borderColor: config.color,
              borderWidth: 1
            }
          },
          signalData: signal
        };
      })
    ]
  };
}
