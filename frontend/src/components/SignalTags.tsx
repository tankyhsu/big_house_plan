import { Tag, Tooltip } from "antd";
import dayjs from "dayjs";
import type { SignalRow, SignalType } from "../api/types";
import { getSignalConfig } from "../utils/signalConfig";

interface SignalTagsProps {
  signals: SignalRow[];
  maxDisplay?: number;
}

const getRelativeTimeText = (tradeDate: string): string => {
  const signalDay = dayjs(tradeDate);
  const now = dayjs();
  const daysDiff = now.diff(signalDay, 'days');
  
  if (daysDiff === 0) {
    return '今天';
  } else if (daysDiff === 1) {
    return '1天前';
  } else if (daysDiff === 2) {
    return '2天前';
  } else if (daysDiff === 3) {
    return '3天前';
  } else {
    // 3天以前显示具体日期
    return signalDay.format('MM-DD');
  }
};

export default function SignalTags({ signals, maxDisplay = 5 }: SignalTagsProps) {
  if (!signals || signals.length === 0) return null;

  const displaySignals = signals.slice(0, maxDisplay);
  const hasMore = signals.length > maxDisplay;

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
      {displaySignals.map((signal, idx) => {
        const config = getSignalConfig(signal.type as SignalType);
        const relativeTime = getRelativeTimeText(signal.trade_date);
        
        // 构建详细的提示信息
        const tooltipTitle = (
          <div>
            <div><strong>{relativeTime}</strong></div>
            <div>{config.emoji} {config.label}</div>
            <div style={{ marginTop: 4, fontSize: '12px', color: '#666' }}>
              {signal.message}
            </div>
          </div>
        );
        
        return (
          <Tooltip 
            key={idx} 
            title={tooltipTitle}
            overlayStyle={{ maxWidth: 300 }}
          >
            <Tag 
              style={{ 
                margin: 0, 
                fontSize: '11px',
                backgroundColor: config.color + '20',
                borderColor: config.color,
                color: config.color
              }}
            >
              {config.emoji} {config.label}
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