<template>
  <div class="report-list">
    <h1>报告列表</h1>

    <!-- 筛选器 -->
    <div class="filters">
      <select v-model="filters.status" @change="updateQuery">
        <option value="">全部状态</option>
        <option value="pending">待审核</option>
        <option value="approved">已通过</option>
        <option value="rejected">已拒绝</option>
      </select>

      <input
        v-model="filters.keyword"
        type="text"
        placeholder="搜索关键词..."
        @input="debounceSearch"
      />

      <button @click="resetFilters">重置</button>
    </div>

    <!-- 报告列表 -->
    <div class="list">
      <div
        v-for="report in filteredReports"
        :key="report.id"
        class="report-item"
        @click="goToDetail(report.id)"
      >
        <h3>{{ report.title }}</h3>
        <p>状态: {{ report.status }}</p>
        <p>创建时间: {{ report.createdAt }}</p>
      </div>
    </div>

    <!-- 分页 -->
    <div class="pagination">
      <button
        :disabled="currentPage === 1"
        @click="changePage(currentPage - 1)"
      >
        上一页
      </button>
      <span>第 {{ currentPage }} 页</span>
      <button
        :disabled="currentPage >= totalPages"
        @click="changePage(currentPage + 1)"
      >
        下一页
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useReportStore } from '@/store/report'

const props = defineProps({
  status: { type: String, default: '' },
  page: { type: Number, default: 1 },
  keyword: { type: String, default: '' }
})

const router = useRouter()
const route = useRoute()
const store = useReportStore()

// 本地筛选状态
const filters = ref({
  status: props.status,
  keyword: props.keyword
})

const currentPage = ref(props.page)
const pageSize = 10

// 计算属性：过滤后的报告
const filteredReports = computed(() => {
  let reports = store.reports

  // 按状态筛选
  if (filters.value.status) {
    reports = reports.filter(r => r.status === filters.value.status)
  }

  // 按关键词筛选
  if (filters.value.keyword) {
    const keyword = filters.value.keyword.toLowerCase()
    reports = reports.filter(r =>
      r.title.toLowerCase().includes(keyword)
    )
  }

  // 分页
  const start = (currentPage.value - 1) * pageSize
  return reports.slice(start, start + pageSize)
})

const totalPages = computed(() => {
  let count = store.reports.length

  if (filters.value.status) {
    count = store.reports.filter(r => r.status === filters.value.status).length
  }

  if (filters.value.keyword) {
    const keyword = filters.value.keyword.toLowerCase()
    count = store.reports.filter(r =>
      r.title.toLowerCase().includes(keyword)
    ).length
  }

  return Math.ceil(count / pageSize) || 1
})

// Bug 1 修复核心：更新 URL query 参数
function updateQuery() {
  const query = {}

  if (filters.value.status) {
    query.status = filters.value.status
  }

  if (filters.value.keyword) {
    query.keyword = filters.value.keyword
  }

  if (currentPage.value > 1) {
    query.page = currentPage.value
  }

  // 使用 router.replace 更新 query，这样浏览器历史会保留这些参数
  // 当用户点击返回按钮时，这些参数会被恢复
  router.replace({
    path: route.path,
    query
  })
}

// 防抖搜索
let searchTimer = null
function debounceSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    updateQuery()
  }, 300)
}

function changePage(page) {
  currentPage.value = page
  updateQuery()
  // 滚动到顶部
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function resetFilters() {
  filters.value.status = ''
  filters.value.keyword = ''
  currentPage.value = 1
  updateQuery()
}

// Bug 1 修复：跳转到详情页时，不携带 query 参数
// 这样返回时会自动恢复到之前的 query 状态
function goToDetail(id) {
  router.push(`/reports/${id}/review`)
}

// 监听 props 变化（从浏览器返回时触发）
watch(() => props.status, (newVal) => {
  filters.value.status = newVal
})

watch(() => props.page, (newVal) => {
  currentPage.value = newVal
})

watch(() => props.keyword, (newVal) => {
  filters.value.keyword = newVal
})

onMounted(async () => {
  // 加载报告数据
  if (!store.isLoaded) {
    await store.loadReports()
  }
})
</script>

<style scoped>
.report-list {
  padding: 20px;
}

.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.filters select,
.filters input {
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.report-item {
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 4px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: background 0.2s;
}

.report-item:hover {
  background: #f5f5f5;
}

.pagination {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 20px;
}

.pagination button {
  padding: 8px 16px;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
}

.pagination button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
