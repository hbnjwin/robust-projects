import client from './client'
import type { Report, ReportListFilters, PaginatedResult, ReviewPayload } from '@/types/report'

export async function getReports(filters: ReportListFilters): Promise<PaginatedResult<Report>> {
  const { data } = await client.get<PaginatedResult<Report>>('/reports', {
    params: {
      status: filters.status || undefined,
      page: filters.page || '1',
      keyword: filters.keyword || undefined,
      pageSize: filters.pageSize || '20'
    }
  })
  return data
}

export async function getReport(id: string): Promise<Report> {
  const { data } = await client.get<Report>(`/reports/${id}`)
  return data
}

export async function submitReview(id: string, payload: ReviewPayload): Promise<Report> {
  const { data } = await client.post<Report>(`/reports/${id}/review`, payload)
  return data
}
