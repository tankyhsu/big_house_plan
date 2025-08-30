import { useEffect, useMemo, useState } from "react";
import { Card, Select, Space, Switch, Tag } from "antd";
import PositionSeriesLine from "./PositionSeriesLine";
import { fetchPositionRaw } from "../../api/hooks";
import type { PositionRaw } from "../../api/types";

type Option = { value: string; label: string };

type Props = {
  title?: string;
  defaultNormalize?: boolean;
};

export default function PositionSeriesPanel({ title, defaultNormalize = false }: Props) {
  const [includeZero, setIncludeZero] = useState(false);
  const [positions, setPositions] = useState<PositionRaw[]>([]);
  const [loading, setLoading] = useState(false);
  const [codes, setCodes] = useState<string[]>([]);
  const [normalize, setNormalize] = useState<boolean>(defaultNormalize);

  const load = async () => {
    setLoading(true);
    try {
      const rows = await fetchPositionRaw(includeZero);
      setPositions(rows);
      // 若当前选择为空，自动选择第一个（非强制）
      if (codes.length === 0 && rows.length > 0) {
        setCodes([rows[0].ts_code]);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [includeZero]);

  const options: Option[] = useMemo(() =>
    (positions || []).map(p => ({
      value: p.ts_code,
      label: `${p.ts_code}｜${p.inst_name || ''}`,
    })), [positions]
  );

  return (
    <Card
      title={title || "标的历史对比"}
      size="small"
      extra={
        <Space>
          <span>包含0仓</span>
          <Switch size="small" checked={includeZero} onChange={setIncludeZero} />
          <span>归一化</span>
          <Switch size="small" checked={normalize} onChange={setNormalize} />
        </Space>
      }
      bodyStyle={{ padding: 12 }}
      loading={loading}
    >
      <Space direction="vertical" style={{ width: "100%" }} size={8}>
        <Select
          mode="multiple"
          allowClear
          placeholder="选择一个或多个持仓标的"
          showSearch
          options={options}
          value={codes}
          onChange={setCodes}
          style={{ width: "100%" }}
          maxTagCount="responsive"
          filterOption={(input, option) => {
            const lab = (option?.label as string) || "";
            const val = (option?.value as string) || "";
            const key = `${lab} ${val}`.toLowerCase();
            return key.includes(input.toLowerCase());
          }}
        />

        {codes.length === 0 ? (
          <Tag color="gold">请选择至少一个标的</Tag>
        ) : (
          <PositionSeriesLine tsCodes={codes} normalize={normalize} />
        )}
      </Space>
    </Card>
  );
}
