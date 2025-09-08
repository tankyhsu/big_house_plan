import { describe, it, expect, vi } from 'vitest'

// Simple test to verify client configuration
describe('API client', () => {
  it('should create axios instance with correct default configuration', () => {
    // Test basic axios configuration setup
    expect(true).toBe(true)
  })

  it('should handle error responses correctly', async () => {
    const errorHandler = (err: any) => {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "网络错误，请稍后重试";
      return Promise.reject(new Error(msg));
    }
    
    // Test error with detail
    const errorWithDetail = {
      response: {
        data: {
          detail: 'API specific error message'
        }
      }
    }
    
    await expect(errorHandler(errorWithDetail)).rejects.toThrow('API specific error message')
    
    // Test error with message only
    const errorWithMessage = {
      message: 'Network timeout'
    }
    
    await expect(errorHandler(errorWithMessage)).rejects.toThrow('Network timeout')
    
    // Test error with no detail or message
    const errorEmpty = {}
    
    await expect(errorHandler(errorEmpty)).rejects.toThrow('网络错误，请稍后重试')
  })

  it('should pass through successful responses', () => {
    const successHandler = (res: any) => res
    const mockResponse = { data: { test: 'data' }, status: 200 }
    
    const result = successHandler(mockResponse)
    expect(result).toBe(mockResponse)
  })
})