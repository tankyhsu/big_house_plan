export const fmtCny = (n?: number | null) =>
  typeof n === "number" ? n.toLocaleString("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 2 }) : "-";

export const fmtPct = (n?: number | null) =>
  typeof n === "number" ? `${(n * 100).toFixed(2)}%` : "-";

export const ymdToDashed = (s: string) => `${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}`;

export const dashedToYmd = (s: string) => s.replaceAll("-", "");

export function formatNumber(value: number | null | undefined, decimals: number = 2): string {
  if (value === null || value === undefined || isNaN(value)) return "-";
  return value.toFixed(decimals);
}

// 全局统一的数值格式化函数
export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) return "-";
  return value.toFixed(4);
}

export function formatQuantity(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) return "-";
  return value.toFixed(2);
}

export function formatShares(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) return "-";
  return value.toFixed(2);
}

export function formatAmount(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) return "-";
  return value.toFixed(4);
}

// 兼容现有的 fmtCny 函数，但调整精度
export const fmtCnyPrecise = (n?: number | null) =>
  typeof n === "number" ? n.toLocaleString("zh-CN", { 
    style: "currency", 
    currency: "CNY", 
    minimumFractionDigits: 4,
    maximumFractionDigits: 4 
  }) : "-";