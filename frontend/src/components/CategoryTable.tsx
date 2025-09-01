import { Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { CategoryRow } from "../api/types";
import { fmtCny, fmtPct, formatNumber } from "../utils/format";

// 头部 import 无需变

type TreeRow = CategoryRow & { key?: string; children?: TreeRow[] };

export default function CategoryTable({ data, loading, header = true, height }: { data: CategoryRow[]; loading: boolean; header?: boolean; height?: number }) {
  // 将平铺的类别行，按一级大类 name 分组为可展开的树形
  // 父级行做汇总（target/actual/mv/cost/pnl/ret/overweight/suggest）
  const treeData: TreeRow[] = (() => {
    const byName = new Map<string, CategoryRow[]>();
    (data || []).forEach((r) => {
      const k = r.name || "";
      if (!byName.has(k)) byName.set(k, []);
      byName.get(k)!.push(r);
    });

    const res: TreeRow[] = [];
    for (const [name, rows] of Array.from(byName.entries()).sort((a, b) => a[0].localeCompare(b[0]))) {
      // 子项按 sub_name 排序（空在前）
      const children = rows
        .slice()
        .sort((a, b) => (a.sub_name || "").localeCompare(b.sub_name || ""))
        .map((r) => ({ ...r, key: String(r.category_id) }));

      // 汇总父级
      const sum = (fn: (r: CategoryRow) => number) => rows.reduce((acc, r) => acc + (Number(fn(r)) || 0), 0);
      const target_units = sum((r) => r.target_units);
      const actual_units = sum((r) => r.actual_units);
      const market_value = sum((r) => r.market_value);
      const cost = sum((r) => r.cost);
      const pnl = sum((r) => r.pnl);
      const gap_units = target_units - actual_units;
      const ret = cost > 0 ? pnl / cost : null;

      // 使用默认带宽 20%（与说明一致）；如需精确可后续接入设置接口
      const band = 0.2;
      const lower = target_units * (1 - band);
      const upper = target_units * (1 + band);
      const overweight = actual_units < lower || actual_units > upper ? 1 : 0;

      const parent: TreeRow = {
        key: `grp:${name}`,
        category_id: -1, // 占位，不用于 rowKey
        name,
        sub_name: "",
        target_units,
        actual_units,
        gap_units,
        market_value,
        cost,
        pnl,
        ret,
        overweight: overweight as 0 | 1,
        suggest_units: Math.round(gap_units),
        children,
      } as TreeRow;
      res.push(parent);
    }
    return res;
  })();

  const columns: ColumnsType<TreeRow> = [
    {
      title: "类别",
      dataIndex: "name",
      key: "name",
      render: (t, r) => {
        const isParent = Array.isArray((r as any).children) && (r as any).children.length > 0;
        // 父级行显示一级分类；子级行仅显示二级分类（无二级则退化为一级名称）
        if (isParent) return <>{t}</>;
        return <>{(r.sub_name && r.sub_name.trim()) ? r.sub_name : t}</>;
      },
    },
    {
      title: "目标份",
      dataIndex: "target_units",
      align: "right",
      width: 80,
      render: (v: number) => formatNumber(v, 2),
    },
    {
      title: "实际份",
      dataIndex: "actual_units",
      align: "right",
      width: 80,
      render: (v: number) => formatNumber(v, 2),
    },
    // 删除：市值/成本/收益 三列，保留核心配置与收益率
    { title: "收益率", dataIndex: "ret", align: "right", render: fmtPct, width: 80 },

    // === 配置偏离：细分“超配/配置不足/未持仓/在目标范围内” ===
    {
      title: "配置偏离",
      dataIndex: "overweight",
      align: "center",
      width: 120,
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
      {header && (
        <>
          <Typography.Title level={5} style={{ marginTop: 16 }}>类别分布</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
            目标范围 = 目标份额 ± 设置里的带宽（默认 20%）。
            状态区分：<strong>超配</strong>（建议减仓） / <strong>配置不足</strong>（建议加仓） / <strong>未持仓</strong> / 在目标范围内。
          </Typography.Paragraph>
        </>
      )}
      <Table
        size="small"
        rowKey={(r) => (r as any).key || String((r as any).category_id)}
        columns={columns as ColumnsType<any>}
        dataSource={treeData as any}
        loading={loading}
        pagination={false}
        expandable={{ defaultExpandAllRows: false }}
        scroll={height ? { y: height } : undefined}
      />
    </>
  );
}
