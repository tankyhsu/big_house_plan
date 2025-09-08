import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  fetchDashboard,
  fetchDashboardAgg,
  fetchPositionSeries,
  fetchCategory,
  fetchPosition,
  fetchSignals,
  fetchSignalsByTsCode,
  fetchAllSignals
} from './hooks'
import client from './client'
import type { DashboardResp, CategoryRow, PositionRow, SignalRow } from './types'

// Mock the client
vi.mock('./client')
const mockedClient = vi.mocked(client)

describe('API hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('fetchDashboard', () => {
    it('should fetch dashboard data with correct params', async () => {
      const mockData: DashboardResp = {
        date: '20231201',
        market_value: 100000,
        cost: 95000,
        unrealized_pnl: 5000,
        ret: 0.05,
        cash: 10000,
        total_assets: 110000
      }
      mockedClient.get.mockResolvedValueOnce({ data: mockData })

      const result = await fetchDashboard('20231201')

      expect(mockedClient.get).toHaveBeenCalledWith('/api/dashboard', {
        params: { date: '20231201' }
      })
      expect(result).toEqual(mockData)
    })
  })

  describe('fetchDashboardAgg', () => {
    it('should fetch aggregated dashboard data', async () => {
      const mockData = {
        period: 'day',
        items: [
          { date: '20231201', market_value: 100000, cost: 95000, unrealized_pnl: 5000, ret: 0.05 }
        ]
      }
      mockedClient.get.mockResolvedValueOnce({ data: mockData })

      const result = await fetchDashboardAgg('20231201', '20231231', 'day')

      expect(mockedClient.get).toHaveBeenCalledWith('/api/dashboard/aggregate', {
        params: { start: '20231201', end: '20231231', period: 'day' }
      })
      expect(result).toEqual(mockData)
    })
  })

  describe('fetchPositionSeries', () => {
    it('should fetch position series data with joined ts_codes', async () => {
      const mockData = {
        items: [
          { date: '20231201', ts_code: '000001.SZ', name: 'Test Stock', market_value: 50000 }
        ]
      }
      mockedClient.get.mockResolvedValueOnce({ data: mockData })

      const result = await fetchPositionSeries('20231201', '20231231', ['000001.SZ', '000002.SZ'])

      expect(mockedClient.get).toHaveBeenCalledWith('/api/series/position', {
        params: { start: '20231201', end: '20231231', ts_codes: '000001.SZ,000002.SZ' }
      })
      expect(result).toEqual(mockData)
    })
  })

  describe('fetchCategory', () => {
    it('should fetch category data', async () => {
      const mockData: CategoryRow[] = [
        { name: 'Technology', market_value: 50000, cost: 45000, unrealized_pnl: 5000, ret: 0.11 }
      ]
      mockedClient.get.mockResolvedValueOnce({ data: mockData })

      const result = await fetchCategory('20231201')

      expect(mockedClient.get).toHaveBeenCalledWith('/api/category', {
        params: { date: '20231201' }
      })
      expect(result).toEqual(mockData)
    })
  })

  describe('fetchPosition', () => {
    it('should fetch position data', async () => {
      const mockData: PositionRow[] = [
        {
          ts_code: '000001.SZ',
          name: 'Test Stock',
          shares: 1000,
          price: 10.5,
          market_value: 10500,
          cost: 10000,
          unrealized_pnl: 500,
          ret: 0.05,
          category: 'Technology'
        }
      ]
      mockedClient.get.mockResolvedValueOnce({ data: mockData })

      const result = await fetchPosition('20231201')

      expect(mockedClient.get).toHaveBeenCalledWith('/api/position', {
        params: { date: '20231201' }
      })
      expect(result).toEqual(mockData)
    })
  })

  describe('fetchSignals', () => {
    it('should fetch signals without type filter', async () => {
      const mockData: SignalRow[] = [
        {
          id: 1,
          ts_code: '000001.SZ',
          name: 'Test Stock',
          date: '20231201',
          type: 'BUY_STRUCTURE',
          level: 'HIGH',
          price: 10.5,
          note: 'Test signal'
        }
      ]
      mockedClient.get.mockResolvedValueOnce({ data: mockData })

      const result = await fetchSignals('20231201')

      expect(mockedClient.get).toHaveBeenCalledWith('/api/signal', {
        params: { date: '20231201' }
      })
      expect(result).toEqual(mockData)
    })

    it('should fetch signals with type filter', async () => {
      const mockData: SignalRow[] = []
      mockedClient.get.mockResolvedValueOnce({ data: mockData })

      await fetchSignals('20231201', 'BUY_STRUCTURE')

      expect(mockedClient.get).toHaveBeenCalledWith('/api/signal', {
        params: { date: '20231201', type: 'BUY_STRUCTURE' }
      })
    })

    it('should not include type param when type is "ALL"', async () => {
      const mockData: SignalRow[] = []
      mockedClient.get.mockResolvedValueOnce({ data: mockData })

      await fetchSignals('20231201', 'ALL')

      expect(mockedClient.get).toHaveBeenCalledWith('/api/signal', {
        params: { date: '20231201' }
      })
    })
  })

  describe('fetchSignalsByTsCode', () => {
    it('should fetch signals for specific ts_code', async () => {
      const mockData: SignalRow[] = [
        {
          id: 1,
          ts_code: '000001.SZ',
          name: 'Test Stock',
          date: '20231201',
          type: 'BUY_STRUCTURE',
          level: 'HIGH',
          price: 10.5,
          note: 'Test signal'
        }
      ]
      mockedClient.get.mockResolvedValueOnce({ data: mockData })

      const result = await fetchSignalsByTsCode('20231201', '000001.SZ')

      expect(mockedClient.get).toHaveBeenCalledWith('/api/signal', {
        params: { date: '20231201', ts_code: '000001.SZ' }
      })
      expect(result).toEqual(mockData)
    })
  })

  describe('fetchAllSignals', () => {
    it('should fetch all signals without filters', async () => {
      const mockData: SignalRow[] = []
      mockedClient.get.mockResolvedValueOnce({ data: mockData })

      const result = await fetchAllSignals()

      expect(mockedClient.get).toHaveBeenCalledWith('/api/signal/all', {
        params: {}
      })
      expect(result).toEqual(mockData)
    })

    it('should fetch all signals with all filters', async () => {
      const mockData: SignalRow[] = []
      mockedClient.get.mockResolvedValueOnce({ data: mockData })

      await fetchAllSignals('BUY_STRUCTURE', '000001.SZ', '20231201', '20231231', 100)

      expect(mockedClient.get).toHaveBeenCalledWith('/api/signal/all', {
        params: {
          type: 'BUY_STRUCTURE',
          ts_code: '000001.SZ',
          start_date: '20231201',
          end_date: '20231231',
          limit: 100
        }
      })
    })

    it('should not include type param when type is "ALL"', async () => {
      const mockData: SignalRow[] = []
      mockedClient.get.mockResolvedValueOnce({ data: mockData })

      await fetchAllSignals('ALL', '000001.SZ')

      expect(mockedClient.get).toHaveBeenCalledWith('/api/signal/all', {
        params: {
          ts_code: '000001.SZ'
        }
      })
    })

    it('should handle partial parameters correctly', async () => {
      const mockData: SignalRow[] = []
      mockedClient.get.mockResolvedValueOnce({ data: mockData })

      await fetchAllSignals('BUY_STRUCTURE', undefined, '20231201')

      expect(mockedClient.get).toHaveBeenCalledWith('/api/signal/all', {
        params: {
          type: 'BUY_STRUCTURE',
          start_date: '20231201'
        }
      })
    })
  })
})