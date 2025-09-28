import { useEffect, useMemo, useState } from "react";
import { Button, Card, Form, Input, Select, Space, Typography, Table, DatePicker, Row, Col, Tabs, App, Modal } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Link, useNavigate, useParams } from "react-router-dom";
import { editInstrument, fetchCategories, fetchInstrumentDetail, fetchTxnRange, fetchOhlcRange, fetchPositionRaw, updatePositionOne, fetchAllSignals, syncPrices, fetchFundProfile } from "../api/hooks";
import CandleChart from "../components/charts/CandleChart";
import SignalTags from "../components/SignalTags";
import type { CategoryLite, InstrumentDetail, SignalRow, FundProfile } from "../api/types";
import dayjs, { Dayjs } from "dayjs";
import type { ColumnsType } from "antd/es/table";
import { formatPrice, formatQuantity } from "../utils/format";

export default function InstrumentDetail() {
  const { message } = App.useApp();
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
  const [headerSignals, setHeaderSignals] = useState<SignalRow[]>([]); // Header显示用的信号（一个月）
  const [chartSignals, setChartSignals] = useState<SignalRow[]>([]); // K线图显示用的信号（6个月）
  const [signalsLoading, setSignalsLoading] = useState(false);
  const [syncing, setSyncing] = useState(false); // 同步按钮状态
  const [chartKey, setChartKey] = useState(0); // K线图刷新key
  const [syncModalOpen, setSyncModalOpen] = useState(false); // 同步Modal状态
  const [syncForm] = Form.useForm(); // 同步日期范围表单
  const [fundProfile, setFundProfile] = useState<FundProfile | null>(null); // 基金profile数据
  const [fundProfileLoading, setFundProfileLoading] = useState(false); // 基金profile加载状态

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

      // If it's a fund, load fund profile data
      if (i.type === "FUND") {
        loadFundProfile();
      }
    } catch (e: any) {
      message.error(e?.message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  const loadFundProfile = async () => {
    if (!ts_code) return;
    setFundProfileLoading(true);
    try {
      const profile = await fetchFundProfile(ts_code);
      setFundProfile(profile);
    } catch (e: any) {
      console.error("Failed to load fund profile:", e);
      // Don't show error message, just fail silently
      setFundProfile(null);
    } finally {
      setFundProfileLoading(false);
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

    // 获取信号数据：分别拉取Header用和K线图用的信号
    const loadSignals = async () => {
      if (!ts_code) return;
      setSignalsLoading(true);
      try {
        const today = dayjs().format("YYYY-MM-DD");
        const oneMonthAgo = dayjs().subtract(1, "month").format("YYYY-MM-DD");
        const sixMonthsAgo = dayjs().subtract(6, "months").format("YYYY-MM-DD");
        
        // 并行获取两个时间周期的信号数据
        const [headerSignalData, chartSignalData] = await Promise.all([
          fetchAllSignals(undefined, ts_code, oneMonthAgo, today, 10), // Header显示用（一个月，限制10条）
          fetchAllSignals(undefined, ts_code, sixMonthsAgo, today, 100) // K线图用（六个月，限制100条）
        ]);
        
        setHeaderSignals(headerSignalData || []);
        setChartSignals(chartSignalData || []);
      } catch (error) {
        console.error("Failed to load signals for ts_code:", error);
        setHeaderSignals([]);
        setChartSignals([]);
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

  // 打开同步Modal
  const onSyncPrices = () => {
    // 设置默认日期范围：过去90天到今天
    const endDate = dayjs();
    const startDate = endDate.subtract(90, 'day');
    syncForm.setFieldsValue({
      dateRange: [startDate, endDate]
    });
    setSyncModalOpen(true);
  };

  // 执行同步操作
  const onConfirmSync = async () => {
    if (!ts_code) return;
    
    try {
      const values = await syncForm.validateFields();
      const [startDate, endDate] = values.dateRange;
      
      if (!startDate || !endDate) {
        message.error('请选择有效的日期范围');
        return;
      }

      setSyncModalOpen(false);
      setSyncing(true);
      const loadingMsg = message.loading(`正在同步 ${ts_code} 从 ${startDate.format('YYYY-MM-DD')} 到 ${endDate.format('YYYY-MM-DD')} 的价格数据，请稍候...`, 0);
      
      // 计算天数差异
      const daysDiff = endDate.diff(startDate, 'day') + 1;
      
      // 异步执行同步操作
      syncPrices({
        days: daysDiff,
        ts_codes: [ts_code],
        recalc: true
      }).then(async (result) => {
        // 清除特定的loading提示
        loadingMsg();
        setSyncing(false);
        
        if (result.total_updated === 0) {
          message.info(`${ts_code} 价格数据已是最新，无需同步`);
        } else {
          message.success(
            `${ts_code} 同步完成！处理${result.dates_processed}个日期，找到${result.total_found}条数据，更新${result.total_updated}条，跳过${result.total_skipped}条`
          );
        }
        
        // 重新加载价格数据以更新头部显示
        const end = dayjs();
        const start = end.subtract(20, "day");
        fetchOhlcRange(ts_code, start.format("YYYYMMDD"), end.format("YYYYMMDD")).then(items => {
          const valid = items.filter(it => typeof it.close === 'number');
          if (valid.length > 0) {
            const last = valid[valid.length - 1];
            const prev = valid.length > 1 ? valid[valid.length - 2] : null;
            setLastPrice({ date: last.date, close: last.close, prevClose: prev ? prev.close : null });
          }
        }).catch(() => {});
        
        // 强制刷新K线图
        setChartKey(prev => prev + 1);
        
        // 提示用户K线图已刷新
        setTimeout(() => {
          message.info('数据同步完成，K线图已刷新显示最新数据');
        }, 500);
        
      }).catch((e: any) => {
        // 清除特定的loading提示
        loadingMsg();
        setSyncing(false);
        message.error(`${ts_code} 同步失败：${e.message}`);
      });
      
    } catch (e: any) {
      if (e?.errorFields) return; // 表单校验错误
      message.error(`启动同步失败：${e?.message || "启动失败"}`);
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
          <Space align="center">
            <Button 
              type="text" 
              icon={<ArrowLeftOutlined />} 
              onClick={() => window.history.back()}
              style={{ padding: "4px 8px" }}
            />
            <Typography.Title level={3} style={{ margin: 0 }}>标的详情</Typography.Title>
          </Space>
          <Button 
            onClick={onSyncPrices} 
            loading={syncing}
            title="选择日期范围同步价格数据"
          >
            {syncing ? "同步中..." : "同步价格数据"}
          </Button>
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
              {headerSignals.length > 0 && (
                <div style={{ marginLeft: 8 }}>
                  <SignalTags signals={headerSignals} maxDisplay={5} variant="solid" />
                </div>
              )}
            </div>
            <div>
              {(() => {
                const c = lastPrice.close;
                const p = lastPrice.prevClose;
                if (typeof c !== 'number') return <span style={{ color: '#98A2B3' }}>—</span>;
                const diff = (p && p > 0) ? (c - p) : 0;
                const pct = (p && p > 0) ? (diff / p) * 100 : 0;
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
                    key={chartKey}
                    tsCode={ts_code} 
                    months={6} 
                    height={320} 
                    title="K 线（可调周期）" 
                    secType={inst?.type}
                    signals={chartSignals.map(signal => ({
                      id: signal.id,
                      date: signal.trade_date,
                      price: null,
                      type: signal.type,
                      level: signal.level,
                      message: signal.message,
                      ts_code: signal.ts_code,
                      category_id: signal.category_id,
                      scope_type: signal.scope_type,
                      created_at: signal.created_at
                    }))}
                  />
                ),
              });
            }

            // Add fund profile tab for fund instruments
            if (t === 'FUND') {
              items.push({
                key: 'fund-profile',
                label: '基金详情',
                children: (
                  <Card
                    title="基金详情"
                    loading={fundProfileLoading}
                    extra={
                      <Button size="small" onClick={loadFundProfile} disabled={fundProfileLoading}>
                        刷新
                      </Button>
                    }
                  >
                    {fundProfile ? (
                      <Tabs
                        size="small"
                        items={[
                          {
                            key: 'holdings',
                            label: '持仓变化',
                            children: (
                              <div>
                                {fundProfile.holdings.error ? (
                                  <Typography.Text type="secondary">
                                    {fundProfile.holdings.error === 'no_token' ? '需要配置TuShare Token' : `加载失败: ${fundProfile.holdings.error}`}
                                  </Typography.Text>
                                ) : fundProfile.holdings.changes.length > 0 ? (
                                  <Table
                                    size="small"
                                    dataSource={fundProfile.holdings.changes.slice(0, 20)}
                                    rowKey="stock_code"
                                    pagination={false}
                                    scroll={{ x: 800 }}
                                    columns={[
                                      {
                                        title: '股票代码',
                                        dataIndex: 'stock_code',
                                        width: 100,
                                        fixed: 'left'
                                      },
                                      {
                                        title: '股票名称',
                                        dataIndex: 'stock_name',
                                        width: 120,
                                        fixed: 'left'
                                      },
                                      {
                                        title: '当前权重(%)',
                                        dataIndex: 'current_weight',
                                        width: 100,
                                        render: (val: number) => formatQuantity(val, 2)
                                      },
                                      {
                                        title: '上期权重(%)',
                                        dataIndex: 'previous_weight',
                                        width: 100,
                                        render: (val: number) => formatQuantity(val, 2)
                                      },
                                      {
                                        title: '权重变化',
                                        dataIndex: 'weight_change',
                                        width: 100,
                                        render: (val: number) => {
                                          const color = val > 0 ? '#f04438' : val < 0 ? '#12b76a' : '#667085';
                                          return (
                                            <span style={{ color }}>
                                              {val > 0 ? '+' : ''}{formatQuantity(val, 2)}
                                            </span>
                                          );
                                        }
                                      },
                                      {
                                        title: '市值(万元)',
                                        dataIndex: 'current_mkv',
                                        width: 100,
                                        render: (val: number) => formatPrice(val / 10000, 2)
                                      },
                                      {
                                        title: '状态',
                                        key: 'status',
                                        width: 60,
                                        render: (_, record: any) => {
                                          if (record.is_new) return <span style={{ color: '#f04438' }}>新增</span>;
                                          if (record.is_increased) return <span style={{ color: '#f04438' }}>增持</span>;
                                          if (record.is_reduced) return <span style={{ color: '#12b76a' }}>减持</span>;
                                          return <span style={{ color: '#667085' }}>持平</span>;
                                        }
                                      }
                                    ]}
                                  />
                                ) : (
                                  <Typography.Text type="secondary">暂无持仓数据</Typography.Text>
                                )}
                              </div>
                            )
                          },
                          {
                            key: 'scale',
                            label: '基金规模',
                            children: (
                              <div>
                                {fundProfile.scale.error ? (
                                  <Typography.Text type="secondary">
                                    {fundProfile.scale.error === 'no_token' ? '需要配置TuShare Token' : `加载失败: ${fundProfile.scale.error}`}
                                  </Typography.Text>
                                ) : (
                                  <Row gutter={16}>
                                    <Col xs={24} md={12}>
                                      <Card size="small" title="份额数据">
                                        {fundProfile.scale.recent_shares.length > 0 ? (
                                          <Table
                                            size="small"
                                            dataSource={fundProfile.scale.recent_shares.slice(-5)}
                                            rowKey="end_date"
                                            pagination={false}
                                            columns={[
                                              {
                                                title: '日期',
                                                dataIndex: 'end_date',
                                                render: (val: string) => val ? dayjs(val).format('YYYY-MM-DD') : '-'
                                              },
                                              {
                                                title: '总份额(亿份)',
                                                dataIndex: 'total_share',
                                                render: (val: number) => val ? formatQuantity(val / 100000000, 2) : '-'
                                              },
                                              {
                                                title: '持有人数',
                                                dataIndex: 'holder_count',
                                                render: (val: number) => val ? val.toLocaleString() : '-'
                                              }
                                            ]}
                                          />
                                        ) : (
                                          <Typography.Text type="secondary">暂无份额数据</Typography.Text>
                                        )}
                                      </Card>
                                    </Col>
                                    <Col xs={24} md={12}>
                                      <Card size="small" title="净值数据">
                                        {fundProfile.scale.nav_data.length > 0 ? (
                                          <Table
                                            size="small"
                                            dataSource={fundProfile.scale.nav_data.slice(-5)}
                                            rowKey="nav_date"
                                            pagination={false}
                                            columns={[
                                              {
                                                title: '日期',
                                                dataIndex: 'nav_date',
                                                render: (val: string) => val ? dayjs(val).format('YYYY-MM-DD') : '-'
                                              },
                                              {
                                                title: '单位净值',
                                                dataIndex: 'unit_nav',
                                                render: (val: number) => val ? formatPrice(val, 4) : '-'
                                              },
                                              {
                                                title: '累计净值',
                                                dataIndex: 'accum_nav',
                                                render: (val: number) => val ? formatPrice(val, 4) : '-'
                                              }
                                            ]}
                                          />
                                        ) : (
                                          <Typography.Text type="secondary">暂无净值数据</Typography.Text>
                                        )}
                                      </Card>
                                    </Col>
                                  </Row>
                                )}
                              </div>
                            )
                          },
                          {
                            key: 'managers',
                            label: '基金经理',
                            children: (
                              <div>
                                {fundProfile.managers.error ? (
                                  <Typography.Text type="secondary">
                                    {fundProfile.managers.error === 'no_token' ? '需要配置TuShare Token' : `加载失败: ${fundProfile.managers.error}`}
                                  </Typography.Text>
                                ) : fundProfile.managers.current_managers.length > 0 ? (
                                  <div>
                                    {fundProfile.managers.current_managers.map((manager, index) => (
                                      <Card key={index} size="small" style={{ marginBottom: 12 }}>
                                        <Row gutter={16}>
                                          <Col xs={24} sm={8}>
                                            <Typography.Text strong>{manager.name}</Typography.Text>
                                            {manager.gender && (
                                              <div style={{ color: '#98A2B3', fontSize: '12px' }}>
                                                {manager.gender} {manager.nationality && `| ${manager.nationality}`}
                                              </div>
                                            )}
                                          </Col>
                                          <Col xs={24} sm={8}>
                                            {manager.education && (
                                              <div style={{ fontSize: '12px', color: '#475467' }}>
                                                <strong>学历:</strong> {manager.education}
                                              </div>
                                            )}
                                            {manager.begin_date && (
                                              <div style={{ fontSize: '12px', color: '#475467' }}>
                                                <strong>任职:</strong> {dayjs(manager.begin_date).format('YYYY-MM-DD')}
                                                {manager.end_date && ` 至 ${dayjs(manager.end_date).format('YYYY-MM-DD')}`}
                                              </div>
                                            )}
                                          </Col>
                                          <Col xs={24} sm={8}>
                                            {manager.resume && (
                                              <Typography.Paragraph
                                                style={{ fontSize: '12px', color: '#667085', margin: 0 }}
                                                ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
                                              >
                                                <strong>履历:</strong> {manager.resume}
                                              </Typography.Paragraph>
                                            )}
                                          </Col>
                                        </Row>
                                      </Card>
                                    ))}
                                  </div>
                                ) : (
                                  <Typography.Text type="secondary">暂无基金经理数据</Typography.Text>
                                )}
                              </div>
                            )
                          }
                        ]}
                      />
                    ) : (
                      <Typography.Text type="secondary">
                        {fundProfileLoading ? '加载中...' : '暂无基金详情数据'}
                      </Typography.Text>
                    )}
                  </Card>
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

      {/* 同步价格数据Modal */}
      <Modal
        title="同步价格数据"
        open={syncModalOpen}
        onOk={onConfirmSync}
        onCancel={() => setSyncModalOpen(false)}
        okText="开始同步"
        cancelText="取消"
        width={480}
      >
        <Form
          form={syncForm}
          layout="vertical"
          initialValues={{
            dateRange: [dayjs().subtract(90, 'day'), dayjs()]
          }}
        >
          <Form.Item
            label="选择同步日期范围"
            name="dateRange"
            rules={[{ required: true, message: "请选择日期范围" }]}
          >
            <DatePicker.RangePicker
              style={{ width: "100%" }}
              placeholder={["开始日期", "结束日期"]}
              allowClear={false}
            />
          </Form.Item>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            将同步选定日期范围内 <strong>{ts_code}</strong> 的价格数据，并重新计算相关投资组合快照。
          </Typography.Paragraph>
        </Form>
      </Modal>
    </Space>
  );
}
