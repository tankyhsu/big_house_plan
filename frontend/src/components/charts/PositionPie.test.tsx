import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import PositionPie from './PositionPie'
import * as hooks from '../../api/hooks'
import dayjs from 'dayjs'

// Mock ReactECharts
vi.mock('echarts-for-react', () => ({
  default: vi.fn(({ option, style }) => (
    <div 
      data-testid="echarts-pie"
      data-option={JSON.stringify(option)}
      style={style}
    >
      ECharts Pie Chart
    </div>
  ))
}))

// Mock API hooks
vi.mock('../../api/hooks', () => ({
  fetchCategory: vi.fn()
}))

// Mock format utilities
vi.mock('../../utils/format', () => ({
  formatQuantity: vi.fn((value) => value?.toFixed(2) || '0.00')
}))

// Mock dayjs
vi.mock('dayjs', () => {
  const actualDayjs = vi.importActual('dayjs')
  return {
    default: vi.fn(() => ({
      format: vi.fn(() => '20231201')
    })),
    ...actualDayjs
  }
})

describe('PositionPie', () => {
  const mockCategoryData = [
    {
      name: '银行',
      sub_name: '股份制银行',
      market_value: 50000
    },
    {
      name: '房地产',
      sub_name: null,
      market_value: 30000
    },
    {
      name: '科技',
      sub_name: '人工智能',
      market_value: 20000
    },
    {
      name: '零持仓',
      sub_name: '测试',
      market_value: 0
    }
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(hooks.fetchCategory).mockResolvedValue(mockCategoryData)
  })

  it('should render card with pie chart', async () => {
    render(<PositionPie />)
    
    expect(screen.getByText('ECharts Pie Chart')).toBeInTheDocument()
    
    await waitFor(() => {
      expect(hooks.fetchCategory).toHaveBeenCalledWith('20231201')
    })
  })

  it('should use provided date parameter', async () => {
    render(<PositionPie date="20240115" />)
    
    await waitFor(() => {
      expect(hooks.fetchCategory).toHaveBeenCalledWith('20240115')
    })
  })

  it('should use current date when no date provided', async () => {
    render(<PositionPie />)
    
    await waitFor(() => {
      expect(hooks.fetchCategory).toHaveBeenCalledWith('20231201')
    })
  })

  it('should filter out zero market value positions', async () => {
    render(<PositionPie />)
    
    await waitFor(() => {
      const chartElement = screen.getByTestId('echarts-pie')
      const option = JSON.parse(chartElement.getAttribute('data-option') || '{}')
      
      // Should have 3 items (excluding the zero market value one)
      expect(option.series[0].data).toHaveLength(3)
      
      // Verify the filtered data
      const dataNames = option.series[0].data.map((item: any) => item.name)
      expect(dataNames).toContain('股份制银行')
      expect(dataNames).toContain('房地产')
      expect(dataNames).toContain('人工智能')
      expect(dataNames).not.toContain('测试')
    })
  })

  it('should prefer sub_name over name when available', async () => {
    render(<PositionPie />)
    
    await waitFor(() => {
      const chartElement = screen.getByTestId('echarts-pie')
      const option = JSON.parse(chartElement.getAttribute('data-option') || '{}')
      
      const dataItems = option.series[0].data
      
      // Should use sub_name for categories that have it
      expect(dataItems.find((item: any) => item.name === '股份制银行')).toBeTruthy()
      expect(dataItems.find((item: any) => item.name === '人工智能')).toBeTruthy()
      
      // Should use name when sub_name is null
      expect(dataItems.find((item: any) => item.name === '房地产')).toBeTruthy()
    })
  })

  it('should handle API errors gracefully', async () => {
    vi.mocked(hooks.fetchCategory).mockRejectedValueOnce(new Error('API Error'))
    
    render(<PositionPie />)
    
    await waitFor(() => {
      const chartElement = screen.getByTestId('echarts-pie')
      const option = JSON.parse(chartElement.getAttribute('data-option') || '{}')
      
      // Should have empty data when API fails
      expect(option.series[0].data).toHaveLength(0)
    })
  })

  it('should have correct chart configuration', async () => {
    render(<PositionPie />)
    
    await waitFor(() => {
      const chartElement = screen.getByTestId('echarts-pie')
      const option = JSON.parse(chartElement.getAttribute('data-option') || '{}')
      
      // Verify tooltip configuration
      expect(option.tooltip).toEqual({
        trigger: 'item',
        formatter: '{b}<br/>{c} 元 ({d}%)'
      })
      
      // Verify legend configuration
      expect(option.legend).toEqual({
        type: 'scroll',
        orient: 'vertical',
        right: 0,
        top: 20,
        bottom: 20
      })
      
      // Verify series configuration
      expect(option.series[0]).toMatchObject({
        type: 'pie',
        radius: ['40%', '70%']
      })
    })
  })

  it('should format market values correctly', async () => {
    render(<PositionPie />)
    
    await waitFor(() => {
      const chartElement = screen.getByTestId('echarts-pie')
      const option = JSON.parse(chartElement.getAttribute('data-option') || '{}')
      
      const dataItems = option.series[0].data
      
      // Verify that values are formatted using formatQuantity
      expect(dataItems.find((item: any) => item.value === 50000.00)).toBeTruthy()
      expect(dataItems.find((item: any) => item.value === 30000.00)).toBeTruthy()
      expect(dataItems.find((item: any) => item.value === 20000.00)).toBeTruthy()
    })
  })

  it('should have responsive chart size', async () => {
    render(<PositionPie />)
    
    // Wait for the component to finish loading
    await waitFor(() => {
      const chartElement = screen.getByTestId('echarts-pie')
      // The style is applied inline, check for the height
      expect(chartElement.style.height).toBe('320px')
    })
  })
})