// 信号样式配置工具函数，与 candleOption.ts 保持一致
export interface SignalConfig {
  color: string;
  emoji: string;
  name: string;
  symbol?: string;
  position?: 'top' | 'bottom';
  offsetMultiplier?: number;
}

// 信号类型颜色配置，与 candleOption.ts 保持一致
export const SIGNAL_CONFIGS: Record<string, SignalConfig> = {
  'UNDERWEIGHT': { color: '#3b82f6', emoji: '📊', name: '低配', symbol: 'circle', position: 'top', offsetMultiplier: 1.01 },
  'BUY_SIGNAL': { color: '#10b981', emoji: '📈', name: '买入', symbol: 'triangle', position: 'top', offsetMultiplier: 1.015 },
  'SELL_SIGNAL': { color: '#ef4444', emoji: '📉', name: '卖出', symbol: 'triangle', position: 'top', offsetMultiplier: 1.015 },
  'REBALANCE': { color: '#8b5cf6', emoji: '⚖️', name: '再平衡', symbol: 'diamond', position: 'top', offsetMultiplier: 1.025 },
  'RISK_ALERT': { color: '#ec4899', emoji: '⚡', name: '风险预警', symbol: 'circle', position: 'top', offsetMultiplier: 1.01 },
  'MOMENTUM': { color: '#06b6d4', emoji: '🚀', name: '动量', symbol: 'circle', position: 'top', offsetMultiplier: 1.008 },
  'MEAN_REVERT': { color: '#1e40af', emoji: '🔄', name: '均值回归', symbol: 'circle', position: 'top', offsetMultiplier: 1.008 },
  'BULLISH': { color: '#52c41a', emoji: '📈', name: '利好', symbol: 'circle', position: 'top', offsetMultiplier: 1.01 },
  'BEARISH': { color: '#fa8c16', emoji: '📉', name: '利空', symbol: 'circle', position: 'top', offsetMultiplier: 1.01 },
  'MARKET_ALERT': { color: '#f04438', emoji: '⚠️', name: '市场预警', symbol: 'circle', position: 'top', offsetMultiplier: 1.01 }
};

// 获取信号配置
export function getSignalConfig(signalType: string): SignalConfig {
  return SIGNAL_CONFIGS[signalType] || { 
    color: '#1890ff', 
    emoji: '📍', 
    name: signalType, 
    symbol: 'circle', 
    position: 'top', 
    offsetMultiplier: 1.01 
  };
}

// 获取信号优先级（用于多信号排序）
export function getSignalPriority(signalType: string): number {
  const priorityOrder: Record<string, number> = {
    'RISK_ALERT': 4, 
    'MARKET_ALERT': 4,
    'SELL_SIGNAL': 3, 
    'BUY_SIGNAL': 3,
    'REBALANCE': 2,
    'MOMENTUM': 1, 
    'MEAN_REVERT': 1, 
    'BULLISH': 1, 
    'BEARISH': 1,
    'UNDERWEIGHT': 0
  };
  
  return priorityOrder[signalType] || 0;
}