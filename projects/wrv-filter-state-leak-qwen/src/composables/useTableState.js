import { ref, reactive, watch } from 'vue'

/**
 * 表格状态统一管理 composable。
 * 解决 filterParams / sortParams / pagination 三个独立响应式对象
 * 在路由切换（keep-alive）时状态不同步的问题。
 *
 * @param {Function} fetchApi - async (params) => { list: [], total: number }
 * @param {Object} options
 * @param {Object} options.defaultFilters - 筛选初始值，如 { docType: '', keyword: '' }
 * @param {string[]} options.sortableFields - 后端接受的排序字段白名单
 * @param {number} options.defaultPageSize - 每页行数（默认 20）
 */
export function useTableState(fetchApi, options = {}) {
  const {
    defaultFilters = {},
    sortableFields = [],
    defaultPageSize = 20,
  } = options

  // ── 已提交的筛选条件（上次发送给 API 的值）──────────────────────────
  const filters = reactive({ ...defaultFilters })

  // ── 草稿筛选条件（UI 当前显示的值）────────────────────────────────
  // 绑定到模板的 v-model，变更不会自动触发请求，
  // 需要通过 commitFilters() 提交后才会触发。
  const filterDraft = reactive({ ...defaultFilters })

  // 已提交 → 草稿同步（如 resetAll() 后 UI 需要跟着更新）
  watch(
    filters,
    (val) => { Object.assign(filterDraft, val) },
    { deep: true, flush: 'sync' }
  )

  // ── 排序状态 ─────────────────────────────────────────────────────────
  const sort = ref({})

  // ── 分页状态 ─────────────────────────────────────────────────────────
  const pagination = reactive({ current: 1, pageSize: defaultPageSize })

  // ── 数据状态 ─────────────────────────────────────────────────────────
  const tableData = ref([])
  const total = ref(0)
  const loading = ref(false)

  // ── 核心操作 ─────────────────────────────────────────────────────────

  /** 提交草稿筛选 → 触发 watcher → fetchData() */
  function commitFilters() {
    Object.assign(filters, filterDraft)
  }

  /** 构建发送给 API 的扁平参数对象。单一数据源，杜绝状态漂移。 */
  function buildParams() {
    const params = {
      ...filters,
      current: pagination.current,
      pageSize: pagination.pageSize,
    }
    // 排序字段白名单校验，防止按不存在的字段排序导致后端 500
    if (sort.value.sortBy && sortableFields.includes(sort.value.sortBy)) {
      params.sortBy = sort.value.sortBy
      params.order = sort.value.descending ? 'desc' : 'asc'
    }
    return params
  }

  /** 使用当前统一状态获取数据 */
  async function fetchData() {
    loading.value = true
    try {
      const res = await fetchApi(buildParams())
      tableData.value = res.list ?? []
      total.value = res.total ?? 0
    } catch (err) {
      console.error('[useTableState] fetchData error:', err)
      tableData.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  // ── 事件处理 ─────────────────────────────────────────────────────────

  /**
   * TDesign t-table @sort-change 处理
   * 接收 { sortBy: string, descending: boolean } 或清空时为空对象
   */
  function onSortChange(s) {
    sort.value = s ?? {}
    pagination.current = 1 // 重新排序始终回到第1页
    fetchData()
  }

  /**
   * TablePagination @change 处理
   * 接收 { current: number, pageSize: number }
   */
  function onPageChange(p) {
    pagination.current = p.current
    pagination.pageSize = p.pageSize
    fetchData()
  }

  /** 重置全部状态（筛选 + 排序 + 分页）并重新获取数据 */
  function resetAll() {
    Object.assign(filters, defaultFilters)
    Object.assign(filterDraft, defaultFilters)
    sort.value = {}
    pagination.current = 1
    pagination.pageSize = defaultPageSize
    fetchData()
  }

  // ── 筛选变化自动触发请求 ─────────────────────────────────────────────
  // deep: true 监听嵌套属性变化
  // 默认 flush ('pre') 保证 resetAll() 中的多次同步修改只触发一次 watcher
  watch(
    filters,
    () => {
      pagination.current = 1 // 筛选变化始终回到第1页
      fetchData()
    },
    { deep: true }
  )

  return {
    // 状态（refs/reactives — 传给模板绑定）
    filterDraft,
    filters,
    sort,
    pagination,
    tableData,
    total,
    loading,

    // 操作（methods — 传给事件处理）
    commitFilters,
    fetchData,
    onSortChange,
    onPageChange,
    resetAll,
  }
}
