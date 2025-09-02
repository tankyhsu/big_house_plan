import { Tag, Tooltip } from "antd";
import type { SignalRow } from "../api/types";

interface SignalTagsProps {
  signals: SignalRow[];
  maxDisplay?: number;
}

// 简化的信号配置
const getSignalColor = (type: string): string => {
  const colors: Record<string, string> = {
    'STOP_GAIN': 'red',
    'STOP_LOSS': 'volcano',
    'UNDERWEIGHT': 'blue',
    'BUY_SIGNAL': 'green',
    'SELL_SIGNAL': 'red',
    'REBALANCE': 'purple',
    'RISK_ALERT': 'magenta',
    'MOMENTUM': 'cyan',
    'MEAN_REVERT': 'geekblue',
  };
  return colors[type] || 'gray';
};

const getSignalLabel = (type: string): string => {
  const labels: Record<string, string> = {
    'STOP_GAIN': '止盈',
    'STOP_LOSS': '止损',
    'UNDERWEIGHT': '低配',
    'BUY_SIGNAL': '买入',
    'SELL_SIGNAL': '卖出',
    'REBALANCE': '再平衡',
    'RISK_ALERT': '风险预警',
    'MOMENTUM': '动量',
    'MEAN_REVERT': '均值回归',
  };
  return labels[type] || type;
};

export default function SignalTags({ signals, maxDisplay = 5 }: SignalTagsProps) {
  console.log('🏷️ SignalTags render:', signals?.length || 0, 'signals:', signals);
  if (!signals || signals.length === 0) return null;

  const displaySignals = signals.slice(0, maxDisplay);
  const hasMore = signals.length > maxDisplay;

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
      {displaySignals.map((signal, idx) => {
        const color = getSignalColor(signal.type);
        const label = getSignalLabel(signal.type);
        
        return (
          <Tooltip key={idx} title={signal.message}>
            <Tag color={color} style={{ margin: 0, fontSize: '11px' }}>
              {label}
            </Tag>
          </Tooltip>
        );
      })}
      {hasMore && (
        <Tag color="default" style={{ margin: 0, fontSize: '11px' }}>
          +{signals.length - maxDisplay}
        </Tag>
      )}
    </div>
  );
}