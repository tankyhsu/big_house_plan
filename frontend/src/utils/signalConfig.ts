import type { SignalType, SignalLevel } from "../api/types";

// 统一的信号配置接口
export interface SignalConfig {
  label: string;
  color: string;
  description: string;
  emoji: string;
  symbol?: string;
  position?: 'top' | 'bottom';
  offsetMultiplier?: number;
}

// 信号类型配置
export const SIGNAL_CONFIG: Record<SignalType, SignalConfig> = {
  UNDERWEIGHT: { 
    label: "低配", 
    color: "#3b82f6", 
    description: "类别配置低于目标范围", 
    emoji: "📊", 
    symbol: "circle", 
    position: "top", 
    offsetMultiplier: 1.01 
  },
  BUY_SIGNAL: { 
    label: "买入", 
    color: "#10b981", 
    description: "买入信号", 
    emoji: "📈", 
    symbol: "triangle", 
    position: "top", 
    offsetMultiplier: 1.015 
  },
  SELL_SIGNAL: { 
    label: "卖出", 
    color: "#ef4444", 
    description: "卖出信号", 
    emoji: "📉", 
    symbol: "triangle", 
    position: "top", 
    offsetMultiplier: 1.015 
  },
  BUY_STRUCTURE: { 
    label: "买入结构", 
    color: "#52c41a", 
    description: "通达信买入结构信号", 
    emoji: "🏗️", 
    symbol: "triangle", 
    position: "top", 
    offsetMultiplier: 1.02 
  },
  SELL_STRUCTURE: { 
    label: "卖出结构", 
    color: "#ff4d4f", 
    description: "通达信卖出结构信号", 
    emoji: "🏗️", 
    symbol: "triangle", 
    position: "bottom", 
    offsetMultiplier: 0.98 
  },
  REBALANCE: { 
    label: "再平衡", 
    color: "#8b5cf6", 
    description: "需要再平衡调整", 
    emoji: "⚖️", 
    symbol: "diamond", 
    position: "top", 
    offsetMultiplier: 1.025 
  },
  RISK_ALERT: { 
    label: "风险预警", 
    color: "#ec4899", 
    description: "风险预警信号", 
    emoji: "⚡", 
    symbol: "circle", 
    position: "top", 
    offsetMultiplier: 1.01 
  },
  MOMENTUM: { 
    label: "动量", 
    color: "#06b6d4", 
    description: "动量信号", 
    emoji: "🚀", 
    symbol: "circle", 
    position: "top", 
    offsetMultiplier: 1.008 
  },
  MEAN_REVERT: { 
    label: "均值回归", 
    color: "#1e40af", 
    description: "均值回归信号", 
    emoji: "🔄", 
    symbol: "circle", 
    position: "top", 
    offsetMultiplier: 1.008 
  },
  BULLISH: { 
    label: "利好", 
    color: "#52c41a", 
    description: "利好政策或市场信号", 
    emoji: "📈", 
    symbol: "circle", 
    position: "top", 
    offsetMultiplier: 1.01 
  },
  BEARISH: { 
    label: "利空", 
    color: "#fa8c16", 
    description: "利空政策或市场信号", 
    emoji: "📉", 
    symbol: "circle", 
    position: "top", 
    offsetMultiplier: 1.01 
  },
};

// 信号级别配置
export const LEVEL_CONFIG: Record<SignalLevel, { label: string; color: string }> = {
  HIGH: { label: "高", color: "error" },
  MEDIUM: { label: "中", color: "warning" },
  LOW: { label: "低", color: "processing" },
  INFO: { label: "信息", color: "default" },
};

// 获取信号类型的颜色
export const getSignalColor = (type: SignalType): string => {
  return SIGNAL_CONFIG[type]?.color || "#1890ff";
};

// 获取信号类型的标签
export const getSignalLabel = (type: SignalType): string => {
  return SIGNAL_CONFIG[type]?.label || type;
};

// 获取完整的信号配置
export const getSignalConfig = (type: SignalType): SignalConfig => {
  return SIGNAL_CONFIG[type] || {
    label: type,
    color: "#1890ff",
    description: "",
    emoji: "📍",
    symbol: "circle",
    position: "top",
    offsetMultiplier: 1.01
  };
};

// 获取信号优先级（用于多信号排序）
export const getSignalPriority = (type: SignalType): number => {
  const priorityOrder: Record<SignalType, number> = {
    RISK_ALERT: 4,
    SELL_SIGNAL: 3,
    BUY_SIGNAL: 3,
    BUY_STRUCTURE: 3,
    SELL_STRUCTURE: 3,
    REBALANCE: 2,
    MOMENTUM: 1,
    MEAN_REVERT: 1,
    BULLISH: 1,
    BEARISH: 1,
    UNDERWEIGHT: 0,
  };
  
  return priorityOrder[type] || 0;
};