import { describe, it, expect } from 'vitest'
import {
  fmtCny,
  fmtPct,
  ymdToDashed,
  dashedToYmd,
  formatNumber,
  formatPrice,
  formatQuantity,
  formatShares,
  formatAmount,
  fmtCnyPrecise
} from './format'

describe('format utilities', () => {
  describe('fmtCny', () => {
    it('should format number as CNY currency', () => {
      expect(fmtCny(1234.56)).toBe('¥1,234.56')
      expect(fmtCny(1000)).toBe('¥1,000.00')
      expect(fmtCny(0)).toBe('¥0.00')
    })

    it('should handle null and undefined values', () => {
      expect(fmtCny(null)).toBe('-')
      expect(fmtCny(undefined)).toBe('-')
    })

    it('should handle negative numbers', () => {
      expect(fmtCny(-1234.56)).toBe('-¥1,234.56')
    })
  })

  describe('fmtPct', () => {
    it('should format number as percentage', () => {
      expect(fmtPct(0.1234)).toBe('12.34%')
      expect(fmtPct(0.05)).toBe('5.00%')
      expect(fmtPct(1.5)).toBe('150.00%')
      expect(fmtPct(0)).toBe('0.00%')
    })

    it('should handle null and undefined values', () => {
      expect(fmtPct(null)).toBe('-')
      expect(fmtPct(undefined)).toBe('-')
    })

    it('should handle negative percentages', () => {
      expect(fmtPct(-0.15)).toBe('-15.00%')
    })
  })

  describe('ymdToDashed', () => {
    it('should convert YYYYMMDD to YYYY-MM-DD', () => {
      expect(ymdToDashed('20231201')).toBe('2023-12-01')
      expect(ymdToDashed('20240615')).toBe('2024-06-15')
      expect(ymdToDashed('19991231')).toBe('1999-12-31')
    })
  })

  describe('dashedToYmd', () => {
    it('should convert YYYY-MM-DD to YYYYMMDD', () => {
      expect(dashedToYmd('2023-12-01')).toBe('20231201')
      expect(dashedToYmd('2024-06-15')).toBe('20240615')
      expect(dashedToYmd('1999-12-31')).toBe('19991231')
    })
  })

  describe('formatNumber', () => {
    it('should format numbers with default 2 decimal places', () => {
      expect(formatNumber(123.456)).toBe('123.46')
      expect(formatNumber(100)).toBe('100.00')
      expect(formatNumber(0)).toBe('0.00')
    })

    it('should format numbers with custom decimal places', () => {
      expect(formatNumber(123.456, 4)).toBe('123.4560')
      expect(formatNumber(123.456, 0)).toBe('123')
      expect(formatNumber(123.456, 1)).toBe('123.5')
    })

    it('should handle null, undefined and NaN values', () => {
      expect(formatNumber(null)).toBe('-')
      expect(formatNumber(undefined)).toBe('-')
      expect(formatNumber(NaN)).toBe('-')
    })
  })

  describe('formatPrice', () => {
    it('should format numbers with 4 decimal places', () => {
      expect(formatPrice(123.456)).toBe('123.4560')
      expect(formatPrice(100)).toBe('100.0000')
      expect(formatPrice(0)).toBe('0.0000')
    })

    it('should handle null, undefined and NaN values', () => {
      expect(formatPrice(null)).toBe('-')
      expect(formatPrice(undefined)).toBe('-')
      expect(formatPrice(NaN)).toBe('-')
    })
  })

  describe('formatQuantity', () => {
    it('should format numbers with 2 decimal places', () => {
      expect(formatQuantity(123.456)).toBe('123.46')
      expect(formatQuantity(100)).toBe('100.00')
      expect(formatQuantity(0)).toBe('0.00')
    })

    it('should handle null, undefined and NaN values', () => {
      expect(formatQuantity(null)).toBe('-')
      expect(formatQuantity(undefined)).toBe('-')
      expect(formatQuantity(NaN)).toBe('-')
    })
  })

  describe('formatShares', () => {
    it('should format numbers with 2 decimal places', () => {
      expect(formatShares(123.456)).toBe('123.46')
      expect(formatShares(100)).toBe('100.00')
      expect(formatShares(0)).toBe('0.00')
    })

    it('should handle null, undefined and NaN values', () => {
      expect(formatShares(null)).toBe('-')
      expect(formatShares(undefined)).toBe('-')
      expect(formatShares(NaN)).toBe('-')
    })
  })

  describe('formatAmount', () => {
    it('should format numbers with 4 decimal places', () => {
      expect(formatAmount(123.456)).toBe('123.4560')
      expect(formatAmount(100)).toBe('100.0000')
      expect(formatAmount(0)).toBe('0.0000')
    })

    it('should handle null, undefined and NaN values', () => {
      expect(formatAmount(null)).toBe('-')
      expect(formatAmount(undefined)).toBe('-')
      expect(formatAmount(NaN)).toBe('-')
    })
  })

  describe('fmtCnyPrecise', () => {
    it('should format number as CNY currency with 4 decimal places', () => {
      expect(fmtCnyPrecise(1234.56)).toBe('¥1,234.5600')
      expect(fmtCnyPrecise(1000)).toBe('¥1,000.0000')
      expect(fmtCnyPrecise(0)).toBe('¥0.0000')
    })

    it('should handle null and undefined values', () => {
      expect(fmtCnyPrecise(null)).toBe('-')
      expect(fmtCnyPrecise(undefined)).toBe('-')
    })

    it('should handle negative numbers', () => {
      expect(fmtCnyPrecise(-1234.56)).toBe('-¥1,234.5600')
    })
  })
})