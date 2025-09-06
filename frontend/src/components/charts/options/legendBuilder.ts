import { getSignalConfig } from "../../../utils/signalConfig";
import type { SignalType } from "../../../api/types";
import type { Panel, Trade, Signal, KlineConfig, Item } from './types';

export function buildLegends(params: {
  panels: Panel[];
  leftPad: number;
  legendH: number;
  tsCode: string;
  maList: number[];
  klineConfig?: KlineConfig;
  items: Item[];
  buys: Trade[];
  sells: Trade[];
  signalGroups: Record<string, Signal[]>;
  restPanels: ('vol'|'macd'|'kdj'|'bias')[];
}) {
  const { 
    panels, 
    leftPad, 
    legendH, 
    tsCode, 
    maList, 
    klineConfig, 
    items, 
    buys, 
    sells, 
    signalGroups, 
    restPanels 
  } = params;

  const legends: any[] = [];
  const pricePanel = panels.find(p => p.key === 'price')!;
  
  // Price panel legend
  const priceLegendData: string[] = [tsCode, ...maList.map(p => `MA${p}`)];
  
  if (klineConfig && typeof klineConfig.avg_cost === 'number' && !isNaN(klineConfig.avg_cost)) {
    const latestPrice = items.length > 0 ? items[items.length - 1].close : klineConfig.avg_cost;
    const isProfitable = latestPrice > klineConfig.avg_cost;
    
    priceLegendData.push(`成本线 (¥${klineConfig.avg_cost.toFixed(2)})`);
    if (isProfitable && typeof klineConfig.stop_gain_price === 'number' && !isNaN(klineConfig.stop_gain_price)) {
      priceLegendData.push(`止盈线 (+${(klineConfig.stop_gain_threshold * 100).toFixed(0)}% ¥${klineConfig.stop_gain_price.toFixed(2)})`);
    } else if (typeof klineConfig.stop_loss_price === 'number' && !isNaN(klineConfig.stop_loss_price)) {
      priceLegendData.push(`止损线 (-${(klineConfig.stop_loss_threshold * 100).toFixed(0)}% ¥${klineConfig.stop_loss_price.toFixed(2)})`);
    }
  }
  
  if (buys.length > 0) priceLegendData.push('BUY');
  if (sells.length > 0) priceLegendData.push('SELL');
  
  // Add all signal types to legend
  Object.entries(signalGroups).forEach(([signalType, signalsOfType]) => {
    if (signalsOfType.length > 0) {
      const config = getSignalConfig(signalType as SignalType);
      priceLegendData.push(config.label);
    }
  });
  
  legends.push({ 
    type: 'plain', 
    top: (pricePanel.top || 0) - legendH + 2, 
    left: leftPad, 
    right: 24, 
    data: priceLegendData, 
    icon: 'circle', 
    itemWidth: 8, 
    itemHeight: 8, 
    textStyle: { color: '#667085' } 
  });

  // Technical indicators legends
  for (const key of restPanels) {
    const p = panels.find(pp => pp.key === key);
    if (!p) continue;
    
    let data: string[] = [];
    if (key === 'macd') data = ['MACD','DIF','DEA'];
    if (key === 'kdj') data = ['K','D','J'];
    if (key === 'bias') data = ['BIAS20','BIAS30','BIAS60'];
    
    if (data.length) {
      legends.push({ 
        type: 'plain', 
        top: (p.top || 0) - legendH + 2, 
        left: leftPad, 
        right: 24, 
        data, 
        icon: 'circle', 
        itemWidth: 8, 
        itemHeight: 8, 
        textStyle: { color: '#667085' } 
      });
    }
  }

  return legends;
}