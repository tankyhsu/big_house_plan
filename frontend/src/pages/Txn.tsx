import { useEffect, useMemo, useRef, useState } from "react";
import { AutoComplete, Button, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, DatePicker, message, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import type { TxnItem, TxnCreate, InstrumentLite, CategoryLite } from "../api/types";
import { fetchTxnList, createTxn, fetchInstruments, fetchCategories, createInstrument } from "../api/hooks";

const ACTIONS = ["BUY", "SELL", "DIV", "FEE", "ADJ"] as const;

export default function TxnPage() {
  const [data, setData] = useState<TxnItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(20);
  const [loading, setLoading] = useState(false);

  // 新增交易弹窗
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  // 标的下拉数据
  const [instOpts, setInstOpts] = useState<InstrumentLite[]>([]);
  const [searching, setSearching] = useState(false);
  const searchTimer = useRef<number | null>(null);

  // 新代码登记 Modal
  const [newInstOpen, setNewInstOpen] = useState(false);
  const [newInstForm] = Form.useForm();
  const [categories, setCategories] = useState<CategoryLite[]>([]);
  // 暂存待提交的交易（当输入新代码时先存起来）
  const [pendingTxn, setPendingTxn] = useState<TxnCreate | null>(null);

  const load = async (p = page, s = size) => {
    setLoading(true);
    try {
      const res = await fetchTxnList(p, s);
      setData(res.items);
      setTotal(res.total);
    } catch (e: any) {
      message.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(1, size);
    // 预加载：标的、类别
    fetchInstruments().then(setInstOpts).catch(()=>{});
    fetchCategories().then(setCategories).catch(()=>{});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const columns: ColumnsType<TxnItem> = [
    { title: "日期", dataIndex: "trade_date", width: 120 },
    { title: "代码", dataIndex: "ts_code", width: 140 },
    { title: "方向", dataIndex: "action", width: 90, render: (v) =>
        v === "BUY" ? <Tag color="green">BUY</Tag> :
        v === "SELL" ? <Tag color="red">SELL</Tag> : <Tag>{v}</Tag>
    },
    { title: "数量", dataIndex: "shares", align: "right", width: 100 },
    { title: "价格", dataIndex: "price", align: "right", width: 100, render: (v) => v == null ? "-" : v.toFixed(4) },
    { title: "费用", dataIndex: "fee", align: "right", width: 100, render: (v) => v == null ? "-" : v.toFixed(2) },
    { title: "备注", dataIndex: "notes" },
  ];

  // 提交交易；若输入的是新代码，先登记 instrument
  const onOk = async () => {
    try {
      const vals = await form.validateFields();
      const tsCode: string = (typeof vals.ts_code === "string" ? vals.ts_code : vals.ts_code?.value)?.trim();
      if (!tsCode) throw new Error("请输入/选择 ts_code");

      const payload: TxnCreate = {
        ts_code: tsCode,
        date: vals.date.format("YYYY-MM-DD"),
        action: vals.action,
        shares: Number(vals.shares),
        price: typeof vals.price === "number" ? vals.price : undefined,
        fee: typeof vals.fee === "number" ? vals.fee : undefined,
        notes: vals.notes?.trim() || undefined,
      };

      const exists = instOpts.some(i => i.ts_code === tsCode);
      if (!exists) {
        // 新代码：弹出登记窗口，暂存交易
        setPendingTxn(payload);
        newInstForm.resetFields();
        newInstForm.setFieldsValue({ ts_code: tsCode, active: true });
        setNewInstOpen(true);
        return;
      }

      // 旧代码：直接创建交易
      await createTxn(payload);
      message.success("新增交易成功");
      setOpen(false);
      form.resetFields();
      setPage(1);
      load(1, size);
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e.message || "提交失败");
    }
  };

  // 构造下拉 options
  const options = useMemo(
    () =>
      instOpts.map((i) => ({
        value: i.ts_code,
        label: `${i.ts_code}｜${i.name || ""}${i.cat_name ? `（${i.cat_name}${i.cat_sub ? `/${i.cat_sub}` : ""}）` : ""}`,
      })),
    [instOpts]
  );

  // 防抖搜索
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

      // 刷新标的列表（使刚创建的可选）
      const rows = await fetchInstruments(vals.ts_code.trim());
      setInstOpts(rows);

      // 如果有待提交的交易，补提
      if (pendingTxn) {
        await createTxn(pendingTxn);
        message.success("新增交易成功");
        setPendingTxn(null);
        setOpen(false);
        form.resetFields();
        setPage(1);
        load(1, size);
      }
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e.message || "登记失败");
    }
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Typography.Title level={3} style={{ margin: 0 }}>交易流水</Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
        选择已有标的，或直接输入一个新的代码（例如 510300.SH）。卖出会在后端校验可用持仓。
      </Typography.Paragraph>

      <Space>
        <Button onClick={() => load(page, size)}>刷新</Button>
        <Button type="primary" onClick={() => setOpen(true)}>新增交易</Button>
      </Space>

      <Table<TxnItem>
        size="small"
        rowKey={(r) => String(r.id)}
        columns={columns}
        dataSource={data}
        loading={loading}
        pagination={{
          current: page,
          pageSize: size,
          total,
          showSizeChanger: true,
          onChange: (p, s) => { setPage(p); setSize(s); load(p, s); },
        }}
      />

      {/* 新增交易弹窗 */}
      <Modal
        title="新增交易"
        open={open}
        onOk={onOk}
        onCancel={() => { setOpen(false); form.resetFields(); }}
        okText="提交"
        cancelText="取消"
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ action: "BUY", date: dayjs(), shares: 0, fee: 0 }}
        >
          <Form.Item
            label="标的代码（可下拉选择或直接输入新代码）"
            name="ts_code"
            rules={[{ required: true, message: "请输入或选择 ts_code" }]}
          >
            <AutoComplete
              options={options}
              onSearch={onSearch}
              placeholder="如 510300.SH"
              allowClear
              notFoundContent={searching ? "搜索中..." : "可直接输入新代码"}
              filterOption={(inputValue, option) =>
                (option?.value as string)?.toUpperCase().includes(inputValue.toUpperCase()) ||
                (option?.label as string)?.toUpperCase().includes(inputValue.toUpperCase())
              }
            />
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

          <Form.Item label="交易日期" name="date" rules={[{ required: true }]}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>

          <Form.Item label="方向" name="action" rules={[{ required: true }]}>
            <Select options={ACTIONS.map(a => ({ value: a, label: a }))} />
          </Form.Item>

          <Form.Item
            label="数量（份/股）"
            name="shares"
            rules={[{ required: true, message: "请输入数量" }, { type: "number", min: 0.000001, message: "必须 > 0" }]}
          >
            <InputNumber controls={false} precision={6} style={{ width: "100%" }} />
          </Form.Item>

          <Form.Item
            label="价格（DIV/FEE/ADJ 可留空）"
            name="price"
            rules={[{ type: "number", min: 0 }]}
          >
            <InputNumber controls={false} precision={6} style={{ width: "100%" }} placeholder="如 4.560000" />
          </Form.Item>

          <Form.Item label="费用（可选）" name="fee" rules={[{ type: "number", min: 0 }]}>
            <InputNumber controls={false} precision={2} style={{ width: "100%" }} placeholder="如 1.50" />
          </Form.Item>

          <Form.Item label="备注" name="notes">
            <Input.TextArea placeholder="可选" rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 新代码登记弹窗 */}
      <Modal
        title="登记新标的"
        open={newInstOpen}
        onOk={onCreateInstrument}
        onCancel={() => { setNewInstOpen(false); newInstForm.resetFields(); setPendingTxn(null); }}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={newInstForm} layout="vertical">
          <Form.Item label="代码" name="ts_code" rules={[{ required: true }]}>
            <Input disabled />
          </Form.Item>
          <Form.Item label="名称" name="name" rules={[{ required: true, message: "请输入名称" }]}>
            <Input placeholder="如 沪深300ETF" />
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
          <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
            提示：登记后会出现在标的列表中，建议尽快完善映射信息（如需要）。
          </Typography.Paragraph>
        </Form>
      </Modal>
    </Space>
  );
}