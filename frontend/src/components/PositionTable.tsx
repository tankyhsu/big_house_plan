import { Badge, Table, Tag, Typography, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { PositionRow } from "../api/types";
import { fmtCny, fmtPct } from "../utils/format";

export default function PositionTable({ data, loading }: { data: PositionRow[]; loading: boolean }) {
  const columns: ColumnsType<PositionRow> = [
    { title: "类别", dataIndex: "cat_name", render: (t, r) => <>{t}{r.cat_sub? <span style={{ color:"#98A2B3" }}> / {r.cat_sub}</span> : null}</> },
    { title: "代码/名称", dataIndex: "ts_code", render: (t, r) => <div><strong>{t}</strong><div style={{ color:"#667085" }}>{r.name}</div></div> },
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
    { title: "信号", dataIndex: "stop_gain_hit", align: "center", width: 90,
      render: (v) => v ? <Tag color="green">止盈</Tag> : "-" },
  ];
  return (
    <>
      <Typography.Title level={5} style={{ marginTop: 24 }}>标的持仓</Typography.Title>
      <Table size="small" rowKey={(r)=>r.ts_code} columns={columns} dataSource={data} loading={loading} pagination={{ pageSize: 10 }} />
    </>
  );
}