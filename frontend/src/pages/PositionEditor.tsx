import { useEffect, useMemo, useRef, useState } from "react";
import { AutoComplete, Button, DatePicker, Form, Input, InputNumber, message, Modal, Select, Space, Table, Typography, Empty, Divider, Alert } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import type { PositionRaw, InstrumentLite, CategoryLite } from "../api/types";
import { fetchPositionRaw, updatePositionOne, fetchInstruments, fetchCategories, createInstrument } from "../api/hooks";

export default function PositionEditor() {
  const [data, setData] = useState<PositionRaw[]>([]);
  const [loading, setLoading] = useState(false);
  const [editKey, setEditKey] = useState<string | null>(null);
  const [form] = Form.useForm();
  const [date, setDate] = useState(dayjs());

  // 新增持仓 Modal
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm();

  // 标的 & 类别（用于登记新标的/下拉选择）
  const [instOpts, setInstOpts] = useState<InstrumentLite[]>([]);
  const [categories, setCategories] = useState<CategoryLite[]>([]);
  const [searching, setSearching] = useState(false);
  const searchTimer = useRef<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const rows = await fetchPositionRaw();
      setData(rows);
    } catch (e: any) {
      message.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  // ✅ 页面打开时自动加载（持仓 + 下拉数据）
  useEffect(() => {
    load();
    fetchInstruments().then(setInstOpts).catch(() => {});
    fetchCategories().then(setCategories).catch(() => {});
  }, []);

  const isEditing = (r: PositionRaw) => editKey === r.ts_code;

  const edit = (r: PositionRaw) => {
    form.setFieldsValue({ shares: r.shares, avg_cost: r.avg_cost });
    setEditKey(r.ts_code);
  };
  const cancel = () => setEditKey(null);

  const save = async (r: PositionRaw) => {
    try {
      const vals = await form.validateFields();
      await updatePositionOne({
        ts_code: r.ts_code,
        shares: typeof vals.shares === "number" ? vals.shares : undefined,
        avg_cost: typeof vals.avg_cost === "number" ? vals.avg_cost : undefined,
        date: date.format("YYYY-MM-DD"),
      });
      message.success("已更新");
      setEditKey(null);
      load();
    } catch (e: any) {
      if (e?.errorFields) return; // 表单校验错误
      message.error(e.message || "更新失败");
    }
  };

  // =============== 新增持仓（含登记新标的） ===============
  // AutoComplete options
  const options = useMemo(
    () =>
      instOpts.map((i) => ({
        value: i.ts_code,
        label: `${i.ts_code}｜${i.name || ""}${i.cat_name ? `（${i.cat_name}${i.cat_sub ? `/${i.cat_sub}` : ""}）` : ""}`,
      })),
    [instOpts]
  );

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

  // 判断新标的：根据当前选值是否存在于 instOpts
  const isNewInstrument = () => {
    const v = createForm.getFieldValue("ts_code");
    if (!v) return false;
    return !instOpts.some(i => i.ts_code === (typeof v === "string" ? v : v?.value));
  };

  const onCreate = async () => {
    try {
      const vals = await createForm.validateFields();
      const ts_code: string = (typeof vals.ts_code === "string" ? vals.ts_code : vals.ts_code?.value)?.trim();
      if (!ts_code) throw new Error("请输入/选择 ts_code");

      // 如果是新标的，校验并先创建 instrument
      if (isNewInstrument()) {
        // 校验登记区字段
        await createForm.validateFields(["inst_name", "inst_type", "inst_category_id", "inst_active"]);
        await createInstrument({
          ts_code,
          name: vals.inst_name.trim(),
          category_id: Number(vals.inst_category_id),
          active: !!vals.inst_active,
          type: vals.inst_type,
        });
      }

      // 接着创建/更新底仓
      await updatePositionOne({
        ts_code,
        shares: Number(vals.shares),
        avg_cost: Number(vals.avg_cost),
        date: vals.date.format("YYYY-MM-DD"),
      });

      message.success(isNewInstrument() ? "已登记新标的并新增持仓" : "已新增持仓");
      setCreateOpen(false);
      createForm.resetFields();
      // 刷新标的列表（让刚创建的出现在下拉）
      fetchInstruments(ts_code).then(setInstOpts).catch(()=>{});
      load();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e.message || "新增失败");
    }
  };

  // 列定义
  const columns: ColumnsType<PositionRaw> = [
    {
      title: "类别",
      dataIndex: "cat_name",
      render: (t, r) => (
        <>
          {t}
          {r.cat_sub ? <span style={{ color: "#98A2B3" }}> / {r.cat_sub}</span> : null}
        </>
      ),
    },
    {
      title: "代码/名称",
      dataIndex: "ts_code",
      render: (t, r) => (
        <div>
          <strong>{t}</strong>
          <div style={{ color: "#667085" }}>{r.inst_name}</div>
        </div>
      ),
    },
    {
      title: "持仓份额",
      dataIndex: "shares",
      align: "right",
      render: (_, record) =>
        isEditing(record) ? (
          <Form.Item
            name="shares"
            rules={[
              { required: true, message: "请输入份额" },
              { type: "number", min: 0, message: "份额必须 ≥ 0" },
            ]}
            style={{ margin: 0 }}
          >
            <InputNumber controls={false} precision={2} style={{ width: 120 }} />
          </Form.Item>
        ) : (
          record.shares
        ),
    },
    {
      title: "持仓均价",
      dataIndex: "avg_cost",
      align: "right",
      render: (_, record) =>
        isEditing(record) ? (
          <Form.Item
            name="avg_cost"
            rules={[
              { required: true, message: "请输入均价" },
              { type: "number", min: 0, message: "均价必须 ≥ 0" },
            ]}
            style={{ margin: 0 }}
          >
            <InputNumber controls={false} precision={4} style={{ width: 120 }} />
          </Form.Item>
        ) : (
          record.avg_cost?.toFixed(4)
        ),
    },
    { title: "最后更新", dataIndex: "last_update", width: 140 },
    {
      title: "操作",
      dataIndex: "actions",
      align: "center",
      width: 220,
      render: (_, record) => {
        const editable = isEditing(record);
        return editable ? (
          <Space>
            <Button type="primary" onClick={() => save(record)}>
              保存
            </Button>
            <Button onClick={cancel}>取消</Button>
          </Space>
        ) : (
          <Space>
            <DatePicker value={date} onChange={(d) => d && setDate(d)} allowClear={false} size="small" />
            <Button onClick={() => edit(record)}>编辑</Button>
          </Space>
        );
      },
    },
  ];

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Typography.Title level={3} style={{ margin: 0 }}>
        持仓编辑
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
        用于初始化或纠错。日常变动请使用“交易”功能，便于复盘与审计。
      </Typography.Paragraph>

      {/* 顶部操作条：刷新 + 新增持仓 */}
      <Space>
        <Button onClick={load}>刷新</Button>
        <Button type="primary" onClick={() => setCreateOpen(true)}>
          新增持仓
        </Button>
      </Space>

      <Form form={form} component={false}>
        <Table
          size="small"
          rowKey={(r) => r.ts_code}
          columns={columns}
          dataSource={data}
          loading={loading}
          pagination={{ pageSize: 15 }}
          locale={{
            emptyText: (
              <Empty
                description={
                  <Space direction="vertical">
                    <div>暂无持仓数据</div>
                    <Button type="primary" onClick={load}>
                      加载当前持仓
                    </Button>
                  </Space>
                }
              />
            ),
          }}
        />
      </Form>

      {/* 新增持仓 Modal（内置“登记新标的”区块） */}
      <Modal
        title="新增持仓"
        open={createOpen}
        onOk={onCreate}
        onCancel={() => {
          setCreateOpen(false);
          createForm.resetFields();
        }}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={createForm} layout="vertical" initialValues={{ date: dayjs(), inst_type: "STOCK", inst_active: true }}>
          <Form.Item
            label="标的代码（可下拉选择或直接输入新代码）"
            name="ts_code"
            rules={[
              { required: true, message: "请输入 ts_code，例如 510300.SH 或 110011" },
              { pattern: /^[0-9A-Za-z.\-]+$/, message: "仅允许字母、数字、点和横线" },
            ]}
          >
            <AutoComplete
              options={options}
              onSearch={onSearch}
              placeholder="例如 510300.SH 或 基金代码"
              allowClear
              notFoundContent={searching ? "搜索中..." : "可直接输入新代码"}
              filterOption={(inputValue, option) =>
                (option?.value as string)?.toUpperCase().includes(inputValue.toUpperCase()) ||
                (option?.label as string)?.toUpperCase().includes(inputValue.toUpperCase())
              }
            />
          </Form.Item>

          {/* 当 ts_code 不在现有列表时，展示“登记新标的”扩展表单 */}
          {isNewInstrument() && (
            <>
              <Alert type="info" showIcon style={{ marginBottom: 8 }} message="检测到新代码，需先登记标的基础信息" />
              <Form.Item label="名称" name="inst_name" rules={[{ required: true, message: "请输入名称" }]}>
                <Input placeholder="如 沪深300ETF / 某某基金" />
              </Form.Item>
              <Form.Item label="类型" name="inst_type" rules={[{ required: true }]}>
                <Select
                  options={[
                    { value: "STOCK", label: "股票/ETF（交易所收盘价）" },
                    { value: "FUND", label: "基金（净值）" },
                    { value: "CASH", label: "现金/货基（不拉行情）" },
                  ]}
                />
              </Form.Item>
              <Form.Item label="类别" name="inst_category_id" rules={[{ required: true, message: "请选择类别" }]}>
                <Select
                  showSearch
                  options={categories.map((c) => ({
                    value: c.id,
                    label: `${c.name}${c.sub_name ? ` / ${c.sub_name}` : ""}`,
                  }))}
                  placeholder="选择类别"
                  filterOption={(input, option) => (option?.label as string).toLowerCase().includes(input.toLowerCase())}
                />
              </Form.Item>
              <Form.Item label="启用" name="inst_active" initialValue={true}>
                <Select
                  options={[
                    { value: true, label: "是" },
                    { value: false, label: "否" },
                  ]}
                />
              </Form.Item>
              <Divider style={{ margin: "8px 0 12px" }} />
            </>
          )}

          <Form.Item
            label="持仓份额"
            name="shares"
            rules={[{ required: true, message: "请输入份额" }, { type: "number", min: 0 }]}
          >
            <InputNumber controls={false} precision={2} style={{ width: "100%" }} placeholder="如 1000" />
          </Form.Item>
          <Form.Item
            label="持仓均价"
            name="avg_cost"
            rules={[{ required: true, message: "请输入均价" }, { type: "number", min: 0 }]}
          >
            <InputNumber controls={false} precision={4} style={{ width: "100%" }} placeholder="如 4.5000" />
          </Form.Item>
          <Form.Item label="日期" name="date" rules={[{ required: true }]}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}