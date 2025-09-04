import { useEffect, useMemo, useState } from "react";
import { Card } from "antd";
import CandleChartView from "./CandleChartView";
import { buildCandleOption } from "./candleOption";
// Indicator computations and option building are handled in separate modules.
import CandleToolbar from "./CandleToolbar";
import { useCandleData } from "./hooks/useCandleData";
import { fetchKlineConfig } from "../../api/hooks";
import type { SignalDetail, KlineConfig } from "../../api/types";

type Props = {
  tsCode: string;
  months?: number; // default 6
  height?: number; // default 260
  title?: string;
  secType?: string; // STOCK | ETF | FUND | CASH
  stretch?: boolean; // 自适应拉伸高度：按面板自动增长
  signals?: SignalDetail[]; // 信号数据
};

export default function CandleChart({ tsCode, months = 6, height = 300, title = "K线（近6个月）", secType, stretch = true, signals = [] }: Props) {
  const { items, loading, range, setRange, buys, sells } = useCandleData({ tsCode, months });
  const [maInput, setMaInput] = useState<string>("20,30,60");
  const [maList, setMaList] = useState<number[]>([20, 30, 60]);
  const [fullscreen, setFullscreen] = useState(false);
  const [viewportH, setViewportH] = useState<number>(typeof window !== 'undefined' ? window.innerHeight : 900);
  const [klineConfig, setKlineConfig] = useState<KlineConfig | null>(null);


  useEffect(() => {
    const onResize = () => setViewportH(window.innerHeight);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // 获取持仓配置信息用于阈值线展示
  useEffect(() => {
    const loadKlineConfig = async () => {
      try {
        // 使用当前日期获取持仓配置
        const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        const config = await fetchKlineConfig(tsCode, today);
        setKlineConfig(config);
      } catch (error) {
        console.warn('Failed to load kline config:', error);
        setKlineConfig(null);
      }
    };

    if (tsCode && tsCode !== 'CASH') {
      loadKlineConfig();
    } else {
      setKlineConfig(null);
    }
  }, [tsCode]);

  // 解析均线输入
  const applyMaInput = () => {
    const nums = (maInput || '')
      .split(',')
      .map(s => parseInt(s.trim(), 10))
      .filter(n => Number.isFinite(n) && n > 0 && n <= 365);
    if (nums.length === 0) return;
    setMaList(nums);
  };

  // Using decoupled builder only; old inline builder removed.

  // New: decoupled builder usage (keeps layout identical)
  const built = useMemo(
    () => buildCandleOption({ items: items as any, tsCode, secType, maList, buys, sells, signals, viewportH, fullscreen, klineConfig }),
    [items, tsCode, secType, maList, buys, sells, signals, viewportH, fullscreen, klineConfig]
  );

  // 现金类不展示 K 线与指标
  if ((secType || '').toUpperCase() === 'CASH') {
    return (
      <Card title={title} size="small" styles={{ body: { padding: 12 } }}>
        <div style={{ color: '#667085' }}>现金（CASH）不展示K线与技术指标。</div>
      </Card>
    );
  }

  return (
    <>
    <Card
      title={title}
      size="small"
      styles={{ body: { padding: 8 } }}
      loading={loading}
      extra={
        <CandleToolbar
          range={range as any}
          onRangeChange={(r) => setRange(r as any)}
          maInput={maInput}
          onMaInputChange={setMaInput}
          onApplyMaInput={applyMaInput}
          onOpenFullscreen={() => setFullscreen(true)}
        />
      }
    >
      <CandleChartView
        option={built.option}
        height={built.chartHeight}
        title={title}
        fullscreen={fullscreen}
        onOpen={() => setFullscreen(true)}
        onClose={() => setFullscreen(false)}
      />
    </Card>
  </>
  );
}
