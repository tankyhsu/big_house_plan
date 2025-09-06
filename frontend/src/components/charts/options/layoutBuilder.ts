import type { Panel } from './types';

export function buildChartLayout(params: {
  secType?: string;
  viewportH: number;
  fullscreen: boolean;
}) {
  const { secType, viewportH, fullscreen } = params;
  
  const padTop = 12;
  const padGap = 28;
  const sliderHeight = 24;
  const sliderBottom = 10;
  const padBottom = sliderHeight + sliderBottom + 6;
  const leftPad = 120;
  const legendH = 18;
  const g1Top = padTop;

  const t = (secType || '').toUpperCase();
  const wantMacd = t !== 'CASH';
  const wantKdj = t !== 'CASH';
  const wantBias = ['ETF', 'FUND'].includes(t);
  const wantVol = t !== 'FUND';

  const panels: Panel[] = [];
  const restPanels: ('vol'|'macd'|'kdj'|'bias')[] = [];
  if (wantVol) restPanels.push('vol');
  if (wantMacd) restPanels.push('macd');
  if (wantKdj) restPanels.push('kdj');
  if (wantBias) restPanels.push('bias');

  let layoutH = 300;
  if (fullscreen) {
    const baseH = Math.max(520, viewportH - 108);
    const totalAvail = baseH - padTop - padBottom;
    const priceWeight = 0.3;
    const priceHeight = Math.floor(totalAvail * priceWeight);
    panels.push({ key: 'price', height: priceHeight, top: g1Top + legendH });
    let cursorTop = g1Top + legendH + priceHeight + padGap;
    const restCount = restPanels.length;
    const per = restCount > 0 ? Math.floor((totalAvail - priceHeight - padGap * restCount) / restCount) : 0;
    restPanels.forEach((key, idx) => {
      let h = per;
      if (idx === restCount - 1) {
        const used = priceHeight + per * (restCount - 1) + padGap * restCount;
        const remain = totalAvail - used;
        h = Math.max(per, remain);
      }
      panels.push({ key, height: h, top: cursorTop + legendH });
      cursorTop += legendH + h + padGap;
    });
    layoutH = baseH;
  } else {
    const priceH = 280; const volH = 160; const macdH = 180; const kdjH = 180; const biasH = 180;
    panels.push({ key: 'price', height: priceH, top: g1Top + legendH });
    let cursorTop = g1Top + legendH + priceH + padGap;
    for (const key of restPanels) {
      const h = key === 'vol' ? volH : (key === 'macd' ? macdH : (key === 'kdj' ? kdjH : biasH));
      panels.push({ key, height: h, top: cursorTop + legendH });
      cursorTop += legendH + h + padGap;
    }
    layoutH = cursorTop - padGap + padBottom;
  }

  return {
    panels,
    layoutH,
    leftPad,
    legendH,
    sliderHeight,
    sliderBottom,
    wantMacd,
    wantKdj,
    wantBias,
    wantVol,
    restPanels
  };
}