import { useEffect, useMemo, useRef, useState } from "react";
import { AutoComplete, Button, DatePicker, Form, Input, InputNumber, message, Modal, Select, Space, Table, Typography, Empty, Divider, Alert, Switch, Popconfirm } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Tooltip } from "antd";
import { fetchIrrBatch } from "../api/hooks";
import dayjs from "dayjs";
import type { PositionRaw, InstrumentLite, CategoryLite } from "../api/types";
import { fetchPositionRaw, updatePositionOne, fetchInstruments, fetchCategories, createInstrument, deletePositionOne, cleanupZeroPositions } from "../api/hooks";

export default function PositionEditor() {
  const [data, setData] = useState<PositionRaw[]>([]);
  const [loading, setLoading] = useState(false);
  const [editKey, setEditKey] = useState<string | null>(null);
  const [form] = Form.useForm();

  // 控制显示 0 仓位
  const [includeZero, setIncludeZero] = useState(true);

  // 新增持仓 Modal
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm();

  // 标的 & 类别（用于登记新标的/下拉选择）
  const [instOpts, setInstOpts] = useState<InstrumentLite[]>([]);
  const [categories, setCategories] = useState<CategoryLite[]>([]);
  const [searching, setSearching] = useState(false);
  const searchTimer = useRef<number | null>(null);

  const load = async (incZero = includeZero) => {
    setLoading(true);
    try {
      const rows = await fetchPositionRaw(incZero);
      setData(rows);
    } catch (e: any) {
      message.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  // 页面打开时加载（持仓 + 下拉）
  useEffect(() => {
    load(true);
    fetchInstruments().then(setInstOpts).catch(() => {});
    fetchCategories().then(setCategories).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // includeZero 变化时刷新
  useEffect(() => {
    load(includeZero);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeZero]);

  const isEditing = (r: PositionRaw) => editKey === r.ts_code;

// 1) 顶部 state：删除全局 date
// const [date, setDate] = useState(dayjs());   // <- 移除

  // 2) 编辑进入时，预填表单含 date
  const edit = (r: PositionRaw) => {
    form.setFieldsValue({
      shares: r.shares,
      avg_cost: r.avg_cost,
      // 若有 last_update 则用它，否则默认今天
      date: r.last_update ? dayjs(r.last_update) : dayjs(),
    });
    setEditKey(r.ts_code);
  };

  const cancel = () => setEditKey(null);

  const save = async (r: PositionRaw) => {
    try {
      const vals = await form.validateFields();
      const effDate = vals.date ? vals.date.format("YYYY-MM-DD") : dayjs().format("YYYY-MM-DD");
      await updatePositionOne({
        ts_code: r.ts_code,
        shares: typeof vals.shares === "number" ? vals.shares : undefined,
        avg_cost: typeof vals.avg_cost === "number" ? vals.avg_cost : undefined,
        date: effDate,
      });
      message.success(`已更新（生效日：${effDate}）`);
      setEditKey(null);
      load();
    } catch (e: any) {
      if (e?.errorFields) return; // 表单校验错误
      message.error(e.message || "更新失败");
    }
  };

  // ====== 新增持仓（含登记新标的）原有逻辑（略） ======
  // === 下拉选项：将 instrument 列表映射为 AutoComplete options ===
  const options = useMemo(
    () =>
      instOpts.map((i) => ({
        value: i.ts_code,
        label: `${i.ts_code}｜${i.name || ""}${i.cat_name ? `（${i.cat_name}${i.cat_sub ? `/${i.cat_sub}` : ""}）` : ""}`,
      })),
    [instOpts]
  );

  // 搜索节流：输入时动态刷新列表（可直接输入新代码）
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

  // 判断是否为新代码（不在现有 instrument 列表中）
  const isNewInstrument = () => {
    const v = createForm.getFieldValue("ts_code");
    if (!v) return false;
    const code = typeof v === "string" ? v : v?.value;
    return !instOpts.some((i) => i.ts_code === code);
  };

  // 提交“新增持仓”（如遇新代码，先登记 instrument 再写 position）
  const onCreate = async () => {
    try {
      const vals = await createForm.validateFields();
      const ts_code: string = (typeof vals.ts_code === "string" ? vals.ts_code : vals.ts_code?.value)?.trim();
      if (!ts_code) throw new Error("请输入/选择 ts_code");

      if (isNewInstrument()) {
        // 校验并创建 instrument
        await createForm.validateFields(["inst_name", "inst_type", "inst_category_id", "inst_active"]);
        await createInstrument({
          ts_code,
          name: vals.inst_name.trim(),
          category_id: Number(vals.inst_category_id),
          active: !!vals.inst_active,
          type: vals.inst_type,
        });
      }

      // 写入/更新底仓
      await updatePositionOne({
        ts_code,
        shares: Number(vals.shares),
        avg_cost: Number(vals.avg_cost),
        date: vals.date.format("YYYY-MM-DD"),
      });

      message.success(isNewInstrument() ? "已登记新标的并新增持仓" : "已新增持仓");
      setCreateOpen(false);
      createForm.resetFields();
      // 刷新：让新标的立即出现在下拉 & 列表
      fetchInstruments(ts_code).then(setInstOpts).catch(() => {});
      load();
    } catch (e: any) {
      if (e?.errorFields) return; // 表单校验错误
      message.error(e.message || "新增失败");
    }
  };

  // 只展示与“删除 0 仓位/批量清理/开关”的增量
  
  // 删除单条 0 仓位
  const onDeleteZero = async (ts_code: string) => {
    try {
      await deletePositionOne(ts_code, dayjs().format("YYYYMMDD"));
      message.success("已删除 0 仓位");
      load();
    } catch (e: any) {
      message.error(e.message || "删除失败");
    }
  };

  // 批量清理 0 仓位
  const onCleanupZero = async () => {
    try {
      const res = await cleanupZeroPositions(dayjs().format("YYYYMMDD"));
      message.success(`已清理 ${res.deleted} 条 0 仓位`);
      load();
    } catch (e: any) {
      message.error(e.message || "清理失败");
    }
  };

  const [irrMap, setIrrMap] = useState<Record<string, number | null>>({});

    // 页面打开时批量拉一次（以今天为估值日；也可以用你页面上的“查看日期”）
  useEffect(() => {
    const ymd = dayjs().format("YYYYMMDD");
    fetchIrrBatch(ymd).then(rows => {
      const m: Record<string, number | null> = {};
      rows.forEach(r => { m[r.ts_code] = r.annualized_mwr; });
      setIrrMap(m);
    }).catch(()=>{});
  }, []);

  // 列定义：当 shares===0 时显示删除按钮
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
          (record.avg_cost ?? 0).toFixed(4)
        ),
    },
    {
      title: "最后更新",
      dataIndex: "last_update",
      width: 100,
      render: (_: any, record) =>
        isEditing(record) ? (
          <Form.Item
            name="date"
            style={{ margin: 0 }}
            rules={[{ required: true, message: "请选择生效日期" }]}
          >
            <DatePicker
              allowClear={false}
              // 可选：禁止选择未来日期
              disabledDate={(d) => d && d.isAfter(dayjs(), "day")}
            />
          </Form.Item>
        ) : (
          record.last_update || "-"
        ),
    },
    {
      title: "建仓时间",
      dataIndex: "opening_date",
      width: 100,
      render: (_: any, record) =>
        isEditing(record) ? (
          <Form.Item
            name="date"
            style={{ margin: 0 }}
            rules={[{ required: true, message: "请选择建仓日期" }]}
          >
            <DatePicker
              allowClear={false}
              // 可选：禁止选择未来日期
              disabledDate={(d) => d && d.isAfter(dayjs(), "day")}
            />
          </Form.Item>
        ) : (
          record.opening_date || "-"
        ),
    },
    {
      title: "年化收益（自建仓）",
      dataIndex: "irr",
      align: "right",
      width: 80,
      render: (_: any, r: PositionRaw) => {
        const irr = irrMap[r.ts_code];
        return (
          <Tooltip title="资金加权收益率（XIRR），考虑加/减仓与分红；以今天为估值日">
            {typeof irr === "number" ? `${(irr * 100).toFixed(2)}%` : "—"}
          </Tooltip>
        );
      },
    },
    {
      title: "操作",
      dataIndex: "actions",
      align: "center",
      width: 180,
      render: (_: any, record) => {
        const editable = isEditing(record);
        const isZero = Number(record.shares) === 0;
        return editable ? (
          <Space>
            <Button type="primary" onClick={() => save(record)}>保存</Button>
            <Button onClick={cancel}>取消</Button>
          </Space>
        ) : (
          <Space>
            <Button onClick={() => edit(record)}>编辑</Button>
            {isZero && (
              <Popconfirm title="确定删除这条 0 仓位吗？" onConfirm={() => onDeleteZero(record.ts_code)}>
                <Button danger>删除</Button>
              </Popconfirm>
            )}
          </Space>
        );
      },
    },
  ];

  // ====== 新增持仓 Modal 省略：沿用你现有实现 ======

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Typography.Title level={3} style={{ margin: 0 }}>持仓编辑</Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
        用于初始化或纠错。日常变动请使用“交易”功能，便于复盘与审计。
      </Typography.Paragraph>

      {/* 顶部操作条：刷新 + 新增持仓 + 开关 + 批量清理 */}
      <Space wrap>
        <Button onClick={() => load()}>刷新</Button>
        <Button type="primary" onClick={() => setCreateOpen(true)}>新增持仓</Button>
        <Space align="center">
          <span>显示 0 仓位</span>
          <Switch checked={includeZero} onChange={setIncludeZero} />
        </Space>
        <Popconfirm title="确定清理所有 0 仓位吗？" onConfirm={onCleanupZero}>
          <Button danger>清理 0 仓位</Button>
        </Popconfirm>
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
              <Empty description="暂无持仓数据" />
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
        <Form
          form={createForm}
          layout="vertical"
          initialValues={{ date: dayjs(), inst_type: "STOCK", inst_active: true }}
        >
          <Form.Item
            label="标的代码（可下拉选择或直接输入新代码）"
            name="ts_code"
            rules={[
              { required: true, message: "请输入 ts_code，例如 510300.SH 或 基金代码" },
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
                    { value: "STOCK", label: "股票（交易所收盘价）" },
                    { value: "ETF", label: "ETF（交易所收盘价）" },
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
          <Form.Item label="生效日期" name="date" rules={[{ required: true }]}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}