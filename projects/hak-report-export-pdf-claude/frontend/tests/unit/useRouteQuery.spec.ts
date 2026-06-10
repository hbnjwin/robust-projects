import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reactive, nextTick } from 'vue'

// Mock vue-router — useRoute() 返回 reactive 对象，和真实行为一致
const mockRoute = reactive({
  query: {} as Record<string, string>,
  path: '/reports'
})
const pushSpy = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushSpy,
    replace: vi.fn()
  }),
  useRoute: () => mockRoute
}))

import { useRouteQuery } from '@/composables/useRouteQuery'

describe('useRouteQuery', () => {
  beforeEach(() => {
    mockRoute.query = {}
    mockRoute.path = '/reports'
    pushSpy.mockClear()
  })

  it('无query参数时返回默认值', () => {
    const { filters } = useRouteQuery({
      status: '',
      page: '1',
      keyword: ''
    })

    expect(filters.value).toEqual({
      status: '',
      page: '1',
      keyword: ''
    })
  })

  it('从route.query读取参数覆盖默认值', () => {
    mockRoute.query = { status: 'pending', page: '3' }

    const { filters } = useRouteQuery({
      status: '',
      page: '1',
      keyword: ''
    })

    expect(filters.value).toEqual({
      status: 'pending',
      page: '3',
      keyword: ''
    })
  })

  it('updateFilters调用router.push（非replace）', () => {
    mockRoute.query = { status: 'pending', page: '1' }

    const { updateFilters } = useRouteQuery({
      status: '',
      page: '1',
      keyword: ''
    })

    updateFilters({ status: 'approved' })

    // 验证调用的是 push 而非 replace
    expect(pushSpy).toHaveBeenCalledTimes(1)
    expect(pushSpy).toHaveBeenCalledWith({
      path: '/reports',
      query: {
        status: 'approved',
        page: '1'
      }
    })
  })

  it('部分更新时保留其他参数', () => {
    mockRoute.query = { status: 'pending', page: '3', keyword: '风机' }

    const { updateFilters } = useRouteQuery({
      status: '',
      page: '1',
      keyword: ''
    })

    updateFilters({ page: '5' })

    expect(pushSpy).toHaveBeenCalledWith({
      path: '/reports',
      query: {
        status: 'pending',
        page: '5',
        keyword: '风机'
      }
    })
  })

  it('route.query变化时filters自动更新', async () => {
    const { filters } = useRouteQuery({
      status: '',
      page: '1'
    })

    expect(filters.value.status).toBe('')

    mockRoute.query = { status: 'rejected' }
    await nextTick()

    expect(filters.value.status).toBe('rejected')
  })

  it('resetFilters清空所有参数', () => {
    mockRoute.query = { status: 'pending', page: '3', keyword: '风机' }

    const { resetFilters } = useRouteQuery({
      status: '',
      page: '1',
      keyword: ''
    })

    resetFilters()

    expect(pushSpy).toHaveBeenCalledWith({
      path: '/reports',
      query: {}
    })
  })
})
