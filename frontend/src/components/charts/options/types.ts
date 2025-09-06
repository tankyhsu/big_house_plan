// 共享类型定义
export type Item = { 
  date: string; 
  open: number; 
  high?: number | null; 
  low?: number | null; 
  close: number; 
  vol?: number | null 
};

export type Trade = { 
  date: string; 
  price: number 
};

export type Signal = { 
  date: string; 
  price: number | null; 
  type: string; 
  message: string;
  level?: string;
};

export type KlineConfig = { 
  avg_cost: number; 
  stop_gain_threshold: number; 
  stop_loss_threshold: number; 
  stop_gain_price: number; 
  stop_loss_price: number 
} | null;

export type Panel = {
  key: 'price' | 'vol' | 'macd' | 'kdj' | 'bias';
  height: number;
  top: number;
};

export type CandleOptionParams = {
  items: Item[];
  tsCode: string;
  secType?: string;
  maList: number[];
  buys: Trade[];
  sells: Trade[];
  signals: Signal[];
  viewportH: number;
  fullscreen: boolean;
  klineConfig?: KlineConfig;
};