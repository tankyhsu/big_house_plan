import { useEffect, useMemo, useState } from "react";
import { Button, Card, Form, Input, Select, Space, Typography, message, Table, DatePicker, Row, Col, Tabs } from "antd";
import { Link, useNavigate, useParams } from "react-router-dom";
import { editInstrument, fetchCategories, fetchInstrumentDetail, fetchTxnRange, fetchOhlcRange, fetchPositionRaw, updatePositionOne, fetchAllSignals } from "../api/hooks";
import CandleChart from "../components/charts/CandleChart";
import SignalTags from "../components/SignalTags";
import type { CategoryLite, InstrumentDetail, SignalRow } from "../api/types";
import dayjs, { Dayjs } from "dayjs";
import type { ColumnsType } from "antd/es/table";
import { formatPrice, formatQuantity } from "../utils/format";

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
  const [posInfo, setPosInfo] = useState<{ shares: number; avg_cost: number; opening_date?: string | null } | null>(null);
  const [lastPrice, setLastPrice] = useState<{ date: string | null; close: number | null; prevClose: number | null }>({ date: null, close: null, prevClose: null });
  const [signals, setSignals] = useState<SignalRow[]>([]);
  const [signalsLoading, setSignalsLoading] = useState(false);

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

  // 加载头部所需：最近价格与前一日，和当前持仓（获取 opening_date）
  useEffect(() => {
    if (!ts_code) return;
    const end = dayjs();
    const start = end.subtract(20, "day");
    fetchOhlcRange(ts_code, start.format("YYYYMMDD"), end.format("YYYYMMDD")).then(items => {
      const valid = items.filter(it => typeof it.close === 'number');
      if (valid.length > 0) {
        const last = valid[valid.length - 1];
        const prev = valid.length > 1 ? valid[valid.length - 2] : null;
        setLastPrice({ date: last.date, close: last.close, prevClose: prev ? prev.close : null });
      } else {
        setLastPrice({ date: null, close: null, prevClose: null });
      }
    }).catch(() => setLastPrice({ date: null, close: null, prevClose: null }));

    // 获取当前持仓信息（用于编辑 opening_date）
    fetchPositionRaw(true).then(rows => {
      const r = (rows || []).find(x => x.ts_code === ts_code);
      if (r) {
        setPosInfo({ shares: Number(r.shares || 0), avg_cost: Number(r.avg_cost || 0), opening_date: r.opening_date || null });
        if (r.opening_date) {
          form.setFieldsValue({ opening_date_edit: dayjs(r.opening_date) });
        }
      } else {
        setPosInfo({ shares: 0, avg_cost: 0, opening_date: null });
      }
    }).catch(() => setPosInfo(null));

    // 获取该标的的历史信号（一个月以内）
    const loadSignals = async () => {
      if (!ts_code) return;
      setSignalsLoading(true);
      try {
        const oneMonthAgo = dayjs().subtract(1, "month").format("YYYY-MM-DD");
        const today = dayjs().format("YYYY-MM-DD");
        const signalData = await fetchAllSignals(undefined, ts_code, oneMonthAgo, today, 10);
        console.log('🔍 Loaded signals for', ts_code, ':', signalData?.length || 0, 'signals');
        setSignals(signalData || []);
      } catch (error) {
        console.error("Failed to load signals for ts_code:", error);
        setSignals([]);
      } finally {
        setSignalsLoading(false);
      }
    };
    
    loadSignals();
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
        name: inst?.name || "",
        category_id: Number(vals.category_id),
        active: !!vals.active,
        type: vals.type,
      });
      // 如提供了 opening_date_edit，则更新 position.opening_date（保持 shares/avg_cost 不变）
      if (vals.opening_date_edit) {
        const shares = posInfo?.shares ?? 0;
        const avg_cost = posInfo?.avg_cost ?? 0;
        await updatePositionOne({
          ts_code,
          shares,
          avg_cost,
          date: dayjs().format("YYYY-MM-DD"),
          opening_date: vals.opening_date_edit.format("YYYY-MM-DD"),
        });
      }
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
    { title: "价格", dataIndex: "price", align: "right", width: 100, render: (v: any) => formatPrice(Number(v)) },
    { title: "金额", dataIndex: "amount", align: "right", width: 120, render: (v: any) => formatQuantity(Number(v)) },
    { title: "费用", dataIndex: "fee", align: "right", width: 100, render: (v: any) => formatQuantity(Number(v)) },
  ]), []);

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Space direction="vertical" style={{ width: "100%" }} size={4}>
        <Space align="center" style={{ justifyContent: "space-between", width: "100%" }}>
          <Typography.Title level={3} style={{ margin: 0 }}>标的详情</Typography.Title>
          <Space>
            <Button onClick={() => navigate("/positions")}>返回持仓编辑</Button>
          </Space>
        </Space>
        {/* 详情页头部：代码｜名称｜类别｜启用状态｜最新价格与涨跌 */}
        {inst && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '6px 8px', background: '#fafafa', border: '1px solid #f0f0f0', borderRadius: 6 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 600 }}>{inst.ts_code}</span>
              <span style={{ color: '#98A2B3' }}>｜{inst.name}</span>
              <span style={{ color: '#667085' }}>
                {inst.cat_name || '-'}{inst.cat_sub ? ` / ${inst.cat_sub}` : ''}
              </span>
              {signals.length > 0 && (
                <div style={{ marginLeft: 8 }}>
                  <SignalTags signals={signals} maxDisplay={5} />
                </div>
              )}
            </div>
            <div>
              {(() => {
                const c = lastPrice.close;
                const p = lastPrice.prevClose;
                if (typeof c !== 'number') return <span style={{ color: '#98A2B3' }}>—</span>;
                let diff = (p && p > 0) ? (c - p) : 0;
                let pct = (p && p > 0) ? (diff / p) * 100 : 0;
                const isUp = diff > 0;
                const isDown = diff < 0;
                const color = isUp ? '#f04438' : (isDown ? '#12b76a' : '#667085');
                return (
                  <span style={{ fontWeight: 600, color }}>
                    {formatPrice(c)}
                    <span style={{ marginLeft: 10, fontWeight: 500 }}>
                      {diff >= 0 ? '+' : ''}{formatPrice(diff)} ({pct >= 0 ? '+' : ''}{formatQuantity(pct)}%)
                    </span>
                    {lastPrice.date && (
                      <span style={{ marginLeft: 8, color: '#98A2B3', fontWeight: 400 }}>[{lastPrice.date}]</span>
                    )}
                  </span>
                );
              })()}
            </div>
          </div>
        )}
      </Space>
      <Row gutter={16}>
        <Col xs={24}>
          {(() => {
            const t = (inst?.type || '').toUpperCase();
            const items = [
              {
                key: 'info',
                label: '基础信息',
                children: (
                  inst ? (
                    <Card loading={loading} title={`${inst.ts_code}｜${inst.name}`}>
                      <Form form={form} layout="vertical">
                {/* 名称/代码已提升到 Header 展示，这里不再编辑 */}
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
                <Form.Item label="建仓日期" name="opening_date_edit" tooltip="用于年化收益等计算的起点日期（可选）">
                  <DatePicker style={{ width: "100%" }} />
                </Form.Item>
                <Space>
                  <Button type="primary" onClick={onSave}>保存</Button>
                  <Link to="/positions">
                    <Button>取消</Button>
                  </Link>
                </Space>
                      </Form>
                    </Card>
                  ) : null
                ),
              },
            ] as any[];
            if (t !== 'CASH') {
              items.push({
                key: 'kline',
                label: 'K 线',
                children: (
                  <CandleChart 
                    tsCode={ts_code} 
                    months={6} 
                    height={320} 
                    title="K 线（可调周期）" 
                    secType={inst?.type}
                    signals={signals.map(signal => ({
                      date: signal.trade_date, // 使用信号实际发生的日期
                      price: null, // 让CandleChart从K线数据中查找对应日期的价格
                      type: signal.type,
                      message: signal.message
                    }))}
                  />
                ),
              });
            }
            items.push({
              key: 'txn',
              label: '交易记录',
              children: (
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
              ),
            });
            const defaultKey = t === 'CASH' ? 'info' : 'kline';
            return <Tabs defaultActiveKey={defaultKey} items={items} />;
          })()}
        </Col>
      </Row>
    </Space>
  );
}
