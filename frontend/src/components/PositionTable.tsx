import { Badge, Table, Typography, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { PositionRow } from "../api/types";
import { fmtCny, fmtPct, formatQuantity, formatPrice } from "../utils/format";
import { Link } from "react-router-dom";
import SignalTags from "./SignalTags";
import { getSignalsForTsCode } from "../hooks/useRecentSignals";

export default function PositionTable({ data, loading, signals }: { data: PositionRow[]; loading: boolean; signals: any[] }) {
  const columns: ColumnsType<PositionRow> = [
    { title: "类别", dataIndex: "cat_name", render: (t, r) => <>{t}{r.cat_sub? <span style={{ color:"#98A2B3" }}> / {r.cat_sub}</span> : null}</> },
    { title: "代码/名称", dataIndex: "ts_code", render: (t, r) => {
      const tsSignals = getSignalsForTsCode(signals, t);
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
    { title: "持仓份额", dataIndex: "shares", align: "right", width: 120, render: (v)=> formatQuantity(v) },
    { title: "均价", dataIndex: "avg_cost", align: "right", width: 100, render: (v) => formatPrice(v) },
    { title: "现价", dataIndex: "close", align: "right", width: 100,
      render: (v, r) => r.price_source==="eod"
        ? formatPrice(v)
        : <Tooltip title="缺日收；用均价代替"><Badge color="gold" />{formatPrice(v)}</Tooltip>
    },
    { title: "市值", dataIndex: "market_value", align: "right", render: fmtCny },
    { title: "成本", dataIndex: "cost", align: "right", render: fmtCny },
    { title: "未实现盈亏", dataIndex: "unrealized_pnl", align: "right", render: fmtCny },
    { title: "收益率", dataIndex: "ret", align: "right", render: fmtPct, width: 100 },
  ];
  return (
    <>
      <Typography.Title level={5} style={{ marginTop: 24 }}>标的持仓</Typography.Title>
      <Table size="small" rowKey={(r)=>r.ts_code} columns={columns} dataSource={data} loading={loading} pagination={{ pageSize: 10 }} />
    </>
  );
}