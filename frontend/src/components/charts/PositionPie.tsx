import { useEffect, useState } from "react";
import ReactECharts from "echarts-for-react";
import { Card } from "antd";
import { fetchCategory } from "../../api/hooks";
import dayjs from "dayjs";
import { formatQuantity } from "../../utils/format";

type PieDatum = { name: string; value: number };

export default function PositionPie({ date }: { date?: string }) {
  const [data, setData] = useState<PieDatum[]>([]);

  useEffect(() => {
    const ymd = date || dayjs().format("YYYYMMDD");
    fetchCategory(ymd).then(rows => {
      const items = rows
        .filter(r => (r.market_value || 0) > 0)
        .map(r => ({
          // 仅显示二级分类；若无二级分类则退化为一级名称
          name: r.sub_name && r.sub_name.trim() ? r.sub_name : r.name,
          value: Number(formatQuantity(r.market_value || 0)),
        }));
      setData(items);
    }).catch(() => setData([]));
  }, [date]);

  const option = {
    tooltip: { trigger: "item", formatter: "{b}<br/>{c} 元 ({d}%)" },
    legend: { type: "scroll", orient: "vertical", right: 0, top: 20, bottom: 20 },
    series: [
      {
        type: "pie",
        radius: ["40%", "70%"],
        center: ["40%", "50%"],
        avoidLabelOverlap: true,
        label: { show: true, formatter: "{b|{b}}\n{d}%", rich: { b: { fontWeight: 500 } }, fontSize: 11 },
        labelLine: { length: 8, length2: 6 },
        data,
      },
    ],
  };

  return (
    <Card title="持仓比例（按市值）" size="small" styles={{ body: { padding: 12 } }}>
      <ReactECharts notMerge lazyUpdate option={option as any} style={{ height: 320 }} />
    </Card>
  );
}
