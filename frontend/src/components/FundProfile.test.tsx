import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchFundProfile } from '../api/hooks'
import client from '../api/client'
import type { FundProfile } from '../api/types'

// Mock the client
vi.mock('../api/client')
const mockedClient = vi.mocked(client)

describe('Fund Profile API hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('fetchFundProfile', () => {
    it('should fetch fund profile data with correct params', async () => {
      const mockData: FundProfile = {
        holdings: {
          current: [
            { stock_code: '000001.SZ', stock_name: '平安银行', weight: 5.5, mkv: 50000, amount: 1000 }
          ],
          previous: [
            { stock_code: '000001.SZ', stock_name: '平安银行', weight: 4.8, mkv: 45000, amount: 900 }
          ],
          changes: [
            {
              stock_code: '000001.SZ',
              stock_name: '平安银行',
              current_weight: 5.5,
              previous_weight: 4.8,
              weight_change: 0.7,
              current_mkv: 50000,
              previous_mkv: 45000,
              mkv_change: 5000,
              current_amount: 1000,
              is_new: false,
              is_increased: true,
              is_reduced: false
            }
          ],
          error: null
        },
        scale: {
          recent_shares: [
            { end_date: '20240331', total_share: 5000000000, holder_count: 10000 },
            { end_date: '20240630', total_share: 5200000000, holder_count: 11000 }
          ],
          nav_data: [
            { nav_date: '20240901', unit_nav: 1.2345, accum_nav: 1.5678 },
            { nav_date: '20240902', unit_nav: 1.2356, accum_nav: 1.5689 }
          ],
          error: null
        },
        managers: {
          current_managers: [
            {
              name: '张三',
              gender: '男',
              education: '硕士',
              nationality: '中国',
              begin_date: '20200101',
              end_date: '',
              resume: '资深基金经理，从业10年'
            }
          ],
          error: null
        }
      }

      mockedClient.get.mockResolvedValue({ data: mockData })

      const result = await fetchFundProfile('000001.OF')

      expect(mockedClient.get).toHaveBeenCalledWith('/api/fund/profile', {
        params: { ts_code: '000001.OF', nocache: expect.any(Number) }
      })
      expect(result).toEqual(mockData)
    })

    it('should handle fund profile with errors', async () => {
      const mockErrorData: FundProfile = {
        holdings: {
          current: [],
          previous: [],
          changes: [],
          error: 'no_token'
        },
        scale: {
          recent_shares: [],
          nav_data: [],
          error: 'no_token'
        },
        managers: {
          current_managers: [],
          error: 'no_token'
        }
      }

      mockedClient.get.mockResolvedValue({ data: mockErrorData })

      const result = await fetchFundProfile('000001.OF')

      expect(result.holdings.error).toBe('no_token')
      expect(result.scale.error).toBe('no_token')
      expect(result.managers.error).toBe('no_token')
      expect(result.holdings.changes).toHaveLength(0)
      expect(result.managers.current_managers).toHaveLength(0)
    })

    it('should handle empty fund profile data', async () => {
      const mockEmptyData: FundProfile = {
        holdings: {
          current: [],
          previous: [],
          changes: [],
          error: null
        },
        scale: {
          recent_shares: [],
          nav_data: [],
          error: null
        },
        managers: {
          current_managers: [],
          error: null
        }
      }

      mockedClient.get.mockResolvedValue({ data: mockEmptyData })

      const result = await fetchFundProfile('000001.OF')

      expect(result.holdings.error).toBeNull()
      expect(result.scale.error).toBeNull()
      expect(result.managers.error).toBeNull()
      expect(result.holdings.changes).toHaveLength(0)
      expect(result.scale.recent_shares).toHaveLength(0)
      expect(result.managers.current_managers).toHaveLength(0)
    })

    it('should handle API errors', async () => {
      const apiError = new Error('Network error')
      mockedClient.get.mockRejectedValue(apiError)

      await expect(fetchFundProfile('000001.OF')).rejects.toThrow('Network error')
    })

    it('should include nocache parameter in request', async () => {
      const mockData: FundProfile = {
        holdings: { current: [], previous: [], changes: [], error: null },
        scale: { recent_shares: [], nav_data: [], error: null },
        managers: { current_managers: [], error: null }
      }

      mockedClient.get.mockResolvedValue({ data: mockData })

      await fetchFundProfile('000001.OF')

      const callArgs = mockedClient.get.mock.calls[0]
      expect(callArgs[1].params.nocache).toBeTypeOf('number')
      expect(callArgs[1].params.ts_code).toBe('000001.OF')
    })
  })

  describe('Fund Holdings Data Structure', () => {
    it('should validate holdings change data structure', async () => {
      const mockData: FundProfile = {
        holdings: {
          current: [],
          previous: [],
          changes: [
            {
              stock_code: '000001.SZ',
              stock_name: '平安银行',
              current_weight: 5.5,
              previous_weight: 4.8,
              weight_change: 0.7,
              current_mkv: 50000,
              previous_mkv: 45000,
              mkv_change: 5000,
              current_amount: 1000,
              is_new: false,
              is_increased: true,
              is_reduced: false
            }
          ],
          error: null
        },
        scale: { recent_shares: [], nav_data: [], error: null },
        managers: { current_managers: [], error: null }
      }

      mockedClient.get.mockResolvedValue({ data: mockData })

      const result = await fetchFundProfile('000001.OF')

      const change = result.holdings.changes[0]
      expect(change).toHaveProperty('stock_code')
      expect(change).toHaveProperty('stock_name')
      expect(change).toHaveProperty('current_weight')
      expect(change).toHaveProperty('previous_weight')
      expect(change).toHaveProperty('weight_change')
      expect(change).toHaveProperty('is_new')
      expect(change).toHaveProperty('is_increased')
      expect(change).toHaveProperty('is_reduced')

      expect(typeof change.current_weight).toBe('number')
      expect(typeof change.is_increased).toBe('boolean')
    })

    it('should validate fund manager data structure', async () => {
      const mockData: FundProfile = {
        holdings: { current: [], previous: [], changes: [], error: null },
        scale: { recent_shares: [], nav_data: [], error: null },
        managers: {
          current_managers: [
            {
              name: '张三',
              gender: '男',
              education: '硕士',
              nationality: '中国',
              begin_date: '20200101',
              end_date: '',
              resume: '资深基金经理'
            }
          ],
          error: null
        }
      }

      mockedClient.get.mockResolvedValue({ data: mockData })

      const result = await fetchFundProfile('000001.OF')

      const manager = result.managers.current_managers[0]
      expect(manager).toHaveProperty('name')
      expect(manager).toHaveProperty('gender')
      expect(manager).toHaveProperty('education')
      expect(manager).toHaveProperty('nationality')
      expect(manager).toHaveProperty('begin_date')
      expect(manager).toHaveProperty('resume')

      expect(typeof manager.name).toBe('string')
      expect(manager.name).toBe('张三')
    })
  })
})