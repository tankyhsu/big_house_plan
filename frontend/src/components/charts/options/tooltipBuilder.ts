import { formatPrice, formatQuantity } from "../../../utils/format";
import { getSignalConfig } from "../../../utils/signalConfig";
import type { SignalType } from "../../../api/types";
import type { Item } from './types';

export function buildTooltipFormatter(params: {
  items: Item[];
  dates: string[];
  upColor: string;
  downColor: string;
  maColors: string[];
}) {
  const { items, dates, upColor, downColor, maColors } = params;

  function fmtVol(n: number) {
    if (n >= 1e8) return formatQuantity(n / 1e8) + ' 亿';
    if (n >= 1e4) return formatQuantity(n / 1e4) + ' 万';
    return String(Math.round(n));
  }

  return (params: any[]) => {
    const pK = params.find(p => p.seriesType === 'candlestick');
    const pV = params.find(p => p.seriesType === 'bar');
    const pLines = params.filter(p => p.seriesType === 'line');
    const pSignals = params.filter(p => p.seriesType === 'scatter' && p.data?.signalData);
    
    const date = (pK?.axisValue || pV?.axisValue || '').toString();
    const arr = (pK?.data || []) as number[];
    
    // Universal fix: Always use original data to ensure accuracy for all symbols
    const dateIndex = dates.indexOf(date);
    let o: number, c: number, l: number, h: number;
    
    if (dateIndex >= 0 && dateIndex < items.length) {
      // Always use original data from items array to avoid any tooltip data corruption
      const item = items[dateIndex];
      o = item.open;
      c = item.close;
      l = Math.min(item.low ?? item.close, item.high ?? item.close);
      h = Math.max(item.low ?? item.close, item.high ?? item.close);
    } else {
      // Fallback to ECharts data if date not found
      o = arr[0] || 0; c = arr[1] || 0; l = arr[2] || 0; h = arr[3] || 0;
    }
    
    const vol = (pV?.seriesName === 'Volume') ? ((pV?.data?.value ?? pV?.data ?? null) as number | null) : null;
    
    let html = `<div style="padding: 8px;">`;
    
    // Date header
    html += `<div style="font-weight: bold; font-size: 13px; margin-bottom: 8px; color: #fff; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 6px;">${date}</div>`;
    
    // Price data (OHLC)
    if (arr.length) {
      const isRising = c >= o;
      const priceColor = isRising ? upColor : downColor;
      html += `<div style="margin-bottom: 8px;">`;
      html += `<div style="display: flex; gap: 12px; font-size: 12px;">`;
      html += `<span style="color: #ccc;">开:</span><span style="color: ${priceColor}; font-weight: bold;">${formatPrice(o)}</span>`;
      html += `<span style="color: #ccc;">高:</span><span style="color: ${priceColor}; font-weight: bold;">${formatPrice(h)}</span>`;
      html += `<span style="color: #ccc;">低:</span><span style="color: ${priceColor}; font-weight: bold;">${formatPrice(l)}</span>`;
      html += `<span style="color: #ccc;">收:</span><span style="color: ${priceColor}; font-weight: bold;">${formatPrice(c)}</span>`;
      html += `</div>`;
      html += `</div>`;
    }
    
    // Volume
    if (vol != null) {
      html += `<div style="margin-bottom: 8px; font-size: 12px;">`;
      html += `<span style="color: #ccc;">成交量:</span> <span style="color: #ffa726; font-weight: bold;">${fmtVol(Number(vol))}</span>`;
      html += `</div>`;
    }
    
    // 按业务意义分组显示指标
    if (pLines && pLines.length > 0) {
      // 1. 趋势指标 (MA均线) - 一行显示
      const maLines = pLines.filter(pl => pl.seriesName.startsWith('MA'));
      if (maLines.length > 0) {
        html += `<div style="margin-bottom: 8px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 6px;">`;
        html += `<div style="color: #ffa726; font-size: 11px; margin-bottom: 4px;">趋势指标</div>`;
        html += `<div style="display: flex; flex-wrap: wrap; gap: 8px; font-size: 11px;">`;
        maLines.forEach((pl, idx) => {
          const color = maColors[idx % maColors.length];
          if (typeof pl.data === 'number') {
            html += `<span><span style="color: ${color};">●</span> ${pl.seriesName}: <span style="color: ${color}; font-weight: bold;">${formatQuantity(pl.data)}</span></span>`;
          }
        });
        html += `</div></div>`;
      }
      
      // 2. 持仓参考线 (成本线、止盈线或止损线) - 分行显示
      const positionLines = pLines.filter(pl => 
        pl.seriesName.includes('成本线') || 
        pl.seriesName.includes('止盈线') || 
        pl.seriesName.includes('止损线')
      );
      if (positionLines.length > 0) {
        html += `<div style="margin-bottom: 8px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 6px;">`;
        html += `<div style="color: #10b981; font-size: 11px; margin-bottom: 4px;">持仓参考</div>`;
        positionLines.forEach(pl => {
          if (typeof pl.data === 'number') {
            let lineColor = '#666666';
            let lineIcon = '━';
            if (pl.seriesName.includes('止盈')) {
              lineColor = '#10b981';
              lineIcon = '━';
            } else if (pl.seriesName.includes('止损')) {
              lineColor = '#ef4444';  
              lineIcon = '━';
            }
            html += `<div style="font-size: 11px; margin-bottom: 2px;"><span style="color: ${lineColor};">${lineIcon}</span> <span style="color: #ccc;">${pl.seriesName}:</span> <span style="color: ${lineColor}; font-weight: bold;">${formatPrice(pl.data)}</span></div>`;
          }
        });
        html += `</div>`;
      }
      
      // 3. 技术指标 (MACD, KDJ, BIAS等) - 按类型分行
      const techLines = pLines.filter(pl => 
        !pl.seriesName.startsWith('MA') && 
        !pl.seriesName.includes('成本线') && 
        !pl.seriesName.includes('止盈线') && 
        !pl.seriesName.includes('止损线')
      );
      if (techLines.length > 0) {
        html += `<div style="margin-bottom: 8px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 6px;">`;
        html += `<div style="color: #42a5f5; font-size: 11px; margin-bottom: 4px;">技术指标</div>`;
        
        // MACD 指标一行
        const macdLines = techLines.filter(pl => pl.seriesName.includes('DIF') || pl.seriesName.includes('DEA') || pl.seriesName.includes('MACD'));
        if (macdLines.length > 0) {
          html += `<div style="font-size: 11px; margin-bottom: 2px;">`;
          macdLines.forEach((pl, idx) => {
            if (typeof pl.data === 'number') {
              let indicatorColor = '#42a5f5';
              if (pl.seriesName.includes('DIF')) indicatorColor = '#ef4444';
              else if (pl.seriesName.includes('DEA')) indicatorColor = '#3b82f6';
              else if (pl.seriesName.includes('MACD')) indicatorColor = '#10b981';
              html += `<span><span style="color: ${indicatorColor};">●</span> ${pl.seriesName}: <span style="color: ${indicatorColor}; font-weight: bold;">${formatQuantity(pl.data)}</span></span>`;
              if (idx < macdLines.length - 1) html += `<span style="color: #666; margin: 0 4px;">|</span>`;
            }
          });
          html += `</div>`;
        }
        
        // KDJ 指标一行  
        const kdjLines = techLines.filter(pl => pl.seriesName.includes('K') || pl.seriesName.includes('D') || pl.seriesName.includes('J'));
        if (kdjLines.length > 0) {
          html += `<div style="font-size: 11px; margin-bottom: 2px;">`;
          kdjLines.forEach((pl, idx) => {
            if (typeof pl.data === 'number') {
              let indicatorColor = '#42a5f5';
              if (pl.seriesName.includes('K')) indicatorColor = '#22c55e';
              else if (pl.seriesName.includes('D')) indicatorColor = '#f59e0b';
              else if (pl.seriesName.includes('J')) indicatorColor = '#ef4444';
              html += `<span><span style="color: ${indicatorColor};">●</span> ${pl.seriesName}: <span style="color: ${indicatorColor}; font-weight: bold;">${formatQuantity(pl.data)}</span></span>`;
              if (idx < kdjLines.length - 1) html += `<span style="color: #666; margin: 0 4px;">|</span>`;
            }
          });
          html += `</div>`;
        }
        
        // BIAS 指标一行
        const biasLines = techLines.filter(pl => pl.seriesName.includes('BIAS'));
        if (biasLines.length > 0) {
          html += `<div style="font-size: 11px; margin-bottom: 2px;">`;
          biasLines.forEach((pl, idx) => {
            if (typeof pl.data === 'number') {
              html += `<span><span style="color: #8b5cf6;">●</span> ${pl.seriesName}: <span style="color: #8b5cf6; font-weight: bold;">${formatQuantity(pl.data)}%</span></span>`;
              if (idx < biasLines.length - 1) html += `<span style="color: #666; margin: 0 4px;">|</span>`;
            }
          });
          html += `</div>`;
        }
        
        html += `</div>`;
      }
    }
    
    // Add trading events information
    const pBuys = params.filter(p => p.seriesName === 'BUY');
    const pSells = params.filter(p => p.seriesName === 'SELL');
    const tradingEvents = [...pBuys, ...pSells];
    
    if (tradingEvents.length > 0) {
      html += `<div style="border-top: 1px solid rgba(255,255,255,0.2); margin-top: 8px; padding-top: 8px;">`;
      html += `<div style="font-weight: bold; font-size: 12px; margin-bottom: 6px; color: #fff;">💼 交易记录</div>`;
      
      tradingEvents.forEach(trade => {
        const isBuy = trade.seriesName === 'BUY';
        const action = isBuy ? '买入' : '卖出';
        const actionColor = isBuy ? upColor : downColor;
        const actionIcon = isBuy ? '📈' : '📉';
        const price = trade.value[1];
        
        html += `<div style="margin-bottom: 6px; padding: 4px 0;">`;
        html += `<div style="display: flex; align-items: center; margin-bottom: 2px;">`;
        html += `<span style="font-size: 14px; margin-right: 4px;">${actionIcon}</span>`;
        html += `<span style="color: ${actionColor}; font-weight: bold; font-size: 12px;">${action}</span>`;
        html += `</div>`;
        html += `<div style="color: #ccc; font-size: 11px; line-height: 1.4; margin-left: 20px;">成交价: <span style="color: ${actionColor}; font-weight: bold;">¥${price}</span></div>`;
        html += `</div>`;
      });
      
      html += `</div>`;
    }
    
    // Signals section
    if (pSignals && pSignals.length > 0) {
      html += `<div style="border-top: 1px solid rgba(255,255,255,0.2); margin-top: 8px; padding-top: 8px;">`;
      html += `<div style="font-weight: bold; font-size: 12px; margin-bottom: 6px; color: #fff;">📡 交易信号</div>`;
      
      pSignals.forEach(ps => {
        const signal = ps.data.signalData;
        const config = getSignalConfig(signal.type as SignalType);
        
        // Signal level badge
        let levelBadge = '';
        if (signal.level) {
          let levelColor = '#666';
          let levelText = '';
          switch(signal.level) {
            case 'HIGH': levelColor = '#ff4757'; levelText = '高'; break;
            case 'MEDIUM': levelColor = '#ff9500'; levelText = '中'; break;
            case 'LOW': levelColor = '#5352ed'; levelText = '低'; break;
            case 'INFO': levelColor = '#747d8c'; levelText = '信息'; break;
          }
          levelBadge = `<span style="background: ${levelColor}; color: white; font-size: 10px; padding: 1px 4px; border-radius: 2px; margin-left: 4px;">${levelText}</span>`;
        }
        
        html += `<div style="margin-bottom: 6px; padding: 4px 0;">`;
        html += `<div style="display: flex; align-items: center; margin-bottom: 2px;">`;
        html += `<span style="font-size: 14px; margin-right: 4px;">${config.emoji}</span>`;
        html += `<span style="color: ${config.color}; font-weight: bold; font-size: 12px;">${config.label}</span>`;
        html += levelBadge;
        html += `</div>`;
        html += `<div style="color: #ccc; font-size: 11px; line-height: 1.4; margin-left: 20px;">${signal.message}</div>`;
        html += `</div>`;
      });
      
      html += `</div>`;
    }
    
    html += `</div>`;
    return html;
  };
}