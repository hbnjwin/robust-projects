import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reportDataGuard } from '@/router/guards'
import type { RouteLocationNormalized } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { useReportStore } from '@/stores/report'

// Mock API
vi.mock('@/api/reports', () => ({
  getReport: vi.fn(),
  submitReview: vi.fn()
}))

function mockTo(id: string): RouteLocationNormalized {
  return {
    params: { id },
    path: `/reports/${id}`,
    name: 'report-detail',
    fullPath: `/reports/${id}`,
    query: {},
    hash: '',
    matched: [],
    meta: {},
    redirectedFrom: undefined
  }
}

describe('reportDataGuard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('store已有匹配报告时直接放行', async () => {
    const store = useReportStore()
    store.currentReport = {
      id: '42',
      title: '测试报告',
      status: 'pending',
      author: '张工程师',
      reviewer: null,
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-06-01T00:00:00Z',
      sections: [],
      annotations: []
    }

    const result = await (reportDataGuard as Function)(mockTo('42'), {}, vi.fn())
    expect(result).toBe(true)
  })

  it('store为空时（F5刷新场景）调用fetchReport后放行', async () => {
    const store = useReportStore()
    const { getReport } = await import('@/api/reports')
    const mockGetReport = vi.mocked(getReport)
    mockGetReport.mockResolvedValueOnce({
      id: '42',
      title: '测试报告',
      status: 'pending',
      author: '张工程师',
      reviewer: null,
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-06-01T00:00:00Z',
      sections: [],
      annotations: []
    })

    expect(store.currentReport).toBeNull()

    const result = await (reportDataGuard as Function)(mockTo('42'), {}, vi.fn())
    expect(result).toBe(true)
    expect(store.currentReport).not.toBeNull()
    expect(store.currentReport!.id).toBe('42')
  })

  it('store有不同报告时重新获取', async () => {
    const store = useReportStore()
    store.currentReport = {
      id: '99',
      title: '另一个报告',
      status: 'approved',
      author: '李工程师',
      reviewer: null,
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-06-01T00:00:00Z',
      sections: [],
      annotations: []
    }

    const { getReport } = await import('@/api/reports')
    const mockGetReport = vi.mocked(getReport)
    mockGetReport.mockResolvedValueOnce({
      id: '42',
      title: '测试报告',
      status: 'pending',
      author: '张工程师',
      reviewer: null,
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-06-01T00:00:00Z',
      sections: [],
      annotations: []
    })

    const result = await (reportDataGuard as Function)(mockTo('42'), {}, vi.fn())
    expect(result).toBe(true)
    expect(store.currentReport!.id).toBe('42')
  })

  it('API请求失败时重定向到列表页', async () => {
    const store = useReportStore()
    expect(store.currentReport).toBeNull()

    const { getReport } = await import('@/api/reports')
    const mockGetReport = vi.mocked(getReport)
    mockGetReport.mockRejectedValueOnce(new Error('Not found'))

    const result = await (reportDataGuard as Function)(mockTo('999'), {}, vi.fn())
    expect(result).toEqual({
      name: 'report-list',
      query: { error: 'report-not-found', failedId: '999' }
    })
  })
})
