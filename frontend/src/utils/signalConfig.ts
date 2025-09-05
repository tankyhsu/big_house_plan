import type { SignalType, SignalLevel } from "../api/types";

// 信号类型配置
export const SIGNAL_CONFIG: Record<SignalType, { label: string; color: string; description: string }> = {
  UNDERWEIGHT: { label: "低配", color: "blue", description: "类别配置低于目标范围" },
  BUY_SIGNAL: { label: "买入", color: "green", description: "买入信号" },
  SELL_SIGNAL: { label: "卖出", color: "red", description: "卖出信号" },
  REBALANCE: { label: "再平衡", color: "purple", description: "需要再平衡调整" },
  RISK_ALERT: { label: "风险预警", color: "magenta", description: "风险预警信号" },
  MOMENTUM: { label: "动量", color: "cyan", description: "动量信号" },
  MEAN_REVERT: { label: "均值回归", color: "geekblue", description: "均值回归信号" },
  BULLISH: { label: "利好", color: "green", description: "利好政策或市场信号" },
  BEARISH: { label: "利空", color: "orange", description: "利空政策或市场信号" },
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
  return SIGNAL_CONFIG[type]?.color || "gray";
};

// 获取信号类型的标签
export const getSignalLabel = (type: SignalType): string => {
  return SIGNAL_CONFIG[type]?.label || type;
};