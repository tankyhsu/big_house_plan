import { Card, Col, Row, Statistic, Tag, Tooltip } from "antd";
import { fmtCny, fmtPct } from "../utils/format";
import { InfoCircleOutlined } from "@ant-design/icons";

// 更灵活的信号类型定义，支持任意信号类型
type Props = {
  marketValue: number; cost: number; pnl: number; ret: number | null;
  signals: Record<string, number>;
  priceFallback: boolean;
  dateText: string;
};

// 信号类型配置
const SIGNAL_LABELS: Record<string, string> = {
  'stop_gain': '止盈',
  'stop_loss': '止损',
  'overweight': '超配',
  'underweight': '低配',
  'buy_signal': '买入',
  'sell_signal': '卖出',
  'rebalance': '再平衡',
  'risk_alert': '风险预警',
  'momentum': '动量',
  'mean_revert': '均值回归',
};

const SIGNAL_COLORS: Record<string, string> = {
  'stop_gain': '#f5222d',
  'stop_loss': '#fa541c',
  'overweight': '#faad14',
  'underweight': '#1890ff',
  'buy_signal': '#52c41a',
  'sell_signal': '#f5222d',
  'rebalance': '#722ed1',
  'risk_alert': '#eb2f96',
  'momentum': '#13c2c2',
  'mean_revert': '#2f54eb',
};

export default function KpiCards({ marketValue, cost, pnl, ret, signals, priceFallback, dateText }: Props) {
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} md={12} lg={8} style={{ display: "flex" }}>
        <Card
          style={{
            background: "linear-gradient(135deg,#67c1ff 0%,#1677ff 100%)",
            color: "#fff",
            flex: 1,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <Statistic title={<span style={{ color: "rgba(255,255,255,0.85)" }}>总资产（{dateText}）</span>}
                     value={marketValue}
                     formatter={(v) => <span style={{ color: "#fff", fontWeight: 700 }}>{fmtCny(Number(v))}</span>} />
          <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ color: "rgba(255,255,255,0.9)" }}>累计收益：</span>
            <span style={{ color: "#fff", fontWeight: 600 }}>{fmtCny(pnl)}</span>
            {priceFallback && (
              <Tooltip title="今日部分标的缺乏收盘价，已用均价代替计算">
                <Tag color="gold" style={{ marginLeft: 8 }}>价格回退 <InfoCircleOutlined /></Tag>
              </Tooltip>
            )}
          </div>
        </Card>
      </Col>
      <Col xs={24} md={12} lg={8} style={{ display: "flex" }}>
        <Card style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 1fr",
              columnGap: 16,
              alignItems: "end",
            }}
          >
            <Statistic title="投入成本" value={fmtCny(cost)} style={{ minWidth: 0 }} />
            <Statistic title="组合收益率" value={ret === null ? "-" : fmtPct(ret)} style={{ minWidth: 0 }} />
          </div>
        </Card>
      </Col>
      <Col xs={24} md={12} lg={8} style={{ display: "flex" }}>
        <Card style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <div style={{ marginBottom: 8, fontSize: 14, fontWeight: 500, color: '#262626' }}>
            信号统计（近一个月）
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
            {Object.entries(signals)
              .filter(([_, count]) => count > 0)
              .map(([type, count]) => (
                <Tag 
                  key={type}
                  color={SIGNAL_COLORS[type] || 'default'}
                  style={{ margin: 0, fontSize: '12px', display: 'flex', alignItems: 'center' }}
                >
                  {SIGNAL_LABELS[type] || type}: {count}
                </Tag>
              ))
            }
            {Object.values(signals).every(count => count === 0) && (
              <Tag color="default" style={{ margin: 0, fontSize: '12px' }}>
                暂无信号
              </Tag>
            )}
          </div>
          <div style={{ color: "#8c8c8c", fontSize: 11, marginTop: 'auto' }}>
            基于近30天信号记录统计
          </div>
        </Card>
      </Col>
    </Row>
  );
}
