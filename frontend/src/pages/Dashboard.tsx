import { useEffect, useMemo, useState } from "react";
import { Button, DatePicker, Flex, message, Space, Row, Col } from "antd";
import dayjs from "dayjs";
import KpiCards from "../components/KpiCards";
import CategoryTable from "../components/CategoryTable";
import PositionTable from "../components/PositionTable";
import PositionPie from "../components/charts/PositionPie";
import TotalAssetsLine from "../components/charts/TotalAssetsLine";
import { fetchDashboard, fetchCategory, fetchPosition, postCalc, postSyncPrices } from "../api/hooks";
import type { CategoryRow, PositionRow } from "../api/types";
import { dashedToYmd } from "../utils/format";
import { ReloadOutlined, CalculatorOutlined, CloudSyncOutlined } from "@ant-design/icons";

export default function Dashboard() {
  const [date, setDate] = useState(dayjs()); // UI 用 YYYY-MM-DD
  const ymd = useMemo(()=> dashedToYmd(date.format("YYYY-MM-DD")), [date]);
  const [loading, setLoading] = useState(false);
  const [cat, setCat] = useState<CategoryRow[]>([]);
  const [pos, setPos] = useState<PositionRow[]>([]);
  const [dash, setDash] = useState<any>(null);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [d, c, p] = await Promise.all([
        fetchDashboard(ymd),
        fetchCategory(ymd),
        fetchPosition(ymd),
      ]);
      setDash(d); setCat(c); setPos(p);
    } catch (e:any) {
      message.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(()=>{ loadAll(); }, [ymd]);

  const onCalc = async () => {
    try {
      await postCalc(ymd);
      message.success("已重算快照");
      loadAll();
    } catch (e:any) { message.error(e.message); }
  };

  const onSync = async () => {
    try {
      const res = await postSyncPrices(ymd);
      if (res.reason === "no_token") {
        message.info("未配置 TuShare Token，已跳过价格同步");
      } else {
        message.success(`已同步价格：${res.updated}/${res.found}`);
      }
    } catch (e:any) { message.error(e.message); }
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Flex justify="space-between" align="center" wrap="wrap" gap={12}>
        <h2 style={{ margin: 0 }}>长赢指数投资计划 - Dashboard</h2>
        <Space>
          <DatePicker value={date} onChange={(d)=> d && setDate(d)} allowClear={false} />
          <Button icon={<CloudSyncOutlined />} onClick={onSync}>同步价格</Button>
          <Button type="primary" icon={<CalculatorOutlined />} onClick={onCalc}>重算</Button>
          <Button icon={<ReloadOutlined />} onClick={loadAll}>刷新</Button>
        </Space>
      </Flex>

      {dash && (
        <KpiCards
          marketValue={dash.kpi.market_value}
          cost={dash.kpi.cost}
          pnl={dash.kpi.unrealized_pnl}
          ret={dash.kpi.ret}
          signals={dash.signals}
          priceFallback={dash.price_fallback_used}
          dateText={dash.date}
        />
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24} md={30}><PositionPie /></Col>
        <Col xs={24} md={30}><TotalAssetsLine /></Col>
      </Row>

      <CategoryTable data={cat} loading={loading} />
      <PositionTable data={pos} loading={loading} />
    </Space>
  );
}