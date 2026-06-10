export interface Report {
  id: string
  title: string
  status: 'draft' | 'pending' | 'approved' | 'rejected'
  author: string
  reviewer: string | null
  createdAt: string
  updatedAt: string
  sections: ReportSection[]
  annotations: Annotation[]
}

export interface ReportSection {
  id: string
  title: string
  content: string
  order: number
}

export interface Annotation {
  id: string
  sectionId: string
  content: string
  author: string
  createdAt: string
}

export interface ReportListFilters {
  status: string
  page: string
  keyword: string
  pageSize: string
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

export interface ReviewPayload {
  action: 'approve' | 'reject'
  comment: string
}
