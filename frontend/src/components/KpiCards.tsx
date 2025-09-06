import { Card, Col, Row, Statistic, Tag, Tooltip } from "antd";
import { fmtCny, fmtPct } from "../utils/format";
import { InfoCircleOutlined } from "@ant-design/icons";
import { getSignalConfig } from "../utils/signalConfig";
import type { SignalType } from "../api/types";

type Props = {
  marketValue: number; cost: number; pnl: number; ret: number | null;
  signals: Record<string, number>;
  priceFallback: boolean;
  dateText: string;
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
              .map(([type, count]) => {
                const config = getSignalConfig(type.toUpperCase() as SignalType);
                return (
                  <Tag 
                    key={type}
                    style={{ 
                      margin: 0, 
                      fontSize: '12px',
                      backgroundColor: config.color,
                      borderColor: config.color,
                      color: '#fff',
                      fontWeight: 'bold'
                    }}
                  >
                    {config.label}: {count}
                  </Tag>
                );
              })
            }
            {Object.values(signals).every(count => count === 0) && (
              <Tag style={{ 
                margin: 0, 
                fontSize: '12px',
                backgroundColor: '#f5f5f5',
                borderColor: '#d9d9d9',
                color: '#666'
              }}>
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
