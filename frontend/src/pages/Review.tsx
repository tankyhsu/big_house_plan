import { Row, Col, Space, Typography } from "antd";
import PositionSeriesPanel from "../components/charts/PositionSeriesPanel";
import TotalAssetsLine from "../components/charts/TotalAssetsLine";

export default function ReviewPage() {
  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Typography.Title level={3} style={{ margin: 0 }}>复盘分析</Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
        总资产变化与标的表现复盘。选择一个或多个标的查看历史市值走势，可切换归一化进行相对表现对比。
      </Typography.Paragraph>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={60}><TotalAssetsLine /></Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={60}><PositionSeriesPanel /></Col>
      </Row>
    </Space>
  );
}
