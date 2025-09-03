import { useEffect, useMemo, useRef, useState } from "react";
import { AutoComplete, Button, DatePicker, Form, Input, InputNumber, message, Modal, Select, Space, Table, Typography, Empty, Divider, Alert, Switch, Popconfirm } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Tooltip } from "antd";
import { fetchIrrBatch, fetchAllSignals } from "../api/hooks";
import dayjs from "dayjs";
import { Link } from "react-router-dom";
import type { PositionRaw, InstrumentLite, CategoryLite, SignalRow } from "../api/types";
import { fetchPositionRaw, updatePositionOne, fetchInstruments, fetchCategories, createInstrument, cleanupZeroPositions, lookupInstrument } from "../api/hooks";
import SignalTags from "../components/SignalTags";
import { formatPrice, fmtPct } from "../utils/format";
import { getSignalsForTsCode } from "../hooks/useRecentSignals";

export default function PositionEditor() {
  const [data, setData] = useState<PositionRaw[]>([]);
  const [loading, setLoading] = useState(false);
  const [signals, setSignals] = useState<SignalRow[]>([]);
  // 行内编辑已移除，统一使用弹窗编辑

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
  // 完整 ts_code 格式：6 位数字 + 点 + 2~3 位字母（如 510300.SH / 110011.OF）
  const TS_CODE_FULL_RE = /^\d{6}\.[A-Za-z]{2,3}$/i;

  // 过滤：类别 + 全局搜索
  const [catFilter, setCatFilter] = useState<number | undefined>(undefined);
  const [globalQuery, setGlobalQuery] = useState<string>("");

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

  // 加载最近一个月的信号数据
  useEffect(() => {
    const loadSignals = async () => {
      try {
        const oneMonthAgo = dayjs().subtract(1, "month").format("YYYY-MM-DD");
        const today = dayjs().format("YYYY-MM-DD");
        const signalData = await fetchAllSignals(undefined, undefined, oneMonthAgo, today, 200);
        console.log('📊 PositionEditor loaded signals:', signalData?.length || 0, 'signals');
        setSignals(signalData || []);
      } catch (error) {
        console.error("Failed to load signals:", error);
        setSignals([]);
      }
    };
    loadSignals();
  }, []);


  // includeZero 变化时刷新
  useEffect(() => {
    load(includeZero);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeZero]);

  // 1) 顶部 state：删除全局 date（保留为注释）
  // const [date, setDate] = useState(dayjs());

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

  // 判断是否为新代码（不在现有 instrument 列表中）。
  // 仅当输入满足完整 ts_code 格式时才进行判断，避免在未输入完整前误判。
  const isNewInstrument = () => {
    const v = createForm.getFieldValue("ts_code");
    if (!v) return false;
    const code = (typeof v === "string" ? v : v?.value)?.trim();
    if (!TS_CODE_FULL_RE.test(code || "")) return false;
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

  // （编辑功能已迁移至详情页，保留新增能力）

  // 新代码时：自动从 TuShare 查询基础信息与建仓日的价格/净值（如提供）
  const [refPriceDate, setRefPriceDate] = useState<string | null>(null);
  useEffect(() => {
    const tsVal = createForm.getFieldValue("ts_code");
    const code: string | undefined = (typeof tsVal === "string" ? tsVal : tsVal?.value)?.trim();
    if (!code) return;
    if (!isNewInstrument()) return; // 仅新代码时触发
    // 未形成完整 ts_code 时，不触发 TuShare 查询，避免无效请求
    if (!TS_CODE_FULL_RE.test(code)) { setRefPriceDate(null); return; }
    const dt = createForm.getFieldValue("date");
    const ymd: string | undefined = dt ? dt.format("YYYYMMDD") : undefined;
    lookupInstrument(code, ymd).then(info => {
      // 覆盖名称：当用户未手动编辑“名称”时，总是使用查到的名称（即使已有旧值）
      if (info?.name && !createForm.isFieldTouched("inst_name")) {
        createForm.setFieldsValue({ inst_name: info.name });
      }
      // 如果从 TuShare 成功识别出类型，且用户尚未手动修改“类型”，则自动选择
      if (info?.type && !createForm.isFieldTouched("inst_type")) {
        createForm.setFieldsValue({ inst_type: info.type });
      }
      // 仅在用户未手动编辑过均价，且表单中当前未填值时，才回填参考价
      if (info?.price?.close && !createForm.isFieldTouched("avg_cost") && !createForm.getFieldValue("avg_cost")) {
        createForm.setFieldsValue({ avg_cost: Number(info.price.close) });
      }
      setRefPriceDate(info?.price?.trade_date || null);
    }).catch(() => { setRefPriceDate(null); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [createForm.getFieldValue("ts_code"), createForm.getFieldValue("date")]);

  // 只展示与“批量清理/开关”的增量

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

  const [irrMap, setIrrMap] = useState<Record<string, { val: number | null; reason?: string }>>({});

    // 页面打开时批量拉一次（以今天为估值日；也可以用你页面上的“查看日期”）
  useEffect(() => {
    const ymd = dayjs().format("YYYYMMDD");
    fetchIrrBatch(ymd).then(rows => {
      const m: Record<string, { val: number | null; reason?: string }> = {};
      rows.forEach(r => {
        m[r.ts_code] = { val: r.annualized_mwr, reason: r.irr_reason || undefined };
      });
      setIrrMap(m);
    }).catch(()=>{});
  }, []);

  // 列定义：当 shares===0 时显示删除按钮
  const columns: ColumnsType<PositionRaw> = [
    {
      title: "类别",
      dataIndex: "cat_name",
      sorter: (a, b) => `${a.cat_name || ''}/${a.cat_sub || ''}`.localeCompare(`${b.cat_name || ''}/${b.cat_sub || ''}`),
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
      sorter: (a, b) => (a.ts_code || '').localeCompare(b.ts_code || ''),
      render: (t, r) => {
        const tsSignals = getSignalsForTsCode(signals, t);
        return (
          <div>
            <Link to={`/instrument/${encodeURIComponent(t)}`}>
              <strong>{t}</strong>
              <div style={{ color: "#667085", display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span>{r.inst_name}</span>
                {tsSignals.length > 0 && (
                  <SignalTags signals={tsSignals} maxDisplay={3} />
                )}
              </div>
            </Link>
          </div>
        );
      },
    },
    {
      title: "持仓份额",
      dataIndex: "shares",
      align: "right",
      sorter: (a, b) => Number(a.shares || 0) - Number(b.shares || 0),
      render: (_, record) => record.shares,
    },
    {
      title: "持仓均价",
      dataIndex: "avg_cost",
      align: "right",
      sorter: (a, b) => Number(a.avg_cost || 0) - Number(b.avg_cost || 0),
      render: (_, record) => formatPrice(record.avg_cost ?? 0),
    },
    {
      title: "最后更新",
      dataIndex: "last_update",
      width: 100,
      sorter: (a, b) => (a.last_update || '').localeCompare(b.last_update || ''),
      render: (_: any, record) => record.last_update || "-",
    },
    {
      title: "建仓时间",
      dataIndex: "opening_date",
      width: 100,
      sorter: (a, b) => (a.opening_date || '').localeCompare(b.opening_date || ''),
      render: (_: any, record) => record.opening_date || "-",
    },
    {
      title: "年化收益（自建仓）",
      dataIndex: "irr",
      align: "right",
      width: 180,
      sorter: (a, b) => {
        const ia = irrMap[a.ts_code]?.val;
        const ib = irrMap[b.ts_code]?.val;
        const va = typeof ia === 'number' ? ia : Number.NEGATIVE_INFINITY;
        const vb = typeof ib === 'number' ? ib : Number.NEGATIVE_INFINITY;
        return va - vb;
      },
      render: (_: any, r: PositionRaw) => {
        const item = irrMap[r.ts_code];
        const irr = item?.val;
        const reason = item?.reason;
        return (
          <>
            {typeof irr === "number" ? fmtPct(irr) : "—"}
            {reason === "fallback_opening_date" && (
              <Tooltip
                title="近似估算：无交易流水，按“建仓日→估值日”和当前收益率推算年化（非资金加权 IRR）。"
              >
                <sup style={{ marginLeft: 2, color: "#ff3c00ff", cursor: "help" }}>*</sup>
              </Tooltip>
            )}
          </>
        );
      },
    },
  ];

  // ====== 新增持仓 Modal 省略：沿用你现有实现 ======

  // 应用过滤后的数据
  const filteredData = useMemo(() => {
    const q = (globalQuery || "").trim().toLowerCase();
    return (data || []).filter((r) => {
      const okCat = catFilter ? Number(r.category_id) === Number(catFilter) : true;
      if (!q) return okCat;
      const hay = [
        r.ts_code || "",
        r.inst_name || "",
        r.cat_name || "",
        r.cat_sub || "",
      ].join(" ").toLowerCase();
      return okCat && hay.includes(q);
    });
  }, [data, catFilter, globalQuery]);

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Typography.Title level={3} style={{ margin: 0 }}>持仓编辑</Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
        用于初始化或纠错。日常变动请使用“交易”功能，便于复盘与审计。
      </Typography.Paragraph>

      {/* 顶部操作条：刷新 + 新增持仓 + 开关 + 批量清理 + 过滤 */}
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
        <Divider type="vertical" />
        <Space align="center" wrap>
          <span>类别</span>
          <Select
            style={{ minWidth: 220 }}
            placeholder="全部类别"
            allowClear
            value={catFilter}
            onChange={(v) => setCatFilter(v)}
            options={categories.map((c) => ({ value: c.id, label: `${c.name}${c.sub_name ? ` / ${c.sub_name}` : ""}` }))}
          />
          <Input
            style={{ width: 260 }}
            placeholder="搜索 代码/名称/类别"
            allowClear
            value={globalQuery}
            onChange={(e) => setGlobalQuery(e.target.value)}
          />
        </Space>
      </Space>

      <Table
        size="small"
        rowKey={(r) => r.ts_code}
        columns={columns}
        dataSource={filteredData}
        loading={loading}
        pagination={{ pageSize: 15 }}
        locale={{
          emptyText: (
            <Empty description="暂无持仓数据" />
          ),
        }}
      />

      {/* 新增持仓 Modal（内置“登记新标的”区块） */}
      <Modal
        title={"新增持仓"}
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
              disabled={false}
              notFoundContent={searching ? "搜索中..." : "可直接输入新代码"}
              filterOption={(inputValue, option) =>
                (option?.value as string)?.toUpperCase().includes(inputValue.toUpperCase()) ||
                (option?.label as string)?.toUpperCase().includes(inputValue.toUpperCase())
              }
            />
          </Form.Item>

          {/* 新增模式下展示“登记新标的”扩展表单 */}
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
          {refPriceDate && (
            <Typography.Text type="secondary" style={{ marginTop: -8, display: "block" }}>
              参考价日期：{refPriceDate}
            </Typography.Text>
          )}
          <Form.Item label="生效日期" name="date" rules={[{ required: true }]}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          {/* 建仓日期仅在详情页可编辑，这里不提供 */}
        </Form>
      </Modal>
    </Space>
  );
}
