export const fmtCny = (n?: number | null) =>
  typeof n === "number" ? n.toLocaleString("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 2 }) : "-";

export const fmtPct = (n?: number | null) =>
  typeof n === "number" ? `${(n * 100).toFixed(2)}%` : "-";

export const ymdToDashed = (s: string) => `${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}`;

export const dashedToYmd = (s: string) => s.replaceAll("-", "");