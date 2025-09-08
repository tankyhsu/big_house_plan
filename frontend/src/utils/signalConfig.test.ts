import { describe, it, expect } from 'vitest'
import {
  SIGNAL_CONFIG,
  LEVEL_CONFIG,
  getSignalColor,
  getSignalLabel,
  getSignalConfig,
  getSignalPriority,
  type SignalConfig
} from './signalConfig'
import type { SignalType, SignalLevel } from '../api/types'

describe('signalConfig utilities', () => {
  describe('SIGNAL_CONFIG', () => {
    it('should contain all required signal types', () => {
      expect(SIGNAL_CONFIG.BUY_STRUCTURE).toBeDefined()
      expect(SIGNAL_CONFIG.SELL_STRUCTURE).toBeDefined()
      expect(SIGNAL_CONFIG.BULLISH).toBeDefined()
      expect(SIGNAL_CONFIG.BEARISH).toBeDefined()
      expect(SIGNAL_CONFIG.ZIG_BUY).toBeDefined()
      expect(SIGNAL_CONFIG.ZIG_SELL).toBeDefined()
    })

    it('should have consistent structure for all signal configs', () => {
      Object.values(SIGNAL_CONFIG).forEach(config => {
        expect(config).toHaveProperty('label')
        expect(config).toHaveProperty('color')
        expect(config).toHaveProperty('description')
        expect(config).toHaveProperty('emoji')
        expect(typeof config.label).toBe('string')
        expect(typeof config.color).toBe('string')
        expect(typeof config.description).toBe('string')
        expect(typeof config.emoji).toBe('string')
      })
    })
  })

  describe('LEVEL_CONFIG', () => {
    it('should contain all required signal levels', () => {
      expect(LEVEL_CONFIG.HIGH).toBeDefined()
      expect(LEVEL_CONFIG.MEDIUM).toBeDefined()
      expect(LEVEL_CONFIG.LOW).toBeDefined()
      expect(LEVEL_CONFIG.INFO).toBeDefined()
    })

    it('should have consistent structure for all level configs', () => {
      Object.values(LEVEL_CONFIG).forEach(config => {
        expect(config).toHaveProperty('label')
        expect(config).toHaveProperty('color')
        expect(typeof config.label).toBe('string')
        expect(typeof config.color).toBe('string')
      })
    })
  })

  describe('getSignalColor', () => {
    it('should return correct colors for known signal types', () => {
      expect(getSignalColor('BUY_STRUCTURE')).toBe('#95d5b2')
      expect(getSignalColor('SELL_STRUCTURE')).toBe('#ffb3ba')
      expect(getSignalColor('BULLISH')).toBe('#52c41a')
      expect(getSignalColor('BEARISH')).toBe('#fa8c16')
      expect(getSignalColor('ZIG_BUY')).toBe('#52c41a')
      expect(getSignalColor('ZIG_SELL')).toBe('#ff4d4f')
    })

    it('should return default color for unknown signal type', () => {
      expect(getSignalColor('UNKNOWN' as SignalType)).toBe('#1890ff')
    })
  })

  describe('getSignalLabel', () => {
    it('should return correct labels for known signal types', () => {
      expect(getSignalLabel('BUY_STRUCTURE')).toBe('九转买入')
      expect(getSignalLabel('SELL_STRUCTURE')).toBe('九转卖出')
      expect(getSignalLabel('BULLISH')).toBe('利好')
      expect(getSignalLabel('BEARISH')).toBe('利空')
      expect(getSignalLabel('ZIG_BUY')).toBe('买点')
      expect(getSignalLabel('ZIG_SELL')).toBe('卖点')
    })

    it('should return signal type as fallback for unknown types', () => {
      expect(getSignalLabel('UNKNOWN' as SignalType)).toBe('UNKNOWN')
    })
  })

  describe('getSignalConfig', () => {
    it('should return correct config for known signal types', () => {
      const buyConfig = getSignalConfig('BUY_STRUCTURE')
      expect(buyConfig.label).toBe('九转买入')
      expect(buyConfig.color).toBe('#95d5b2')
      expect(buyConfig.emoji).toBe('🏗️')
      expect(buyConfig.symbol).toBe('triangle')
      expect(buyConfig.position).toBe('top')
      expect(buyConfig.offsetMultiplier).toBe(0.9)
    })

    it('should return default config for unknown signal types', () => {
      const unknownConfig = getSignalConfig('UNKNOWN' as SignalType)
      expect(unknownConfig.label).toBe('UNKNOWN')
      expect(unknownConfig.color).toBe('#1890ff')
      expect(unknownConfig.emoji).toBe('📍')
      expect(unknownConfig.symbol).toBe('circle')
      expect(unknownConfig.position).toBe('top')
      expect(unknownConfig.offsetMultiplier).toBe(1.01)
    })
  })

  describe('getSignalPriority', () => {
    it('should return correct priorities for different signal types', () => {
      expect(getSignalPriority('BUY_STRUCTURE')).toBe(3)
      expect(getSignalPriority('SELL_STRUCTURE')).toBe(3)
      expect(getSignalPriority('ZIG_BUY')).toBe(3)
      expect(getSignalPriority('ZIG_SELL')).toBe(3)
      expect(getSignalPriority('BULLISH')).toBe(1)
      expect(getSignalPriority('BEARISH')).toBe(1)
    })

    it('should return default priority for unknown signal types', () => {
      expect(getSignalPriority('UNKNOWN' as SignalType)).toBe(0)
    })

    it('should allow for proper priority sorting', () => {
      const signals: SignalType[] = ['BULLISH', 'BUY_STRUCTURE', 'BEARISH', 'ZIG_SELL']
      const sorted = signals.sort((a, b) => getSignalPriority(b) - getSignalPriority(a))
      
      // Higher priority signals should come first
      expect(sorted[0]).toBe('BUY_STRUCTURE')
      expect(sorted[1]).toBe('ZIG_SELL')
      expect(sorted[2]).toBe('BULLISH')
      expect(sorted[3]).toBe('BEARISH')
    })
  })

  describe('signal position and display properties', () => {
    it('should have correct position settings for buy and sell signals', () => {
      const buyStructure = getSignalConfig('BUY_STRUCTURE')
      const sellStructure = getSignalConfig('SELL_STRUCTURE')
      
      expect(buyStructure.position).toBe('top')
      expect(sellStructure.position).toBe('bottom')
    })

    it('should have rotation settings for sell signals', () => {
      const sellStructure = getSignalConfig('SELL_STRUCTURE')
      const zigSell = getSignalConfig('ZIG_SELL')
      
      expect(sellStructure.symbolRotate).toBe(180)
      expect(zigSell.symbolRotate).toBe(180)
    })

    it('should have appropriate offset multipliers', () => {
      Object.values(SIGNAL_CONFIG).forEach(config => {
        if (config.offsetMultiplier) {
          expect(config.offsetMultiplier).toBeGreaterThan(0)
          expect(config.offsetMultiplier).toBeLessThan(2)
        }
      })
    })
  })
})