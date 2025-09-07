import type { SignalType, SignalLevel } from "../api/types";

// 统一的信号配置接口
export interface SignalConfig {
  label: string;
  color: string;
  description: string;
  emoji: string;
  symbol?: string;
  symbolRotate?: number, 
  position?: 'top' | 'bottom';
  offsetMultiplier?: number;
}

// 信号类型配置
export const SIGNAL_CONFIG: Record<SignalType, SignalConfig> = {
  BUY_STRUCTURE: { 
    label: "九转买入", 
    color: "#95d5b2", 
    description: "神奇九转买入信号", 
    emoji: "🏗️", 
    symbol: "triangle", 
    position: "top", 
    offsetMultiplier: 0.9
  },
  SELL_STRUCTURE: { 
    label: "九转卖出", 
    color: "#ffb3ba", 
    description: "神奇九转卖出信号", 
    emoji: "🏗️", 
    symbol: "triangle", 
    symbolRotate: 180, 
    position: "bottom", 
    offsetMultiplier: 1.1
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
    symbol: "triangle", 
    symbolRotate: 180, 
    position: "top", 
    offsetMultiplier: 1.01 
  },
  ZIG_BUY: { 
    label: "买点", 
    color: "#52c41a", 
    description: "ZIG转向买入信号", 
    emoji: "", 
    symbol: "triangle", 
    position: "top", 
    offsetMultiplier: 0.8
  },
  ZIG_SELL: { 
    label: "卖点", 
    color: "#ff4d4f", 
    description: "ZIG转向卖出信号", 
    emoji: "", 
    symbol: "triangle", 
    symbolRotate: 180, 
    position: "top", 
    offsetMultiplier: 0.8
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
    BUY_STRUCTURE: 3,
    SELL_STRUCTURE: 3,
    ZIG_BUY: 3,
    ZIG_SELL: 3,
    BULLISH: 1,
    BEARISH: 1,
  };
  
  return priorityOrder[type] || 0;
};
