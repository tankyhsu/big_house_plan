import { useEffect, useMemo, useState } from "react";
import { Button, Card, Form, Input, Select, Space, Typography, message, Table, DatePicker, Row, Col } from "antd";
import { Link, useNavigate, useParams } from "react-router-dom";
import { editInstrument, fetchCategories, fetchInstrumentDetail, fetchTxnRange } from "../api/hooks";
import type { CategoryLite, InstrumentDetail } from "../api/types";
import dayjs, { Dayjs } from "dayjs";
import type { ColumnsType } from "antd/es/table";

export default function InstrumentDetail() {
  const { ts_code = "" } = useParams();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [inst, setInst] = useState<InstrumentDetail | null>(null);
  const [categories, setCategories] = useState<CategoryLite[]>([]);
  const [txnLoading, setTxnLoading] = useState(false);
  const [txns, setTxns] = useState<Array<{ date: string; action: string; shares: number; price: number | null; amount: number | null; fee: number | null }>>([]);
  const [range, setRange] = useState<[Dayjs, Dayjs]>(() => {
    const end = dayjs();
    const start = end.subtract(1, "year");
    return [start, end];
  });

  const load = async () => {
    setLoading(true);
    try {
      const [i, cats] = await Promise.all([
        fetchInstrumentDetail(ts_code),
        fetchCategories(),
      ]);
      setInst(i);
      setCategories(cats);
      form.setFieldsValue({
        ts_code: i.ts_code,
        name: i.name,
        type: i.type || "STOCK",
        category_id: i.category_id || undefined,
        active: !!i.active,
      });
    } catch (e: any) {
      message.error(e?.message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (ts_code) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ts_code]);

  const loadTxns = async () => {
    if (!ts_code) return;
    setTxnLoading(true);
    try {
      const [start, end] = range;
      const res = await fetchTxnRange(start.format("YYYYMMDD"), end.format("YYYYMMDD"), [ts_code]);
      // 仅保留该 code 的数据（后端已过滤，但稳妥起见）
      const items = (res.items || []).filter(r => r.ts_code === ts_code);
      setTxns(items);
    } catch (e: any) {
      message.error(e?.message || "交易记录加载失败");
    } finally {
      setTxnLoading(false);
    }
  };

  useEffect(() => {
    loadTxns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ts_code, range[0], range[1]]);

  const onSave = async () => {
    try {
      const vals = await form.validateFields();
      await editInstrument({
        ts_code,
        name: vals.name.trim(),
        category_id: Number(vals.category_id),
        active: !!vals.active,
        type: vals.type,
      });
      message.success("已保存标的信息");
      navigate("/positions");
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.message || "保存失败");
    }
  };

  const txnColumns: ColumnsType<any> = useMemo(() => ([
    { title: "日期", dataIndex: "date", width: 110 },
    { title: "动作", dataIndex: "action", width: 80 },
    { title: "份额", dataIndex: "shares", align: "right", width: 100, render: (v: any) => Number(v ?? 0) },
    { title: "价格", dataIndex: "price", align: "right", width: 100, render: (v: any) => v != null ? Number(v).toFixed(4) : "-" },
    { title: "金额", dataIndex: "amount", align: "right", width: 120, render: (v: any) => v != null ? Number(v).toFixed(2) : "-" },
    { title: "费用", dataIndex: "fee", align: "right", width: 100, render: (v: any) => v != null ? Number(v).toFixed(2) : "-" },
  ]), []);

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Space align="center" style={{ justifyContent: "space-between", width: "100%" }}>
        <Typography.Title level={3} style={{ margin: 0 }}>标的详情</Typography.Title>
        <Space>
          <Button onClick={() => navigate("/positions")}>返回持仓编辑</Button>
        </Space>
      </Space>
      <Row gutter={16}>
        <Col xs={24} lg={10}>
          {inst && (
            <Card loading={loading} title={`${inst.ts_code}｜${inst.name}`}>
              <Form form={form} layout="vertical">
                <Form.Item label="代码" name="ts_code">
                  <Input disabled />
                </Form.Item>
                <Form.Item label="名称" name="name" rules={[{ required: true, message: "请输入名称" }]}>
                  <Input placeholder="如 沪深300ETF / 某某基金" />
                </Form.Item>
                <Form.Item label="类型" name="type" rules={[{ required: true }]}>
                  <Select
                    options={[
                      { value: "STOCK", label: "股票" },
                      { value: "ETF", label: "ETF" },
                      { value: "FUND", label: "基金" },
                      { value: "CASH", label: "现金/货基" },
                    ]}
                  />
                </Form.Item>
                <Form.Item label="类别" name="category_id" rules={[{ required: true, message: "请选择类别" }]}>
                  <Select
                    showSearch
                    options={categories.map((c) => ({ value: c.id, label: `${c.name}${c.sub_name ? ` / ${c.sub_name}` : ""}` }))}
                    placeholder="选择类别"
                    filterOption={(input, option) => (option?.label as string).toLowerCase().includes(input.toLowerCase())}
                  />
                </Form.Item>
                <Form.Item label="启用" name="active" rules={[{ required: true }]}>
                  <Select
                    options={[
                      { value: true, label: "是" },
                      { value: false, label: "否" },
                    ]}
                  />
                </Form.Item>
                <Space>
                  <Button type="primary" onClick={onSave}>保存</Button>
                  <Link to="/positions">
                    <Button>取消</Button>
                  </Link>
                </Space>
              </Form>
            </Card>
          )}
        </Col>
        <Col xs={24} lg={14}>
          <Card title="交易记录">
            <Space style={{ marginBottom: 12 }}>
              <span>时间范围</span>
              <DatePicker.RangePicker
                value={range}
                onChange={(vals) => {
                  if (!vals || vals.length !== 2) return;
                  setRange([vals[0]!, vals[1]!]);
                }}
                allowClear={false}
              />
              <Button onClick={loadTxns}>刷新</Button>
            </Space>
            <Table
              rowKey={(r) => `${r.date}-${r.action}-${r.shares}-${r.price ?? ''}-${r.amount ?? ''}-${r.fee ?? ''}`}
              columns={txnColumns}
              dataSource={txns}
              loading={txnLoading}
              size="small"
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
