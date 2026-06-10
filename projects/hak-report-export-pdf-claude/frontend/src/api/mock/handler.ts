import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import type { PaginatedResult, Report } from '@/types/report'
import { mockReports } from './data'

function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function mockResponse<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: {} as InternalAxiosRequestConfig
  }
}

function handleGetReports(config: InternalAxiosRequestConfig): AxiosResponse<PaginatedResult<Report>> {
  const params = config.params || {}
  const status = params.status as string | undefined
  const keyword = params.keyword as string | undefined
  const page = parseInt(params.page || '1', 10)
  const pageSize = parseInt(params.pageSize || '20', 10)

  let filtered = [...mockReports]

  if (status) {
    filtered = filtered.filter(r => r.status === status)
  }
  if (keyword) {
    filtered = filtered.filter(r => r.title.includes(keyword))
  }

  const total = filtered.length
  const start = (page - 1) * pageSize
  const items = filtered.slice(start, start + pageSize)

  return mockResponse({ items, total, page, pageSize })
}

function handleGetReport(id: string): AxiosResponse<Report> | null {
  const report = mockReports.find(r => r.id === id)
  if (!report) return null
  return mockResponse(report)
}

function handleSubmitReview(id: string, body: Record<string, unknown>): AxiosResponse<Report> | null {
  const report = mockReports.find(r => r.id === id)
  if (!report) return null

  const action = body.action as string
  if (action === 'approve') {
    report.status = 'approved'
  } else if (action === 'reject') {
    report.status = 'rejected'
  }
  report.updatedAt = new Date().toISOString()

  return mockResponse({ ...report })
}

export function setupMock(client: AxiosInstance): void {
  client.interceptors.request.use(async (config) => {
    const url = config.url || ''
    const method = (config.method || 'get').toLowerCase()

    // Simulate network latency (300-500ms)
    await delay(300 + Math.random() * 200)

    let response: AxiosResponse | null = null

    // GET /reports
    if (method === 'get' && url === '/reports') {
      response = handleGetReports(config)
    }

    // GET /reports/:id
    const detailMatch = url.match(/^\/reports\/(\d+)$/)
    if (method === 'get' && detailMatch) {
      response = handleGetReport(detailMatch[1])
      if (!response) {
        return Promise.reject({
          response: { status: 404, data: { message: '报告未找到' } }
        })
      }
    }

    // POST /reports/:id/review
    const reviewMatch = url.match(/^\/reports\/(\d+)\/review$/)
    if (method === 'post' && reviewMatch) {
      const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
      response = handleSubmitReview(reviewMatch[1], body)
      if (!response) {
        return Promise.reject({
          response: { status: 404, data: { message: '报告未找到' } }
        })
      }
    }

    if (response) {
      // Abort the real request and return mock data via adapter
      config.adapter = () => Promise.resolve(response!)
    }

    return config
  })
}
