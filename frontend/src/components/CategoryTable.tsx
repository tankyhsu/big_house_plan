import { Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { CategoryRow } from "../api/types";
import { fmtCny, fmtPct, formatNumber } from "../utils/format";

// 头部 import 无需变

export default function CategoryTable({ data, loading }: { data: CategoryRow[]; loading: boolean }) {
  const columns: ColumnsType<CategoryRow> = [
    {
      title: "类别",
      dataIndex: "name",
      key: "name",
      render: (t, r) => (
        <>
          {t}
          {r.sub_name ? <span style={{ color: "#98A2B3" }}> / {r.sub_name}</span> : null}
        </>
      ),
    },
    {
      title: "目标份",
      dataIndex: "target_units",
      align: "right",
      width: 100,
      render: (v: number) => formatNumber(v, 2),
    },
    {
      title: "实际份",
      dataIndex: "actual_units",
      align: "right",
      width: 100,
      render: (v: number) => formatNumber(v, 2),
    },
    { title: "市值", dataIndex: "market_value", align: "right", render: fmtCny },
    { title: "成本", dataIndex: "cost", align: "right", render: fmtCny },
    { title: "收益", dataIndex: "pnl", align: "right", render: fmtCny },
    { title: "收益率", dataIndex: "ret", align: "right", render: fmtPct, width: 100 },

    // === 配置偏离：细分“超配/配置不足/未持仓/在目标范围内” ===
    {
      title: "配置偏离",
      dataIndex: "overweight",
      align: "center",
      width: 140,
      render: (_v, r) => {
        const isEmpty =
          (r.actual_units === 0 || r.actual_units === null) &&
          (r.market_value === 0 || r.market_value === null) &&
          (r.cost === 0 || r.cost === null);

        // 目标=0 且当前也为0：无需配置
        if ((r.target_units ?? 0) === 0 && isEmpty) {
          return <Tag>无需配置</Tag>;
        }

        // 未持仓（应配但未配）
        if (isEmpty && (r.target_units ?? 0) > 0) {
          return <Tag>未持仓</Tag>;
        }

        // 在目标范围内（未越带）
        if (r.overweight === 0) {
          return <Tag color="blue">在目标范围内</Tag>;
        }

        // 已越带：用份差/建议方向判断“超配 or 配置不足”
        const gap = r.gap_units ?? 0;            // 实际 - 目标（项目内一致口径）
        const suggest = r.suggest_units ?? 0;    // >0 表示建议加仓；<0 表示建议减仓

        if (gap > 0 || suggest > 0) {
          return <Tag color="orange">配置不足</Tag>; // 需要加仓
        }
        if (gap < 0 || suggest < 0) {
          return <Tag color="red">超配</Tag>;        // 需要减仓
        }
        // 极少数边界（数据恰为0但 overweight=1），给默认标签
        return <Tag color="gold">超出目标范围</Tag>;
      },
    },
  ];

  return (
    <>
      <Typography.Title level={5} style={{ marginTop: 16 }}>类别分布</Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
        目标范围 = 目标份额 ± 设置里的带宽（默认 20%）。
        状态区分：<strong>超配</strong>（建议减仓） / <strong>配置不足</strong>（建议加仓） / <strong>未持仓</strong> / 在目标范围内。
      </Typography.Paragraph>
      <Table
        size="small"
        rowKey={(r) => String(r.category_id)}
        columns={columns}
        dataSource={data}
        loading={loading}
        pagination={false}
      />
    </>
  );
}