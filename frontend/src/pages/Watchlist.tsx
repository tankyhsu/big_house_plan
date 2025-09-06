import { useEffect, useMemo, useState } from "react";
import { Button, Card, DatePicker, Flex, Input, message, Modal, Space, Table, AutoComplete, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { dashedToYmd } from "../utils/format";
import { addWatchlist, fetchAllSignals, fetchInstruments, fetchWatchlist, removeWatchlist } from "../api/hooks";
import type { InstrumentLite, SignalRow, WatchlistItem } from "../api/types";
import InstrumentDisplay, { createInstrumentOptions } from "../components/InstrumentDisplay";
import CandleChart from "../components/charts/CandleChart";

export default function WatchlistPage() {
  const [date, setDate] = useState(dayjs()); // UI: YYYY-MM-DD
  const ymd = useMemo(() => dashedToYmd(date.format("YYYY-MM-DD")), [date]);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [adding, setAdding] = useState(false);
  const [instQuery, setInstQuery] = useState<string>("");
  const [instOptions, setInstOptions] = useState<{ value: string; label: string }[]>([]);
  const [instSelect, setInstSelect] = useState<string>("");
  const [note, setNote] = useState<string>("");
  const [selected, setSelected] = useState<WatchlistItem | null>(null);
  const [signals, setSignals] = useState<SignalRow[]>([]);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  // const [signalsLoading, setSignalsLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchWatchlist(ymd);
      setItems(data);
      // 保持当前选中项
      if (selected) {
        const cur = data.find(d => d.ts_code === selected.ts_code) || null;
        setSelected(cur);
      }
    } catch (e: any) {
      message.error(e?.message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [ymd]);

  // 查询标的用于添加
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        if (!instQuery || instQuery.trim().length < 1) { setInstOptions([]); return; }
        const list: InstrumentLite[] = await fetchInstruments(instQuery.trim());
        // 仅取展示需要的字段，避免类型不匹配
        const simple = list.map(it => ({ ts_code: it.ts_code, name: it.name, cat_name: it.cat_name, cat_sub: it.cat_sub }));
        if (!cancelled) setInstOptions(createInstrumentOptions(simple as any));
      } catch {
        if (!cancelled) setInstOptions([]);
      }
    };
    run();
    return () => { cancelled = true; };
  }, [instQuery]);

  const onAdd = async () => {
    const code = (instSelect || instQuery).trim();
    if (!code) { message.warning("请输入代码"); return; }
    setAdding(true);
    try {
      await addWatchlist(code, note || undefined);
      message.success("已加入自选");
      setInstQuery("");
      setInstSelect("");
      setNote("");
      await load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || "添加失败");
    } finally {
      setAdding(false);
    }
  };

  const onRemove = async (ts_code: string) => {
    try {
      await removeWatchlist(ts_code);
      message.success("已移除");
      if (selected?.ts_code === ts_code) {
        setSelected(null);
        setDetailModalOpen(false);
      }
      await load();
    } catch (e: any) {
      message.error(e?.message || "移除失败");
    }
  };

  const onViewDetail = (item: WatchlistItem) => {
    setSelected(item);
    setDetailModalOpen(true);
  };

  // 加载选中标的最近信号（用于K线图叠加）
  useEffect(() => {
    const run = async () => {
      if (!selected?.ts_code) { setSignals([]); return; }
      // setSignalsLoading(true);
      try {
        const today = dayjs().format("YYYY-MM-DD");
        const sixMonthsAgo = dayjs().subtract(6, "month").format("YYYY-MM-DD");
        const rows = await fetchAllSignals(undefined, selected.ts_code, sixMonthsAgo, today, 200);
        setSignals(rows || []);
      } catch {
        setSignals([]);
      } finally {
        // setSignalsLoading(false);
      }
    };
    run();
  }, [selected?.ts_code]);

  const columns: ColumnsType<WatchlistItem> = [
    {
      title: "标的",
      dataIndex: "ts_code",
      key: "ts_code",
      width: 200,
      render: (_: any, r) => (
        <div>
          <InstrumentDisplay data={{ ts_code: r.ts_code, name: (r.name || undefined) }} />
          {r.has_position && <Tag color="blue" size="small" style={{ marginTop: 4 }}>已持仓</Tag>}
        </div>
      ),
    },
    {
      title: "最新价",
      dataIndex: "last_price",
      align: "right",
      width: 110,
      render: (v: any) => (typeof v === 'number' ? v.toFixed(3) : "-")
    },
    {
      title: "日期",
      dataIndex: "last_price_date",
      width: 110,
      render: (v: any) => v || "-",
    },
    {
      title: "备注",
      dataIndex: "note",
      ellipsis: true,
      render: (v: any) => v || "-",
    },
    {
      title: "创建",
      dataIndex: "created_at",
      width: 120,
      render: (v: any) => (v ? v.replace("T", " ") : "-"),
    },
    {
      title: "操作",
      key: "op",
      width: 120,
      render: (_: any, r) => (
        <Space size={8}>
          <Button size="small" onClick={() => onViewDetail(r)}>查看</Button>
          <Button size="small" danger onClick={() => onRemove(r.ts_code)}>移除</Button>
        </Space>
      )
    },
  ];

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Flex justify="space-between" align="center" wrap="wrap" gap={12}>
        <h2 style={{ margin: 0 }}>自选关注</h2>
        <Space>
          <DatePicker value={date} onChange={(d) => d && setDate(d)} allowClear={false} />
          <Button onClick={load}>刷新</Button>
        </Space>
      </Flex>

      <Card title="我的自选" size="small" styles={{ body: { padding: 12 } }}>
        <div style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: "100%" }} size={8}>
            <AutoComplete
              style={{ width: "100%" }}
              options={instOptions}
              value={instSelect || instQuery}
              onSelect={(v) => setInstSelect(v)}
              onSearch={(v) => { setInstQuery(v); setInstSelect(""); }}
              placeholder="输入代码或名称搜索"
              allowClear
            />
            <Flex gap={8}>
              <Input 
                placeholder="备注（可选）" 
                value={note} 
                onChange={(e) => setNote(e.target.value)} 
                style={{ flex: 1 }}
              />
              <Button type="primary" loading={adding} onClick={onAdd}>加入</Button>
            </Flex>
          </Space>
        </div>
        <Table
          size="small"
          rowKey={(r) => r.ts_code}
          loading={loading}
          dataSource={items}
          columns={columns}
          pagination={{ pageSize: 15, showTotal: (t) => `共 ${t} 条` }}
          scroll={{ x: 'max-content' }}
        />
      </Card>

      <Modal
        title={selected ? `${selected.ts_code}｜${selected.name ?? ''}` : "标的详情"}
        open={detailModalOpen}
        onCancel={() => setDetailModalOpen(false)}
        width={1000}
        footer={[
          <Button key="remove" danger onClick={() => selected && onRemove(selected.ts_code)}>
            从自选中移除
          </Button>,
          <Button key="close" onClick={() => setDetailModalOpen(false)}>
            关闭
          </Button>,
        ]}
        destroyOnClose
      >
        {selected ? (
          <CandleChart
            tsCode={selected.ts_code}
            secType={(selected.type || '').toUpperCase()}
            months={6}
            title="K线（近6个月）"
            signals={(signals || []).map(s => ({
              date: s.trade_date,
              type: s.type,
              level: s.level,
              message: s.message,
            }))}
          />
        ) : (
          <div style={{ color: '#667085', padding: 12 }}>加载中...</div>
        )}
      </Modal>
    </Space>
  );
}
