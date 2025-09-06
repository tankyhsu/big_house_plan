import { useEffect, useMemo, useRef, useState } from "react";
import { Button, Card, DatePicker, Flex, Input, message, Modal, Space, Table, AutoComplete, Tag, Form, Select, Alert } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { dashedToYmd } from "../utils/format";
import { addWatchlist, fetchAllSignals, fetchInstruments, fetchWatchlist, removeWatchlist, fetchCategories, createInstrument, lookupInstrument } from "../api/hooks";
import type { InstrumentLite, SignalRow, WatchlistItem, CategoryLite } from "../api/types";
import InstrumentDisplay, { createInstrumentOptions } from "../components/InstrumentDisplay";
import CandleChart from "../components/charts/CandleChart";

// 完整 ts_code 格式：6 位数字 + 点 + 2~3 位字母（如 510300.SH / 110011.OF）
const TS_CODE_FULL_RE = /^\d{6}\.[A-Za-z]{2,3}$/i;

export default function WatchlistPage() {
  const [date, setDate] = useState(dayjs()); // UI: YYYY-MM-DD
  const ymd = useMemo(() => dashedToYmd(date.format("YYYY-MM-DD")), [date]);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<WatchlistItem[]>([]);
  
  // 新增相关状态
  const [addOpen, setAddOpen] = useState(false);
  const [addForm] = Form.useForm();
  const [instOpts, setInstOpts] = useState<InstrumentLite[]>([]);
  const [categories, setCategories] = useState<CategoryLite[]>([]);
  const [searching, setSearching] = useState(false);
  const searchTimer = useRef<number | null>(null);
  
  // 新代码登记 Modal
  const [newInstOpen, setNewInstOpen] = useState(false);
  const [newInstForm] = Form.useForm();
  const [pendingWatchlist, setPendingWatchlist] = useState<{ ts_code: string; note?: string } | null>(null);
  const [autoLookupName, setAutoLookupName] = useState<string | null>(null);
  
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

  useEffect(() => { 
    load(); 
    // 预加载下拉数据
    fetchInstruments().then(setInstOpts).catch(()=>{});
    fetchCategories().then(setCategories).catch(()=>{});
  }, [ymd]);

  // 防抖搜索标的
  const onSearch = (kw: string) => {
    if (searchTimer.current) window.clearTimeout(searchTimer.current);
    searchTimer.current = window.setTimeout(async () => {
      try {
        setSearching(true);
        const rows = await fetchInstruments(kw || undefined);
        setInstOpts(rows);
      } finally {
        setSearching(false);
      }
    }, 250);
  };

  // 提交新增自选
  const onAdd = async () => {
    try {
      const vals = await addForm.validateFields();
      const tsCode: string = (typeof vals.ts_code === "string" ? vals.ts_code : vals.ts_code?.value)?.trim();
      if (!tsCode) throw new Error("请输入/选择 ts_code");

      const exists = instOpts.some(i => i.ts_code === tsCode);
      if (!exists) {
        // 新代码：弹出登记窗口，暂存关注请求
        setPendingWatchlist({ ts_code: tsCode, note: vals.note?.trim() || undefined });
        newInstForm.resetFields();
        newInstForm.setFieldsValue({ ts_code: tsCode, active: true });
        
        // 如果是完整的 ts_code 格式，尝试自动查询基础信息
        if (TS_CODE_FULL_RE.test(tsCode)) {
          lookupInstrument(tsCode).then(info => {
            if (info?.name) {
              setAutoLookupName(info.name);
              newInstForm.setFieldsValue({ name: info.name });
            } else {
              // 即使没有名称，也表示查询过了，避免用户以为没有自动查询
              setAutoLookupName("（未查询到名称，需手动输入）");
            }
            if (info?.type) {
              newInstForm.setFieldsValue({ type: info.type });
            }
          }).catch(() => {
            setAutoLookupName("（查询失败，请检查代码格式）");
          });
        } else {
          setAutoLookupName(null);
        }
        
        setNewInstOpen(true);
        return;
      }

      // 已存在代码：直接添加到自选
      await addWatchlist(tsCode, vals.note?.trim() || undefined);
      message.success("已加入自选");
      setAddOpen(false);
      addForm.resetFields();
      await load();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e.message || "添加失败");
    }
  };
  
  // 新代码登记-提交
  const onCreateInstrument = async () => {
    try {
      const vals = await newInstForm.validateFields();
      await createInstrument({
        ts_code: vals.ts_code.trim(),
        name: vals.name.trim(),
        category_id: Number(vals.category_id),
        active: !!vals.active,
        type: vals.type,
      });
      message.success("已登记新标的");
      setNewInstOpen(false);
      setAutoLookupName(null);

      // 刷新标的列表
      const rows = await fetchInstruments(vals.ts_code.trim());
      setInstOpts(rows);

      // 如果有待添加的关注，补提
      if (pendingWatchlist) {
        await addWatchlist(pendingWatchlist.ts_code, pendingWatchlist.note);
        message.success("已加入自选");
        setPendingWatchlist(null);
        setAddOpen(false);
        addForm.resetFields();
        await load();
      }
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e.message || "登记失败");
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
          <Button type="primary" onClick={() => setAddOpen(true)}>新增自选</Button>
        </Space>
      </Flex>

      <Card title="我的自选" size="small" styles={{ body: { padding: 12 } }}>
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

      {/* 新增自选弹窗 */}
      <Modal
        title="新增自选"
        open={addOpen}
        onOk={onAdd}
        onCancel={() => { setAddOpen(false); addForm.resetFields(); }}
        okText="加入自选"
        cancelText="取消"
        destroyOnClose
        width={600}
      >
        <Form
          form={addForm}
          layout="vertical"
          initialValues={{}}
        >
          <Form.Item
            label="标的代码"
            name="ts_code"
            rules={[{ required: true, message: "请输入或选择 ts_code" }]}
          >
            <AutoComplete
              options={createInstrumentOptions(instOpts)}
              onSearch={onSearch}
              placeholder="如 510300.SH，支持搜索或直接输入新代码"
              allowClear
              notFoundContent={searching ? "搜索中..." : "可直接输入新代码"}
              filterOption={(inputValue, option) =>
                (option?.value as string)?.toUpperCase().includes(inputValue.toUpperCase()) ||
                (option?.label as string)?.toUpperCase().includes(inputValue.toUpperCase())
              }
            />
          </Form.Item>

          <Form.Item label="备注" name="note">
            <Input.TextArea placeholder="可选，如：关注原因、预期策略等" rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 新代码登记弹窗 */}
      <Modal
        title="登记新标的"
        open={newInstOpen}
        onOk={onCreateInstrument}
        onCancel={() => { setNewInstOpen(false); newInstForm.resetFields(); setPendingWatchlist(null); setAutoLookupName(null); }}
        okText="保存并加入自选"
        cancelText="取消"
        destroyOnClose
      >
        <Alert 
          type="info" 
          showIcon 
          style={{ marginBottom: 16 }} 
          message="检测到新代码" 
          description="该标的尚未在系统中，需先登记基础信息后加入自选关注。" 
        />
        
        <Form form={newInstForm} layout="vertical">
          <Form.Item label="代码" name="ts_code" rules={[{ required: true }]}>
            <Input disabled />
          </Form.Item>
          <Form.Item 
            label="名称" 
            name="name" 
            rules={[{ required: true, message: "请输入名称" }]}
            extra={autoLookupName ? `TuShare 查询结果：${autoLookupName}` : undefined}
          >
            <Input placeholder="如 沪深300ETF" />
          </Form.Item>
          <Form.Item label="类型" name="type" initialValue="STOCK" rules={[{ required: true }]}>
            <Select
              options={[
                { value: "STOCK", label: "股票（交易所收盘价）" },
                { value: "ETF", label: "ETF（交易所收盘价）" },
                { value: "FUND", label: "基金（净值）" },
                { value: "CASH", label: "现金/货基（不拉行情）" },
              ]}
            />
          </Form.Item>
          <Form.Item label="类别" name="category_id" rules={[{ required: true, message: "请选择类别" }]}>
            <Select
              showSearch
              options={categories.map(c => ({
                value: c.id,
                label: `${c.name}${c.sub_name ? ` / ${c.sub_name}` : ""}`
              }))}
              placeholder="选择类别"
              filterOption={(input, option) => (option?.label as string).toLowerCase().includes(input.toLowerCase())}
            />
          </Form.Item>
          <Form.Item label="启用" name="active" initialValue={true} valuePropName="checked">
            <Select
              options={[
                { value: true, label: "是" },
                { value: false, label: "否" },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
