import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useReportStore } from '@/stores/report'

// Mock API
vi.mock('@/api/reports', () => ({
  getReport: vi.fn(),
  submitReview: vi.fn()
}))

describe('useReportStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('初始状态正确', () => {
    const store = useReportStore()
    expect(store.currentReport).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('fetchReport成功后设置currentReport', async () => {
    const store = useReportStore()
    const mockReport = {
      id: '1',
      title: '测试报告',
      status: 'pending' as const,
      author: '张工程师',
      reviewer: null,
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-06-01T00:00:00Z',
      sections: [],
      annotations: []
    }

    const { getReport } = await import('@/api/reports')
    vi.mocked(getReport).mockResolvedValueOnce(mockReport)

    await store.fetchReport('1')

    expect(store.currentReport).toEqual(mockReport)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('fetchReport期间loading状态正确变化', async () => {
    const store = useReportStore()

    const { getReport } = await import('@/api/reports')
    let resolvePromise: (value: any) => void
    vi.mocked(getReport).mockReturnValueOnce(
      new Promise(resolve => { resolvePromise = resolve })
    )

    expect(store.loading).toBe(false)

    const fetchPromise = store.fetchReport('1')
    expect(store.loading).toBe(true)

    resolvePromise!({
      id: '1', title: '测试', status: 'pending',
      author: '', reviewer: null, createdAt: '', updatedAt: '',
      sections: [], annotations: []
    })
    await fetchPromise

    expect(store.loading).toBe(false)
  })

  it('fetchReport失败时设置error并抛出异常', async () => {
    const store = useReportStore()

    const { getReport } = await import('@/api/reports')
    vi.mocked(getReport).mockRejectedValueOnce(new Error('网络错误'))

    await expect(store.fetchReport('1')).rejects.toThrow('网络错误')

    expect(store.currentReport).toBeNull()
    expect(store.error).toBe('网络错误')
    expect(store.loading).toBe(false)
  })

  it('$reset恢复初始状态', async () => {
    const store = useReportStore()

    const { getReport } = await import('@/api/reports')
    vi.mocked(getReport).mockResolvedValueOnce({
      id: '1', title: '测试', status: 'pending' as const,
      author: '', reviewer: null, createdAt: '', updatedAt: '',
      sections: [], annotations: []
    })

    await store.fetchReport('1')
    expect(store.currentReport).not.toBeNull()

    store.$reset()
    expect(store.currentReport).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })
})
