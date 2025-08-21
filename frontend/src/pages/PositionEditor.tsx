import { useEffect, useState } from "react";
import { Button, DatePicker, Form, Input, InputNumber, message, Modal, Space, Table, Typography, Empty } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import type { PositionRaw } from "../api/types";
import { fetchPositionRaw, updatePositionOne } from "../api/hooks";

export default function PositionEditor() {
  const [data, setData] = useState<PositionRaw[]>([]);
  const [loading, setLoading] = useState(false);
  const [editKey, setEditKey] = useState<string | null>(null);
  const [form] = Form.useForm();
  const [date, setDate] = useState(dayjs());

  // 新增持仓 Modal
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm();

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

  // ✅ 页面打开时自动加载（进入路由就触发）
  useEffect(() => {
    load();
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

  const onCreate = async () => {
    try {
      const vals = await createForm.validateFields();
      await updatePositionOne({
        ts_code: vals.ts_code.trim(),
        shares: Number(vals.shares),
        avg_cost: Number(vals.avg_cost),
        date: vals.date.format("YYYY-MM-DD"),
      });
      message.success("已新增持仓");
      setCreateOpen(false);
      createForm.resetFields();
      load();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e.message || "新增失败");
    }
  };

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

      {/* 新增持仓 Modal */}
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
        <Form form={createForm} layout="vertical" initialValues={{ date: dayjs() }}>
          <Form.Item
            label="标的代码（ts_code）"
            name="ts_code"
            rules={[
              { required: true, message: "请输入 ts_code，例如 510300.SH 或 159915.SZ" },
              { pattern: /^[0-9A-Za-z.\-]+$/, message: "仅允许字母、数字、点和横线" },
            ]}
          >
            <Input placeholder="例如 510300.SH" />
          </Form.Item>
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