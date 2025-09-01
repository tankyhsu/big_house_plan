// Technical indicator helpers extracted from CandleChart.
// Keep logic identical to inlined versions to avoid behavior changes.

export function sma(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i] ?? 0;
    sum += v;
    if (i >= period) sum -= (values[i - period] ?? 0);
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

export function ema(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  const k = 2 / (period + 1);
  let prev: number | null = null;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v == null) { out[i] = prev; continue; }
    if (prev == null) prev = v; else prev = v * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}

export function computeMacd(closes: number[]) {
  const ema12 = ema(closes as number[], 12);
  const ema26 = ema(closes as number[], 26);
  const dif: (number | null)[] = closes.map((_, i) => (ema12[i] != null && ema26[i] != null) ? (ema12[i]! - ema26[i]!) : null);
  const dea = ema(dif.map(v => (v == null ? 0 : v)) as number[], 9); // 简化处理，保持原逻辑
  const macd: (number | null)[] = closes.map((_, i) => (dif[i] != null && dea[i] != null) ? (dif[i]! - dea[i]!) * 2 : null);
  return { ema12, ema26, dif, dea, macd };
}

export function computeKdj(highs: number[], lows: number[], closes: number[], period = 9) {
  const rsv: (number | null)[] = new Array(closes.length).fill(null);
  for (let i = 0; i < closes.length; i++) {
    const start = Math.max(0, i - period + 1);
    const hh = Math.max(...highs.slice(start, i + 1));
    const ll = Math.min(...lows.slice(start, i + 1));
    const c = closes[i] ?? 0;
    const denom = (hh - ll);
    rsv[i] = denom === 0 ? 0 : ((c - ll) / denom) * 100;
  }
  const kArr: (number | null)[] = new Array(closes.length).fill(null);
  const dArr: (number | null)[] = new Array(closes.length).fill(null);
  const jArr: (number | null)[] = new Array(closes.length).fill(null);
  for (let i = 0; i < closes.length; i++) {
    const prevK = i > 0 && kArr[i-1] != null ? kArr[i-1]! : 50;
    const prevD = i > 0 && dArr[i-1] != null ? dArr[i-1]! : 50;
    const curRsv = (rsv[i] == null ? 0 : rsv[i]!);
    const k = (2/3) * prevK + (1/3) * curRsv;
    const d = (2/3) * prevD + (1/3) * k;
    const j = 3 * k - 2 * d;
    kArr[i] = k; dArr[i] = d; jArr[i] = j;
  }
  return { kArr, dArr, jArr };
}

export function computeBias(closes: number[], periods = [20, 30, 60]) {
  const maMap: Record<number, (number | null)[]> = {};
  const out: Record<number, (number | null)[]> = {};
  periods.forEach(p => { maMap[p] = sma(closes, p); });
  periods.forEach(p => {
    const ma = maMap[p]!;
    out[p] = closes.map((c, i) => (ma[i] ? ((c - (ma[i]!)) / (ma[i]!)) * 100 : null));
  });
  return out;
}

export function mapVolumes(items: { open: number; close: number; vol?: number | null }[], upColor: string, downColor: string) {
  return items.map(it => {
    const isUp = (it.close ?? 0) >= (it.open ?? 0);
    const v = typeof it.vol === 'number' ? it.vol : 0;
    return { value: v, itemStyle: { color: isUp ? upColor : downColor } } as any;
  });
}
