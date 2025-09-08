import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import KpiCards from './KpiCards'

// Mock the format utilities
vi.mock('../utils/format', () => ({
  fmtCny: vi.fn((value) => `¥${value?.toLocaleString() || '-'}`),
  fmtPct: vi.fn((value) => `${(value * 100).toFixed(2)}%`)
}))

// Mock the signal config
vi.mock('../utils/signalConfig', () => ({
  getSignalConfig: vi.fn((type) => ({
    label: type === 'BUY_STRUCTURE' ? '九转买入' : '测试信号',
    color: '#52c41a',
    emoji: '📈'
  }))
}))

describe('KpiCards', () => {
  const defaultProps = {
    marketValue: 100000,
    cost: 95000,
    pnl: 5000,
    ret: 0.0526,
    signals: { BUY_STRUCTURE: 2, SELL_STRUCTURE: 1 },
    priceFallback: false,
    dateText: '2023-12-01'
  }

  it('should render market value card', () => {
    render(<KpiCards {...defaultProps} />)
    
    expect(screen.getByText('总资产（2023-12-01）')).toBeInTheDocument()
    expect(screen.getByText('¥100,000')).toBeInTheDocument()
  })

  it('should render profit and loss information', () => {
    render(<KpiCards {...defaultProps} />)
    
    expect(screen.getByText('累计收益：')).toBeInTheDocument()
    expect(screen.getByText('¥5,000')).toBeInTheDocument()
  })

  it('should display price fallback warning when enabled', () => {
    render(<KpiCards {...defaultProps} priceFallback={true} />)
    
    expect(screen.getByText('价格回退')).toBeInTheDocument()
    // The tooltip text should be available but might not be visible without hover
    // Just check that the warning tag is present
  })

  it('should not display price fallback warning when disabled', () => {
    render(<KpiCards {...defaultProps} priceFallback={false} />)
    
    expect(screen.queryByText('价格回退')).not.toBeInTheDocument()
  })

  it('should render cost information', () => {
    render(<KpiCards {...defaultProps} />)
    
    expect(screen.getByText('投入成本')).toBeInTheDocument()
    expect(screen.getByText('¥95,000')).toBeInTheDocument()
  })

  it('should render return rate when available', () => {
    render(<KpiCards {...defaultProps} />)
    
    expect(screen.getByText('5.26%')).toBeInTheDocument()
  })

  it('should handle null return rate', () => {
    render(<KpiCards {...defaultProps} ret={null} />)
    
    // Should still render the component without throwing
    expect(screen.getByText('总资产（2023-12-01）')).toBeInTheDocument()
  })

  it('should render signal counts', () => {
    render(<KpiCards {...defaultProps} />)
    
    // Should display signal information as "label: count" format
    expect(screen.getByText('九转买入: 2')).toBeInTheDocument() // BUY_STRUCTURE
    expect(screen.getByText('测试信号: 1')).toBeInTheDocument() // SELL_STRUCTURE
  })

  it('should handle empty signals object', () => {
    render(<KpiCards {...defaultProps} signals={{}} />)
    
    // Should still render the component
    expect(screen.getByText('总资产（2023-12-01）')).toBeInTheDocument()
  })

  it('should handle negative values correctly', () => {
    const negativeProps = {
      ...defaultProps,
      marketValue: 90000,
      pnl: -5000,
      ret: -0.0526
    }
    
    render(<KpiCards {...negativeProps} />)
    
    expect(screen.getByText('¥90,000')).toBeInTheDocument()
    expect(screen.getByText('¥-5,000')).toBeInTheDocument()
    expect(screen.getByText('-5.26%')).toBeInTheDocument()
  })

  it('should use correct date text', () => {
    render(<KpiCards {...defaultProps} dateText="2024-01-15" />)
    
    expect(screen.getByText('总资产（2024-01-15）')).toBeInTheDocument()
  })
})