import { useEffect, useMemo, useState } from "react";
import { Card, Select, Space, Switch, Tag } from "antd";
import { StarOutlined, StarFilled } from "@ant-design/icons";
import React from "react";
import PositionSeriesLine from "./PositionSeriesLine";
import { fetchPositionRaw } from "../../api/hooks";
import type { PositionRaw } from "../../api/types";

type Option = { value: string; label: React.ReactNode; rawLabel?: string };

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
  const [favorites, setFavorites] = useState<string[]>([]);
  const [recents, setRecents] = useState<string[]>([]);

  const LS_KEYS = {
    fav: "ps_favorites",
    recent: "ps_recents",
    selected: "ps_selected",
  } as const;

  const load = async () => {
    setLoading(true);
    try {
      const rows = await fetchPositionRaw(includeZero);
      setPositions(rows);
      // 初始化 本地存储：收藏/最近/已选
      try {
        const fav = JSON.parse(localStorage.getItem(LS_KEYS.fav) || "[]");
        if (Array.isArray(fav)) setFavorites(fav.filter((v) => typeof v === "string"));
      } catch {}
      try {
        const rec = JSON.parse(localStorage.getItem(LS_KEYS.recent) || "[]");
        if (Array.isArray(rec)) setRecents(rec.filter((v) => typeof v === "string"));
      } catch {}
      if (codes.length === 0) {
        try {
          const sel = JSON.parse(localStorage.getItem(LS_KEYS.selected) || "[]");
          const valid = Array.isArray(sel) ? sel.filter((c: any) => typeof c === "string") : [];
          const exists = rows.map(r => r.ts_code);
          const filtered = valid.filter((c: string) => exists.includes(c));
          if (filtered.length > 0) setCodes(filtered);
          else if (rows.length > 0) setCodes([rows[0].ts_code]);
        } catch {
          if (rows.length > 0) setCodes([rows[0].ts_code]);
        }
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [includeZero]);

  const nameMap = useMemo(() => {
    const m: Record<string, string> = {};
    (positions || []).forEach(p => { m[p.ts_code] = p.inst_name || ""; });
    return m;
  }, [positions]);

  const toggleFavorite = (code: string) => {
    setFavorites((prev) => {
      const set = new Set(prev);
      if (set.has(code)) set.delete(code); else set.add(code);
      const arr = Array.from(set);
      localStorage.setItem(LS_KEYS.fav, JSON.stringify(arr));
      return arr;
    });
  };

  const onSelectChange = (vals: string[]) => {
    setCodes(vals);
    // 维护最近使用：新选择的放前面
    setRecents((prev) => {
      const arr = [...vals, ...prev.filter((c) => !vals.includes(c))];
      const uniq = Array.from(new Set(arr)).slice(0, 12);
      localStorage.setItem(LS_KEYS.recent, JSON.stringify(uniq));
      return uniq;
    });
    localStorage.setItem(LS_KEYS.selected, JSON.stringify(vals));
  };

  const options: Option[] = useMemo(() =>
    (positions || []).map(p => {
      const code = p.ts_code;
      const labelText = `${p.ts_code}｜${p.inst_name || ''}`;
      const isFav = favorites.includes(code);
      const star = isFav ? <StarFilled style={{ color: "#f5a623" }} /> : <StarOutlined style={{ color: "#999" }} />;
      return {
        value: code,
        rawLabel: labelText,
        label: (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{labelText}</span>
            <span
              onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); }}
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); toggleFavorite(code); }}
              title={isFav ? '取消收藏' : '收藏'}
              style={{ cursor: 'pointer' }}
            >{star}</span>
          </div>
        ),
      } as Option;
    }), [positions, favorites]
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
        {(favorites.length > 0) && (
          <div>
            <span style={{ marginRight: 8, color: '#667085' }}>收藏：</span>
            <Space size={6} wrap>
              {favorites.map(code => (
                <Tag
                  key={`fav-${code}`}
                  color="gold"
                  closable
                  onClose={(e) => { e.preventDefault(); toggleFavorite(code); }}
                  style={{ cursor: 'pointer' }}
                  onClick={() => {
                    const exists = codes.includes(code);
                    const next = exists ? codes.filter(c => c !== code) : [...codes, code];
                    onSelectChange(next);
                  }}
                >
                  {code}{nameMap[code] ? `｜${nameMap[code]}` : ''}
                </Tag>
              ))}
            </Space>
          </div>
        )}

        {(recents.length > 0) && (
          <div>
            <span style={{ marginRight: 8, color: '#667085' }}>最近使用：</span>
            <Space size={6} wrap>
              {recents.map(code => (
                <Tag
                  key={`rc-${code}`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => {
                    const exists = codes.includes(code);
                    const next = exists ? codes.filter(c => c !== code) : [...codes, code];
                    onSelectChange(next);
                  }}
                >
                  {code}{nameMap[code] ? `｜${nameMap[code]}` : ''}
                </Tag>
              ))}
            </Space>
          </div>
        )}
        <Select
          mode="multiple"
          allowClear
          placeholder="选择一个或多个持仓标的"
          showSearch
          options={options}
          value={codes}
          onChange={onSelectChange}
          style={{ width: "100%" }}
          maxTagCount="responsive"
          filterOption={(input, option) => {
            const lab = ((option as any)?.rawLabel as string) || "";
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
