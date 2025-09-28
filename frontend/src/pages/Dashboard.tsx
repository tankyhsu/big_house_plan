import { useEffect, useMemo, useState } from "react";
import { Button, Flex, Space, Row, Col, Card, Modal, App } from "antd";
import dayjs from "dayjs";
import KpiCards from "../components/KpiCards";
import CategoryTable from "../components/CategoryTable";
import PositionTable from "../components/PositionTable";
import PositionPie from "../components/charts/PositionPie";
import { fetchDashboard, fetchCategory, fetchPosition, postCalc, syncPricesEnhanced, fetchAllSignals, getLastValidTradingDate, getLatestTradingDate } from "../api/hooks";
import { fetchDashboardFull } from "../api/aggregated-hooks";
import type { CategoryRow, PositionRow, SignalRow } from "../api/types";
import { dashedToYmd } from "../utils/format";
import { ReloadOutlined, CalculatorOutlined, CloudSyncOutlined, ExclamationCircleOutlined } from "@ant-design/icons";

export default function Dashboard() {
  const { message } = App.useApp();

  // 智能交易日逻辑
  const today = dayjs();
  const [currentDate, setCurrentDate] = useState(today); // 当前实际显示的日期
  const [isAfter7PM, setIsAfter7PM] = useState(false);
  const [lastValidTradingDate, setLastValidTradingDate] = useState<string | null>(null);
  const [showSyncPrompt, setShowSyncPrompt] = useState(false);

  // 添加会话存储状态来记住用户选择
  const [syncPromptDismissed, setSyncPromptDismissed] = useState(false);
  const [dontShowAgain, setDontShowAgain] = useState(false);

  const ymd = useMemo(() => dashedToYmd(currentDate.format("YYYY-MM-DD")), [currentDate]);
  const [loading, setLoading] = useState(false);
  const [cat, setCat] = useState<CategoryRow[]>([]);
  const [pos, setPos] = useState<PositionRow[]>([]);
  const [dash, setDash] = useState<any>(null);
  const [monthlySignals, setMonthlySignals] = useState<SignalRow[]>([]);

  // 检查会话存储中的用户偏好
  useEffect(() => {
    const dismissed = sessionStorage.getItem('syncPromptDismissed') === 'true';
    const dontShow = sessionStorage.getItem('dontShowSyncPrompt') === 'true';
    setSyncPromptDismissed(dismissed);
    setDontShowAgain(dontShow);
  }, []);

  /**
   * 智能交易日检测逻辑
   * 1. 获取price_eod表中的最新交易日作为基准
   * 2. 检测当前时间是否超过晚上7点
   * 3. 根据条件决定是否提醒用户同步数据或展示最新有效交易日数据
   * 优化：添加会话存储避免重复弹窗
   */
  const checkTradingDateLogic = async () => {
    const now = dayjs();
    const after7PM = now.hour() >= 19; // 晚上7点后
    setIsAfter7PM(after7PM);

    try {
      // 获取price_eod表中的最新交易日
      const latestTradingDateResult = await getLatestTradingDate();
      const latestTradingDate = latestTradingDateResult.latest_trading_date;
      setLastValidTradingDate(latestTradingDate);

      if (!latestTradingDate) {
        // 如果数据库中没有任何价格数据，使用今天的日期
        setCurrentDate(today);
        return;
      }

      const latestDate = dayjs(latestTradingDate);
      const todayStr = today.format("YYYY-MM-DD");
      const isLatestToday = latestTradingDate === todayStr;

      // 判断是否需要提醒同步
      if (after7PM) {
        // 晚上7点后：如果最新交易日不是今天，提醒同步
        if (!isLatestToday && !syncPromptDismissed && !dontShowAgain) {
          setShowSyncPrompt(true);
          return;
        }
      } else {
        // 晚上7点前：如果最新交易日是今天，可以展示昨天的数据；否则检查是否需要同步
        if (isLatestToday) {
          // 如果今天有数据，可以展示昨天的数据（如果存在）
          const yesterday = today.subtract(1, 'day');
          const yesterdayStr = yesterday.format("YYYY-MM-DD");
          const yesterdayData = await getLastValidTradingDate(dashedToYmd(yesterdayStr));
          if (yesterdayData.trade_date === yesterdayStr) {
            setCurrentDate(yesterday);
            return;
          }
        } else {
          // 如果今天没有数据，可能需要提醒同步（取决于是否是工作日）
          const daysSinceLatest = today.diff(latestDate, 'day');
          if (daysSinceLatest > 1 && !syncPromptDismissed && !dontShowAgain) {
            // 如果超过1天没有数据，提醒同步
            setShowSyncPrompt(true);
            return;
          }
        }
      }

      // 默认使用最新有效交易日的数据
      setCurrentDate(latestDate);
    } catch (error) {
      console.error("检测交易日逻辑失败:", error);
      // 如果检测失败，使用今天的日期
      setCurrentDate(today);
    }
  };

  /**
   * 加载仪表板所有数据 - 使用聚合API优化
   * 包括：仪表板汇总、类别数据、持仓数据、近一个月信号
   */
  const loadAll = async () => {
    setLoading(true);
    try {
      // 使用聚合API一次获取所有Dashboard数据
      const data = await fetchDashboardFull(ymd);

      setDash(data.dashboard);
      setCat(data.categories);
      setPos(data.positions);
      setMonthlySignals(data.signals || []);
    } catch (e:any) {
      message.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  // 计算月度信号统计
  const monthlySignalStats = useMemo(() => {
    const stats: Record<string, number> = {};
    monthlySignals.forEach(signal => {
      const type = signal.type.toLowerCase();
      stats[type] = (stats[type] || 0) + 1;
    });
    return stats;
  }, [monthlySignals]);

  useEffect(() => {
    checkTradingDateLogic();
  }, [syncPromptDismissed, dontShowAgain]); // 依赖更新：当用户偏好改变时重新检查

  useEffect(() => {
    if (!showSyncPrompt) {
      loadAll();
    }
  }, [currentDate, showSyncPrompt]);

  /**
   * 重新计算指定日期的投资组合快照
   * 包括持仓计算、类别汇总、信号生成等
   */
  const onCalc = async () => {
    try {
      await postCalc(ymd);
      message.success("已重算快照");
      loadAll();
    } catch (e:any) { message.error(e.message); }
  };

  /**
   * 智能同步价格数据（异步方式）
   * 自动检测并补齐过去7天缺失的价格数据，同步完成后自动重算
   */
  const onSync = async () => {
    setLoading(true);
    const loadingMsg = message.loading("正在同步价格数据，请稍候...", 0);
    
    try {
      // 异步执行同步操作
      syncPricesEnhanced({ 
        lookback_days: 7, 
        recalc: true 
      }).then(async (res) => {
        // 清除特定的loading提示
        loadingMsg();
        setLoading(false);
        
        if (res.total_updated === 0) {
          message.info("价格数据已是最新，无需同步");
        } else {
          const missingDates = Object.keys(res.missing_summary).length;
          message.success(
            `同步完成！已同步 ${res.dates_processed} 个日期的价格数据，更新 ${res.total_updated} 条记录` +
            (missingDates > 0 ? `，补齐了 ${missingDates} 天的缺失数据` : "")
          );
        }
        
        // 同步完成后刷新页面数据
        await loadAll();

        // 清除同步提醒状态，避免立即再次弹窗
        setSyncPromptDismissed(true);
        sessionStorage.setItem('syncPromptDismissed', 'true');
      }).catch((e: any) => {
        // 清除特定的loading提示
        loadingMsg();
        setLoading(false);
        message.error(`同步失败：${e.message}`);
      });
      
    } catch (e: any) { 
      loadingMsg();
      setLoading(false);
      message.error(`启动同步失败：${e.message}`); 
    }
  };

  /**
   * 处理同步提醒弹窗的确认操作
   */
  const handleSyncConfirm = async () => {
    setShowSyncPrompt(false);
    setSyncPromptDismissed(true);
    sessionStorage.setItem('syncPromptDismissed', 'true');

    onSync(); // 不等待同步完成，立即返回
    // 由于同步是异步的，不需要等待就重新检测交易日逻辑
    setTimeout(() => checkTradingDateLogic(), 1000);
  };

  /**
   * 处理同步提醒弹窗的取消操作
   */
  const handleSyncCancel = () => {
    setShowSyncPrompt(false);
    setSyncPromptDismissed(true);
    sessionStorage.setItem('syncPromptDismissed', 'true');

    // 使用最近有效交易日的数据
    if (lastValidTradingDate) {
      setCurrentDate(dayjs(lastValidTradingDate));
    }
  };

  /**
   * 处理"不再提醒"选项
   */
  const handleDontShowAgain = () => {
    setShowSyncPrompt(false);
    setDontShowAgain(true);
    setSyncPromptDismissed(true);

    // 存储用户偏好
    sessionStorage.setItem('dontShowSyncPrompt', 'true');
    sessionStorage.setItem('syncPromptDismissed', 'true');

    // 使用最近有效交易日的数据
    if (lastValidTradingDate) {
      setCurrentDate(dayjs(lastValidTradingDate));
    }

    message.info('已设置不再提醒，您可以随时点击"智能同步"按钮手动同步数据');
  };

  /**
   * 重置同步提醒偏好（可供调试使用）
   */
  const resetSyncPreferences = () => {
    sessionStorage.removeItem('syncPromptDismissed');
    sessionStorage.removeItem('dontShowSyncPrompt');
    setSyncPromptDismissed(false);
    setDontShowAgain(false);
    message.success('已重置同步提醒偏好');
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Flex justify="space-between" align="center" wrap="wrap" gap={12}>
        <h2 style={{ margin: 0 }}>
          长赢指数投资计划 - Dashboard ({currentDate.format("YYYY-MM-DD")})
          {currentDate.format("YYYY-MM-DD") !== today.format("YYYY-MM-DD") && (
            <span style={{ color: '#1890ff', fontSize: '14px', marginLeft: 8 }}>
              (最近有效交易日)
            </span>
          )}
          {isAfter7PM && (
            <span style={{ color: '#ff7875', fontSize: '14px', marginLeft: 8 }}>
              (交易日晚上7点后)
            </span>
          )}
        </h2>
        <Space>
          <Button icon={<CloudSyncOutlined />} onClick={onSync} loading={loading}>智能同步</Button>
          <Button type="primary" icon={<CalculatorOutlined />} onClick={onCalc}>重算</Button>
          <Button icon={<ReloadOutlined />} onClick={loadAll}>刷新</Button>
          {/* 调试功能：重置同步提醒偏好 */}
          {process.env.NODE_ENV === 'development' && (
            <Button size="small" onClick={resetSyncPreferences}>重置提醒</Button>
          )}
        </Space>
      </Flex>

      {dash && (
        <KpiCards
          marketValue={dash.kpi.market_value}
          cost={dash.kpi.cost}
          pnl={dash.kpi.unrealized_pnl}
          ret={dash.kpi.ret}
          signals={monthlySignalStats}
          priceFallback={dash.price_fallback_used}
          dateText={dash.date}
        />
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24} md={12} lg={12} xl={12}>
          <PositionPie />
        </Col>
        <Col xs={24} md={12} lg={12} xl={12}>
          <Card title="类别分布" size="small" styles={{ body: { padding: 12, height: 344 } }}>
            <CategoryTable data={cat} loading={loading} header={false} height={280} />
          </Card>
        </Col>
      </Row>

      {/* 明细列表 */}
      <PositionTable data={pos} loading={loading} signals={monthlySignals} />

      {/* 数据同步提醒弹窗 - 优化版 */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <ExclamationCircleOutlined style={{ color: '#faad14', marginRight: 8 }} />
            数据同步提醒
          </div>
        }
        open={showSyncPrompt}
        onOk={handleSyncConfirm}
        onCancel={handleSyncCancel}
        confirmLoading={loading}
        footer={[
          <Button key="never" onClick={handleDontShowAgain}>
            不再提醒
          </Button>,
          <Button key="cancel" onClick={handleSyncCancel}>
            稍后再说
          </Button>,
          <Button key="ok" type="primary" loading={loading} onClick={handleSyncConfirm}>
            立即同步
          </Button>
        ]}
      >
        <p>
          {isAfter7PM
            ? "现在是交易日晚上7点后，检测到可能需要同步最新的价格数据。"
            : "检测到价格数据可能不是最新的，"
          }
          是否需要同步最新的价格数据？
        </p>
        <p style={{ color: '#666' }}>
          当前数据库中最新交易日为：{lastValidTradingDate}<br/>
          • 选择"立即同步"将获取最新数据并重新计算投资组合<br/>
          • 选择"稍后再说"将展示最近有效交易日的数据<br/>
          • 选择"不再提醒"将不再弹出此提醒（本次会话内有效）
        </p>
      </Modal>
    </Space>
  );
}
