import { Badge, Table, Tag, Typography, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { PositionRow, SignalRow } from "../api/types";
import { fmtCny, fmtPct } from "../utils/format";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import dayjs from "dayjs";
import { fetchAllSignals } from "../api/hooks";
import SignalTags from "./SignalTags";
import { getSignalsForTsCode } from "../hooks/useRecentSignals";

export default function PositionTable({ data, loading }: { data: PositionRow[]; loading: boolean }) {
  const [signals, setSignals] = useState<SignalRow[]>([]);

  // 获取最近一个月的信号数据
  useEffect(() => {
    const loadSignals = async () => {
      try {
        const oneMonthAgo = dayjs().subtract(1, "month").format("YYYY-MM-DD");
        const today = dayjs().format("YYYY-MM-DD");
        const signalData = await fetchAllSignals(undefined, undefined, oneMonthAgo, today, 200);
        console.log('📊 PositionTable loaded signals:', signalData?.length || 0, 'signals', signalData);
        setSignals(signalData || []);
      } catch (error) {
        console.error("Failed to load signals:", error);
        setSignals([]);
      }
    };
    loadSignals();
  }, []);
  const columns: ColumnsType<PositionRow> = [
    { title: "类别", dataIndex: "cat_name", render: (t, r) => <>{t}{r.cat_sub? <span style={{ color:"#98A2B3" }}> / {r.cat_sub}</span> : null}</> },
    { title: "代码/名称", dataIndex: "ts_code", render: (t, r) => {
      const tsSignals = getSignalsForTsCode(signals, t);
      console.log('📋 Row render:', t, 'signals found:', tsSignals?.length || 0, 'tsSignals:', tsSignals);
      return (
        <div>
          <Link to={`/instrument/${t}`} style={{ fontWeight: 'bold' }}>
            {t}
          </Link>
          <div style={{ color:"#667085", display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span>{r.name}</span>
            {tsSignals.length > 0 && (
              <SignalTags signals={tsSignals} maxDisplay={3} />
            )}
          </div>
        </div>
      );
    }},
    { title: "持仓份额", dataIndex: "shares", align: "right", width: 120, render: (v)=> v ?? "-" },
    { title: "均价", dataIndex: "avg_cost", align: "right", width: 100, render: (v) => v===null? "-" : v.toFixed(4) },
    { title: "现价", dataIndex: "close", align: "right", width: 100,
      render: (v, r) => r.price_source==="eod"
        ? (v===null? "-" : v.toFixed(4))
        : <Tooltip title="缺日收；用均价代替"><Badge color="gold" />{v===null? "-" : v.toFixed(4)}</Tooltip>
    },
    { title: "市值", dataIndex: "market_value", align: "right", render: fmtCny },
    { title: "成本", dataIndex: "cost", align: "right", render: fmtCny },
    { title: "未实现盈亏", dataIndex: "unrealized_pnl", align: "right", render: fmtCny },
    { title: "收益率", dataIndex: "ret", align: "right", render: fmtPct, width: 100 },
    { title: "信号", dataIndex: "ts_code", align: "center", width: 120,
      render: (ts_code) => {
        const tsSignals = getSignalsForTsCode(ts_code);
        if (tsSignals.length === 0) return "-";
        
        // 显示最新的信号
        const latestSignal = tsSignals[0];
        const color = latestSignal.type === "STOP_GAIN" ? "red" : 
                     latestSignal.type === "STOP_LOSS" ? "volcano" : 
                     latestSignal.type === "UNDERWEIGHT" ? "blue" : "gray";
        
        const label = latestSignal.type === "STOP_GAIN" ? "止盈" :
                     latestSignal.type === "STOP_LOSS" ? "止损" :
                     latestSignal.type === "UNDERWEIGHT" ? "低配" : latestSignal.type;
        
        return (
          <Tooltip title={`${latestSignal.trade_date}: ${latestSignal.message}`}>
            <Tag color={color}>
              {label}
            </Tag>
          </Tooltip>
        );
      }},
  ];
  return (
    <>
      <Typography.Title level={5} style={{ marginTop: 24 }}>标的持仓</Typography.Title>
      <Table size="small" rowKey={(r)=>r.ts_code} columns={columns} dataSource={data} loading={loading} pagination={{ pageSize: 10 }} />
    </>
  );
}