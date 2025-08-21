import { Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { CategoryRow } from "../api/types";
import { fmtCny, fmtPct } from "../utils/format";

// 头部 import 无需变

export default function CategoryTable({ data, loading }: { data: CategoryRow[]; loading: boolean }) {
  const columns: ColumnsType<CategoryRow> = [
    { title: "类别", dataIndex: "name", key: "name",
      render: (t, r) => <>{t}{r.sub_name ? <span style={{ color:"#98A2B3" }}> / {r.sub_name}</span> : null}</> },
    { title: "目标份", dataIndex: "target_units", align: "right", width: 100 },
    { title: "实际份", dataIndex: "actual_units", align: "right", width: 100 },
    { title: "份差", dataIndex: "gap_units", align: "right", width: 100,
      render: (v) => <span style={{ color: v>0 ? "#16a34a" : v<0 ? "#dc2626" : "#1f2937" }}>{v.toFixed(2)}</span> },
    { title: "市值", dataIndex: "market_value", align: "right", render: fmtCny },
    { title: "成本", dataIndex: "cost", align: "right", render: fmtCny },
    { title: "收益", dataIndex: "pnl", align: "right", render: fmtCny },
    { title: "收益率", dataIndex: "ret", align: "right", render: fmtPct, width: 100 },

    // === 这里替换为更合理的显示逻辑 ===
    { title: "配置偏离", dataIndex: "overweight", align: "center", width: 130,
      render: (_v, r) => {
        const isEmpty = (r.actual_units === 0 || r.actual_units === null) &&
                        (r.market_value === 0 || r.market_value === null) &&
                        (r.cost === 0 || r.cost === null);

        if (isEmpty && r.target_units > 0) {
          // 还没建仓，不显示“超配”，而显示“未持仓”
          return <Tag>未持仓</Tag>;
        }
        // 正常判断：后端已给出 overweight=1/0
        return r.overweight === 1 ? <Tag color="red">超出目标范围</Tag> : <Tag color="blue">在目标范围内</Tag>;
      }
    },

    { title: "建议调整", dataIndex: "suggest_units", align: "right", width: 110,
      render: (v, r) => {
        // 空仓时展示 “+目标份” 更直观（与 gap_units 一致）
        if ((r.actual_units ?? 0) === 0 && (r.market_value ?? 0) === 0 && (r.cost ?? 0) === 0) {
          return r.target_units ? `+${Math.round(r.target_units)} 份` : "-";
        }
        return v===null? "-" : (v>0? `+${v} 份` : `${v} 份`);
      }
    }
  ];

  return (
    <>
      <Typography.Title level={5} style={{ marginTop: 16 }}>类别分布</Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
        目标范围 = 目标份额 ± 设置里的带宽（默认 20%）。超出该范围会标记为“超配”。
      </Typography.Paragraph>
      <Table size="small" rowKey={(r)=>String(r.category_id)} columns={columns} dataSource={data} loading={loading} pagination={false} />
    </>
  );
}