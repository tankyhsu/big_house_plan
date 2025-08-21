import { Card, Col, Row, Statistic, Tag, Tooltip } from "antd";
import { fmtCny, fmtPct } from "../utils/format";
import { InfoCircleOutlined } from "@ant-design/icons";

type Props = {
  marketValue: number; cost: number; pnl: number; ret: number | null;
  signals: { stop_gain: number; overweight: number };
  priceFallback: boolean;
  dateText: string;
};

export default function KpiCards({ marketValue, cost, pnl, ret, signals, priceFallback, dateText }: Props) {
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} md={12} lg={8}>
        <Card style={{ background: "linear-gradient(135deg,#67c1ff 0%,#1677ff 100%)", color: "#fff" }}>
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
      <Col xs={24} md={12} lg={8}>
        <Card>
          <Statistic title="投入成本" value={fmtCny(cost)} />
          <div style={{ marginTop: 8 }}>
            <Statistic title="组合收益率" value={ret === null ? "-" : fmtPct(ret)} />
          </div>
        </Card>
      </Col>
      <Col xs={24} md={12} lg={8}>
        <Card>
          <div style={{ display: "flex", gap: 12 }}>
            <Statistic title="止盈信号" value={signals.stop_gain} />
            <Statistic title="超出目标范围（类别）" value={signals.overweight} />
          </div>
          <div style={{ marginTop: 12, color: "#667085", fontSize: 12 }}>
            提示：信号统计来自当日快照（/api/signal）
          </div>
        </Card>
      </Col>
    </Row>
  );
}