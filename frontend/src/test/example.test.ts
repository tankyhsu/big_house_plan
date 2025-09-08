import { describe, it, expect, vi } from 'vitest'

describe('Test Setup Verification', () => {
  it('should verify that Vitest is working correctly', () => {
    expect(1 + 1).toBe(2)
  })

  it('should verify that mocking works', () => {
    const mockFn = vi.fn(() => 'mocked')
    expect(mockFn()).toBe('mocked')
    expect(mockFn).toHaveBeenCalledTimes(1)
  })
})