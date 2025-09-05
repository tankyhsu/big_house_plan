import { useEffect, useState, useMemo } from "react";
import { Select, Space, Table, Tag, Typography, Card, Row, Col, Statistic, Button, DatePicker, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs, { Dayjs } from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";

dayjs.extend(relativeTime);
import { fetchAllSignals, generateStructureSignals, rebuildStructureSignals } from "../api/hooks";
import client from "../api/client";
import type { SignalRow, SignalType, SignalLevel } from "../api/types";
import { ReloadOutlined, AlertOutlined, PlusOutlined, HistoryOutlined, FunctionOutlined } from "@ant-design/icons";
import { SIGNAL_CONFIG, LEVEL_CONFIG } from "../utils/signalConfig";
import CreateSignalModal from "../components/CreateSignalModal";
import InstrumentDisplay from "../components/InstrumentDisplay";

export default function SignalsPage() {
  const [signals, setSignals] = useState<SignalRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedType, setSelectedType] = useState<string>("ALL");
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>(() => {
    const end = dayjs();
    const start = end.subtract(1, "month");
    return [start, end];
  });
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [rebuildLoading, setRebuildLoading] = useState(false);
  const [structureLoading, setStructureLoading] = useState(false);
  const [rebuildStructureLoading, setRebuildStructureLoading] = useState(false);

  const loadSignals = async () => {
    setLoading(true);
    try {
      const [start, end] = dateRange;
      const data = await fetchAllSignals(
        selectedType === "ALL" ? undefined : selectedType, 
        undefined,
        start.format("YYYY-MM-DD"),
        end.format("YYYY-MM-DD"),
        200
      );
      setSignals(data);
    } catch (error) {
      console.error("Failed to load signals:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleRebuildHistorical = async () => {
    setRebuildLoading(true);
    try {
      const { data } = await client.post("/api/signal/rebuild-historical");
      message.success(`历史信号重建完成：生成${data.generated_signals}个信号，时间范围：${data.date_range}`);
      await loadSignals(); // 重新加载信号列表
    } catch (error: any) {
      message.error(error?.response?.data?.detail || "重建历史信号失败");
    } finally {
      setRebuildLoading(false);
    }
  };

  const handleGenerateStructureSignals = async () => {
    setStructureLoading(true);
    try {
      const today = dayjs().format("YYYY-MM-DD");
      const response = await generateStructureSignals(today);
      message.success(`结构信号生成完成：${response.message}`);
      await loadSignals(); // 重新加载信号列表
    } catch (error: any) {
      message.error(error?.message || "生成结构信号失败");
    } finally {
      setStructureLoading(false);
    }
  };

  const handleRebuildStructureSignals = async () => {
    setRebuildStructureLoading(true);
    try {
      const response = await rebuildStructureSignals();
      message.success(`结构信号重建完成：${response.message}`);
      await loadSignals(); // 重新加载信号列表
    } catch (error: any) {
      message.error(error?.message || "重建结构信号失败");
    } finally {
      setRebuildStructureLoading(false);
    }
  };

  useEffect(() => {
    loadSignals();
  }, [selectedType, dateRange]);

  // 信号统计
  const signalStats = useMemo(() => {
    const stats: Record<SignalType, number> = {
      UNDERWEIGHT: 0,
      BUY_SIGNAL: 0,
      SELL_SIGNAL: 0,
      BUY_STRUCTURE: 0,
      SELL_STRUCTURE: 0,
      REBALANCE: 0,
      RISK_ALERT: 0,
      MOMENTUM: 0,
      MEAN_REVERT: 0,
      BULLISH: 0,
      BEARISH: 0,
    };

    const levelStats: Record<SignalLevel, number> = {
      HIGH: 0,
      MEDIUM: 0,
      LOW: 0,
      INFO: 0,
    };

    signals.forEach((signal) => {
      stats[signal.type] = (stats[signal.type] || 0) + 1;
      levelStats[signal.level] = (levelStats[signal.level] || 0) + 1;
    });

    return { typeStats: stats, levelStats, total: signals.length };
  }, [signals]);

  const columns: ColumnsType<SignalRow> = [
    {
      title: "级别",
      dataIndex: "level",
      width: 80,
      render: (level: SignalLevel) => (
        <Tag color={LEVEL_CONFIG[level]?.color || "default"}>
          {LEVEL_CONFIG[level]?.label || level}
        </Tag>
      ),
    },
    {
      title: "类型",
      dataIndex: "type",
      width: 100,
      render: (type: SignalType) => (
        <Tag color={SIGNAL_CONFIG[type]?.color || "default"}>
          {SIGNAL_CONFIG[type]?.label || type}
        </Tag>
      ),
    },
    {
      title: "标的",
      dataIndex: "ts_code",
      width: 200,
      render: (ts_code, record) => (
        <InstrumentDisplay
          data={{
            ts_code,
            name: record.name,
            category_id: record.category_id,
          }}
          mode="combined"
          showLink={true}
        />
      ),
    },
    {
      title: "作用范围",
      dataIndex: "scope_type",
      width: 150,
      render: (scope_type, record) => {
        const getScopeDisplay = () => {
          switch (scope_type) {
            case "INSTRUMENT":
              return { text: "单个标的", color: "blue" };
            case "MULTI_INSTRUMENT":
              return { text: "多个标的", color: "cyan" };
            case "ALL_INSTRUMENTS":
              return { text: "所有标的", color: "purple" };
            case "CATEGORY":
              return { text: "单个类别", color: "green" };
            case "MULTI_CATEGORY":
              return { text: "多个类别", color: "lime" };
            case "ALL_CATEGORIES":
              return { text: "所有类别", color: "orange" };
            default:
              return { text: scope_type || "-", color: "default" };
          }
        };

        const { text, color } = getScopeDisplay();
        
        return (
          <Tag color={color}>
            {text}
          </Tag>
        );
      },
    },
    {
      title: "信号描述",
      dataIndex: "message",
      render: (message) => <Typography.Text>{message}</Typography.Text>,
    },
    {
      title: "日期",
      dataIndex: "trade_date",
      width: 130,
      render: (date) => (
        <div>
          <Typography.Text style={{ fontSize: "13px", display: "block" }}>
            {dayjs(date).format("YYYY-MM-DD")}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: "11px" }}>
            {dayjs(date).fromNow()}
          </Typography.Text>
        </div>
      ),
    },
  ];

  const typeOptions = [
    { value: "ALL", label: "全部信号" },
    ...Object.entries(SIGNAL_CONFIG).map(([key, config]) => ({
      value: key,
      label: config.label,
    })),
  ];

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      {/* 页面标题和控制栏 */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          <AlertOutlined style={{ marginRight: 8 }} />
          历史交易信号
        </Typography.Title>
        <Space wrap>
          <DatePicker.RangePicker
            value={dateRange}
            onChange={(dates) => {
              if (dates && dates[0] && dates[1]) {
                setDateRange([dates[0], dates[1]]);
              }
            }}
            allowClear={false}
            format="YYYY-MM-DD"
          />
          <Select
            value={selectedType}
            onChange={setSelectedType}
            options={typeOptions}
            style={{ width: 120 }}
          />
          <Button icon={<ReloadOutlined />} onClick={loadSignals}>
            刷新
          </Button>
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={() => setCreateModalOpen(true)}
          >
            创建信号
          </Button>
          <Button 
            icon={<HistoryOutlined />}
            loading={rebuildLoading}
            onClick={handleRebuildHistorical}
            title="重建所有历史信号，找到首次触发止盈/止损的正确日期"
          >
            重建历史信号
          </Button>
          <Button 
            icon={<FunctionOutlined />}
            loading={structureLoading}
            onClick={handleGenerateStructureSignals}
            title="为今日生成结构信号"
          >
            生成结构信号
          </Button>
          <Button 
            icon={<HistoryOutlined />}
            loading={rebuildStructureLoading}
            onClick={handleRebuildStructureSignals}
            title="重新计算所有历史结构信号"
          >
            重建结构信号
          </Button>
        </Space>
      </div>

      {/* 信号统计卡片 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={6}>
          <Card size="small">
            <Statistic
              title="总信号数"
              value={signalStats.total}
              prefix={<AlertOutlined style={{ color: "#1890ff" }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card size="small">
            <Statistic
              title="高优先级"
              value={signalStats.levelStats.HIGH}
              valueStyle={{ color: "#ff4d4f" }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card size="small">
            <Statistic
              title="风险预警"
              value={signalStats.typeStats.RISK_ALERT}
              valueStyle={{ color: "#ff7a45" }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card size="small">
            <Statistic
              title="结构信号"
              value={signalStats.typeStats.BUY_STRUCTURE + signalStats.typeStats.SELL_STRUCTURE}
              valueStyle={{ color: "#52c41a" }}
            />
          </Card>
        </Col>
      </Row>

      {/* 信号类型分布 */}
      <Card title="信号类型分布" size="small">
        <Space wrap size={[8, 8]}>
          {Object.entries(SIGNAL_CONFIG).map(([type, config]) => {
            const count = signalStats.typeStats[type as SignalType];
            return count > 0 ? (
              <Tag
                key={type}
                color={config.color}
                style={{ margin: 0, cursor: "pointer" }}
                onClick={() => setSelectedType(type)}
              >
                {config.label}: {count}
              </Tag>
            ) : null;
          })}
        </Space>
      </Card>

      {/* 信号详情表格 */}
      <Card title={`信号详情 (${signals.length} 条)`} size="small">
        <Table<SignalRow>
          columns={columns}
          dataSource={signals}
          loading={loading}
          rowKey={(record) => `${record.trade_date}-${record.type}-${record.ts_code || record.category_id || Math.random()}`}
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
          }}
          size="small"
        />
      </Card>

      <CreateSignalModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onSuccess={() => {
          loadSignals();
        }}
      />
    </Space>
  );
}