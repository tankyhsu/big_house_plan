import { useEffect, useMemo, useRef, useState } from "react";
import { AutoComplete, Button, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, DatePicker, message, Typography, Alert, Row, Col } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import type { TxnItem, TxnCreate, InstrumentLite, CategoryLite } from "../api/types";
import { fetchTxnList, createTxn, fetchInstruments, fetchCategories, createInstrument, fetchPositionRaw, fetchLastPrice } from "../api/hooks";
import type { PositionRaw } from "../api/types";
import { formatQuantity, formatPrice, fmtPct } from "../utils/format";

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

  // 当前持仓/价格信息（用于增强录单体验）
  const [posRaw, setPosRaw] = useState<PositionRaw[]>([]);
  const [curShares, setCurShares] = useState<number | null>(null);
  const [curAvgCost, setCurAvgCost] = useState<number | null>(null);
  const [lastClose, setLastClose] = useState<number | null>(null);
  const [retPct, setRetPct] = useState<number | null>(null);
  const [typeLocked, setTypeLocked] = useState<boolean>(false);
  const [curName, setCurName] = useState<string | null>(null);

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
    fetchPositionRaw(true).then(setPosRaw).catch(()=>{});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 当选择 ts_code 或日期/动作变化时，刷新持仓/价格提示与快捷按钮
  const refreshContextInfo = async () => {
    const vals = form.getFieldsValue();
    const tsCode: string | undefined = (typeof vals.ts_code === "string" ? vals.ts_code : vals.ts_code?.value)?.trim();
    if (!tsCode) { setCurShares(null); setCurAvgCost(null); setLastClose(null); setRetPct(null); return; }
    // 是否已有标的（用于锁定类型）
    const inst = instOpts.find(i => i.ts_code === tsCode);
    if (inst) {
      setCurName(inst.name || null);
      const t = (inst.type || "").toString().toUpperCase();
      if (t) {
        setTypeLocked(true);
        if (form.getFieldValue("type") !== t) form.setFieldsValue({ type: t });
      } else {
        setTypeLocked(false);
      }
    } else {
      setTypeLocked(false);
      setCurName(null);
    }
    // 持仓
    const pr = posRaw.find(p => p.ts_code === tsCode);
    const shares = pr ? Number(pr.shares || 0) : 0;
    const avg = pr ? (typeof pr.avg_cost === "number" ? pr.avg_cost : null) : null;
    setCurShares(shares);
    setCurAvgCost(avg);
    // 价格：以选择的交易日或今天为准
    const ymd: string = (vals.date ? vals.date.format("YYYYMMDD") : dayjs().format("YYYYMMDD"));
    try {
      const lp = await fetchLastPrice(tsCode, ymd);
      const close = (typeof lp.close === "number") ? lp.close : null;
      setLastClose(close);
      if (close != null && avg != null && shares > 0) {
        setRetPct((close - avg) / avg);
      } else {
        setRetPct(null);
      }
      // 卖出时自动填充最新价
      if (vals.action === "SELL" && close != null) {
        form.setFieldsValue({ price: Number(close) });
      }
    } catch {
      setLastClose(null); setRetPct(null);
    }
    // 若为 SELL 且有持仓，自动带出全仓数量
    if (shares > 0 && vals.action === "SELL") {
      form.setFieldsValue({ shares: Number(shares.toFixed(6)) });
    }
  };

  // 监听 ts_code / date / action 变化
  const watchTsCode = Form.useWatch("ts_code", form);
  const watchDate = Form.useWatch("date", form);
  const watchAction = Form.useWatch("action", form);
  const watchShares = Form.useWatch("shares", form);
  const watchAmount = Form.useWatch("amount", form);
  const watchType = Form.useWatch("type", form);
  const watchPrice = Form.useWatch("price", form);
  const watchFee = Form.useWatch("fee", form);
  useEffect(() => { 
    refreshContextInfo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [watchTsCode, watchDate, watchAction, posRaw]);

  // 当类型为 CASH 时：固定价格为 1；若填写金额则自动折算数量
  useEffect(() => {
    if (form.getFieldValue('type') === 'CASH') {
      if (form.getFieldValue('price') !== 1) {
        form.setFieldsValue({ price: 1 });
      }
      const amt = form.getFieldValue('amount');
      if (typeof amt === 'number' && !Number.isNaN(amt)) {
        const q = Math.abs(Number(amt));
        if (q > 0 && form.getFieldValue('shares') !== q) {
          form.setFieldsValue({ shares: q });
        }
      }
    }
  }, [watchType, watchAmount, watchAction]);

  // 计算本次卖出收益（只在 SELL 下显示）；= shares * (price - avg_cost) - fee
  const tradePnl = useMemo(() => {
    if (watchAction !== "SELL") return null;
    const s = Number(watchShares || 0);
    const p = typeof watchPrice === "number" ? watchPrice : (watchPrice ? Number(watchPrice) : NaN);
    const f = Number(watchFee || 0);
    if (!curAvgCost && curAvgCost !== 0) return null;
    if (!s || !p || Number.isNaN(p)) return null;
    return s * (p - (curAvgCost as number)) - f;
  }, [watchAction, watchShares, watchPrice, watchFee, curAvgCost]);

  // 投资框架合规性检查
  const frameworkCompliance = useMemo(() => {
    const action = watchAction;
    const shares = Number(watchShares || 0);
    const holdings = curShares || 0;
    
    if (!action || !shares || shares <= 0) return null;

    const warnings = [];
    
    if (action === "BUY") {
      // 买入检查：是否超过1份单位
      if (shares > 1) {
        warnings.push({
          type: "warning" as const,
          message: `买入数量 ${shares} 份超过了投资框架建议的单次1份限制，可能存在冲动交易风险。建议分批建仓，避免一次性满仓。`
        });
      }
    } else if (action === "SELL") {
      // 卖出检查：是否一次性清仓
      if (holdings > 0 && shares >= holdings) {
        warnings.push({
          type: "error" as const,
          message: `准备全仓卖出 ${shares} 份（当前持有 ${holdings} 份），这违背了投资框架的渐进减仓原则。建议分批减仓，每次卖出不超过总持仓的1/2。`
        });
      } else if (holdings > 0 && shares > holdings * 0.5) {
        warnings.push({
          type: "warning" as const,
          message: `本次卖出 ${shares} 份超过持仓的一半（当前持有 ${holdings} 份），建议考虑是否符合你的投资框架，避免情绪化决策。`
        });
      }
    }
    
    return warnings.length > 0 ? warnings : null;
  }, [watchAction, watchShares, curShares]);

  const columns: ColumnsType<TxnItem> = [
    { title: "日期", dataIndex: "trade_date", width: 120 },
    { title: "代码", dataIndex: "ts_code", width: 140 },
    { title: "名称", dataIndex: "name", width: 160, render: (v) => v || "-" },
    { title: "方向", dataIndex: "action", width: 90, render: (v) =>
        v === "BUY" ? <Tag color="green">BUY</Tag> :
        v === "SELL" ? <Tag color="red">SELL</Tag> : <Tag>{v}</Tag>
    },
    { title: "数量", dataIndex: "shares", align: "right", width: 100, render: (v) => formatQuantity(v) },
    { title: "价格", dataIndex: "price", align: "right", width: 100, render: (v) => formatPrice(v) },
    { title: "费用", dataIndex: "fee", align: "right", width: 100, render: (v) => formatQuantity(v) },
    { title: "本次收益", dataIndex: "realized_pnl", align: "right", width: 120,
      render: (v, row) => {
        if (row.action !== "SELL" || v == null) return "-";
        const n = Number(v);
        const color = n > 0 ? "#cf1322" : (n < 0 ? "#096dd9" : undefined);
        const sign = n > 0 ? "+" : "";
        return <span style={{ color }}>{sign}{formatQuantity(n)}</span>;
      }
    },
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
      if (vals.action === 'ADJ' || vals.action === 'DIV' || vals.action === 'FEE') {
        if (typeof vals.amount === 'number') {
          (payload as any).amount = vals.amount;
        }
      }

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
        width={720}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ action: "BUY", date: dayjs(), shares: 0, fee: 0 }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="标的代码"
                name="ts_code"
                rules={[{ required: true, message: "请输入或选择 ts_code" }]}
              >
                <AutoComplete
                  options={options}
                  onSearch={onSearch}
                  onChange={() => { setTimeout(refreshContextInfo, 0); }}
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
                  disabled={typeLocked}
                  options={[
                    { value: "STOCK", label: "股票（交易所收盘价）" },
                    { value: "ETF", label: "ETF（交易所收盘价）" },
                    { value: "FUND", label: "基金（净值）" },
                    { value: "CASH", label: "现金/货基（不拉行情）" },
                  ]}
                />
              </Form.Item>

              <Form.Item label="交易日期" name="date" rules={[{ required: true }]}>
                <DatePicker style={{ width: "100%" }} onChange={() => { setTimeout(refreshContextInfo, 0); }} />
              </Form.Item>

              <Form.Item label="方向" name="action" rules={[{ required: true }]}>
                <Select options={ACTIONS.map(a => ({ value: a, label: a }))} onChange={() => { setTimeout(refreshContextInfo, 0); }} />
              </Form.Item>
            </Col>
            
            <Col span={12}>
              {form.getFieldValue('type') !== 'CASH' && (
                <Form.Item
                  label="数量（份/股）"
                  name="shares"
                  rules={[{ required: true, message: "请输入数量" }, { type: "number", min: 0.000001, message: "必须 > 0" }]}
                >
                  <InputNumber controls={false} precision={6} style={{ width: "100%" }} />
                </Form.Item>
              )}

              {form.getFieldValue('type') !== 'CASH' && (
                <Form.Item
                  label="价格（DIV/FEE/ADJ 可留空）"
                  name="price"
                  rules={[{ type: "number", min: 0 }]}
                >
                  <InputNumber
                    controls={false}
                    precision={6}
                    style={{ width: "100%" }}
                    placeholder="如 4.560000"
                  />
                </Form.Item>
              )}

              <Form.Item label="费用（可选）" name="fee" rules={[{ type: "number", min: 0 }]}>
                <InputNumber controls={false} precision={2} style={{ width: "100%" }} placeholder="如 1.50" />
              </Form.Item>

              <Form.Item label="备注" name="notes">
                <Input.TextArea placeholder="可选" rows={3} />
              </Form.Item>
            </Col>
          </Row>

          {(form.getFieldValue('action') === 'ADJ' || form.getFieldValue('type') === 'CASH') && (
            <Form.Item
              label={form.getFieldValue('type') === 'CASH' ? '金额（自动按单价1折算数量）' : '金额（正=入金，负=出金）'}
              name="amount"
              rules={[{ required: true, message: '请输入金额' }]}
            >
              <InputNumber controls={false} precision={2} style={{ width: '100%' }} />
            </Form.Item>
          )}

          {/* 当前持仓/价格提示 + 快捷仓位按钮 */}
          <div style={{ marginBottom: 8 }}>
            <Space wrap size={[8, 8]}>
              <Typography.Text type="secondary">
                标的名称：{curName ?? "-"}
              </Typography.Text>
              <Typography.Text type="secondary">
                当前持仓：{curShares != null ? curShares : "-"}
              </Typography.Text>
              <Typography.Text type="secondary">
                成本价：{curAvgCost != null ? curAvgCost : "-"}
              </Typography.Text>
              <Typography.Text type="secondary">
                最新价：{lastClose != null ? formatPrice(lastClose) : "-"}
              </Typography.Text>
              <Typography.Text type="secondary">
                收益率：{retPct != null ? fmtPct(retPct) : "-"}
              </Typography.Text>
              {tradePnl != null && (
                <Typography.Text style={{ color: tradePnl > 0 ? "#cf1322" : tradePnl < 0 ? "#096dd9" : undefined }}>
                  本次收益：{tradePnl > 0 ? "+" : ""}{formatQuantity(tradePnl)}
                </Typography.Text>
              )}
              {curShares && curShares > 0 && form.getFieldValue("action") === "SELL" && (
                <Space size={6}>
                  <Button size="small" onClick={() => form.setFieldsValue({ shares: Number(curShares.toFixed(6)) })}>全仓</Button>
                  <Button size="small" onClick={() => form.setFieldsValue({ shares: Number((curShares / 2).toFixed(6)) })}>半仓</Button>
                  <Button size="small" onClick={() => form.setFieldsValue({ shares: Number((curShares / 4).toFixed(6)) })}>1/4 仓</Button>
                </Space>
              )}
            </Space>
          </div>

          {/* 投资框架合规性警告 */}
          {frameworkCompliance && (
            <div style={{ marginBottom: 16 }}>
              {frameworkCompliance.map((warning, index) => (
                <Alert
                  key={index}
                  type={warning.type}
                  message="投资框架提醒"
                  description={warning.message}
                  showIcon
                  style={{ marginBottom: index < frameworkCompliance.length - 1 ? 8 : 0 }}
                />
              ))}
            </div>
          )}
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
          <Form.Item label="类型" name="type" initialValue={form.getFieldValue("type") || "STOCK"} rules={[{ required: true }]}>
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
          <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
            提示：登记后会出现在标的列表中，建议尽快完善映射信息（如需要）。
          </Typography.Paragraph>
        </Form>
      </Modal>
    </Space>
  );
}
